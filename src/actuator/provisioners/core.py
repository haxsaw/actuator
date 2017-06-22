# 
# Copyright (c) 2014 Tom Carroll
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Base classes for all Actuator provisioners.
"""
import string
import threading
from errator import narrate, narrate_cm
from actuator.modeling import AbstractModelReference
from actuator.task import Task
from actuator.infra import InfraModel
from actuator.task import TaskEngine, GraphableModelMixin
from actuator.utils import (root_logger, LOG_INFO, get_mapper)


class ProvisionerException(Exception):
    def __init__(self, msg, record=None):
        super(ProvisionerException, self).__init__(msg)
        self.record = record


class BaseProvisioner(object):
    """
    Base class for all provisioners.
    """
    @narrate(lambda _, imi: "...which caused the infra model {} to start the provisioning process".format(imi.name))
    def provision_infra_model(self, inframodel_instance):
        """
        Instructs the provisioner to do the work to provision the supplied
        infra model
        
        @param inframodel_instance: An instance of a derived class of InfraModel
        """
        if not isinstance(inframodel_instance, InfraModel):
            raise ProvisionerException("Provisioner asked to provision something not an InfraModel")
        _ = inframodel_instance.refs_for_components()
        return self._provision(inframodel_instance)
    
    def _provision(self, inframodel_instance):
        raise TypeError("Derived class must implement _provision()")
    
    def deprovision_infra_from_record(self, record):
        """
        Not implemented.
        """
        if not isinstance(record, BaseProvisioningRecord):
            raise ProvisionerException("Record must be a kind of BaseProvisioningRecord")
        self._deprovision(record)
        
    def deprovision_infra_model(self, inframodel_instance):
        if not isinstance(inframodel_instance, InfraModel):
            raise ProvisionerException("Deprovision must be supplied an InfraModel"
                                       " instance, not %s" % str(inframodel_instance))
        _ = inframodel_instance.refs_for_components()
        return self._deprovision(inframodel_instance)
        
    def _deprovision(self, inframodel_instance, record=None):
        raise TypeError("Derived class must implement _deprovision()")
    
    
class BaseProvisioningRecord(object):
    """
    Captures the details of provisioning a single resource.
    """
    def __init__(self, rid):
        self.id = rid
        
    def __getstate__(self):
        return {"id": self.id}
    
    def __setstate__(self, state):
        self.id = state["id"]
        del state["id"]


class ProvisioningTask(Task):
    clone_attrs = False
    _rsrc_by_id = {}

    def __init__(self, rsrc, repeat_count=1):
        super(ProvisioningTask, self).__init__("{}_provisioning_{}_task"
                                               .format(rsrc.name,
                                                       rsrc.__class__.__name__),
                                               repeat_count=repeat_count)
        self._rsrc_by_id[rsrc._id] = rsrc
        self.rsrc_id = rsrc._id

    def get_performance_status(self):
        rsrc = self._rsrc_by_id.get(self.rsrc_id)
        if not rsrc:
            raise ProvisionerException("get_performance_status can't find resource %s by id while trying to determine its performance_status"
                                       % self.rsrc_id)
        return rsrc.get_performance_status()

    def set_performance_status(self, status):
        rsrc = self._rsrc_by_id.get(self.rsrc_id)
        if not rsrc:
            raise ProvisionerException("set_performance_status can't find resource %s by id while trying to determine its performance_status" % self.rsrc_id)
        rsrc.set_performance_status(status)

    def _get_rsrc(self):
        return self._rsrc_by_id[self.rsrc_id]

    rsrc = property(_get_rsrc)

    def get_ref(self):
        return AbstractModelReference.find_ref_for_obj(self.rsrc)

    def depends_on_list(self):
        return []

    def _perform(self, engine):
        """
        override this method to perform the actual provisioning work. there is
        no return value
        """
        return

    def _reverse(self, engine):
        return

    def get_init_args(self):
        return (self.rsrc,), {"repeat_count": self.repeat_count}


class BaseTaskSequencerAgent(TaskEngine, GraphableModelMixin):
    no_punc = string.maketrans(string.punctuation, "_"*len(string.punctuation))
    exception_class = ProvisionerException
    exec_agent = "rsrc_provisioner"
    repeat_count = 3

    def __init__(self, infra_model, class_mapper_domain, run_context_factory, num_threads=5,
                 log_level=LOG_INFO, no_delay=True):
        self.logger = root_logger.getChild("os_prov_agent")
        self.infra_model = infra_model
        self.event_handler = infra_model.get_event_handler()
        self.class_mapper_domain = class_mapper_domain
        self.run_context_factory = run_context_factory
        super(BaseTaskSequencerAgent, self).__init__("{}-engine".format(infra_model.name),
                                                     self,
                                                     num_threads=num_threads,
                                                     log_level=log_level,
                                                     no_delay=no_delay)
        self.run_contexts = {}  # keys are threads, values are RunContext objects
        # self.record = OpenstackProvisioningRecord(uuid.uuid4())
        # self.os_creds = os_creds
        self.rsrc_task_map = {}

    def get_event_handler(self):
        return self.event_handler

    @narrate("...and then it was required to collect the tasks to provision the resources")
    def get_tasks(self):
        """
        Returns a list of all the tasks for provisioning the resources

        Looks to the resources in the infra_model and creates appropriate
        tasks to provision each. Returns a list of the created tasks. A new
        list with the same task will be returned for subsequent calls.
        Raises an exception if a task can't be determined for a resource.

        @raise ProvisionerException: Raised if a resource is found for which
            there is no corresponding task.
        """
        with narrate_cm("-starting by looking in the infra model for all the components that have to be provisioned"):
            all_resources = set(self.infra_model.components())
        tasks = []
        self.logger.info("%s resources to provision" % len(all_resources))
        with narrate_cm(lambda dname: "-which requires getting the resource to task mapper for task "
                                      "domain {}".format(dname),
                        self.class_mapper_domain):
            class_mapper = get_mapper(self.class_mapper_domain)
        for rsrc in all_resources:
            if rsrc in self.rsrc_task_map:
                tasks.append(self.rsrc_task_map[rsrc])
                continue
            rsrc.fix_arguments()
            with narrate_cm(lambda cls: "-which requires looking for the task class for resource "
                                        "class {}".format(cls.__name__),
                            rsrc.__class__):
                task_class = class_mapper.get(rsrc.__class__)
                if task_class is None:
                    ref = AbstractModelReference.find_ref_for_obj(rsrc)
                    path = ref.get_path() if ref is not None else "NO PATH"
                    raise self.exception_class("Could not find a task for resource "
                                               "%s named %s at path %s" %
                                               (rsrc.__class__.__name__,
                                                rsrc.name, path))
            task = task_class(rsrc, repeat_count=self.repeat_count)
            tasks.append(task)
            self.rsrc_task_map[rsrc] = task
        return tasks

    @narrate("...which required computing the dependencies between the resources")
    def get_dependencies(self):
        """
        Returns a list of _Dependency objects for the tasks in the model

        This method creates and returns a list of _Dependency objects that
        represent the dependencies in the resource provisioning graph. If the
        method comes across a dependent resource that wasn't represented by
        the tasks returned by get_tasks(), an exception is raised.

        @raise ProvisionerException: Raised if a dependency is discovered that
            involves a resource not considered by get_tasks()
        """
        # now, self already contains a rsrc_task_map, but that's meant to be
        # used as a cache for multiple calls to get_tasks so that the tasks
        # returned are always the same. However, we can't assume in this
        # method that get_tasks() has already been called, or that doing
        # so causes the side-effect that self.rsrc_task_map gets populated
        # (or that it even exists). So we get the tasks and construct our own
        # map, just to be on the safe side.
        rsrc_task_map = {task.rsrc: task for task in self.get_tasks()}
        dependencies = []
        for rsrc, task in rsrc_task_map.items():
            for d in task.depends_on_list():
                with narrate_cm(lambda r:
                                "-first, resource {}, class {} is check to be in the set of known resources"
                                .format(r.name, r.__class__.__name__), rsrc):
                    if d not in rsrc_task_map:
                        ref = AbstractModelReference.find_ref_for_obj(d)
                        path = ref.get_path() if ref is not None else "NO PATH"
                        raise self.exception_class("Resource {} named {} path {} says it depends on {}, "
                                                   "but the latter isn't in the list of all components"
                                                   .format(rsrc.__class__.__name__,
                                                           rsrc.name, path,
                                                           d.name))
                dtask = rsrc_task_map[d]
                dependencies.append(dtask | task)
        self.logger.info("%d resource dependencies" % len(dependencies))
        return dependencies

    def get_context(self):
        context = self.run_contexts.get(threading.current_thread())
        if context is None:
            context = self.run_context_factory()
            self.run_contexts[threading.current_thread()] = context
        return context

    @narrate(lambda _, t, **kw: "...when the task engine was asked to start preforming task {}".format(t.name))
    def _perform_task(self, task, logfile=None):
        self.logger.info("Starting provisioning task %s named %s, id %s" %
                         (task.__class__.__name__, task.name, str(task._id)))
        try:
            task.perform(self)
        finally:
            self.logger.info("Completed provisioning task %s named %s, id %s" %
                             (task.__class__.__name__, task.name, str(task._id)))
