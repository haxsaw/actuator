import string
import threading
from errator import narrate, narrate_cm
from actuator.modeling import AbstractModelReference
from actuator.task import TaskEngine, GraphableModelMixin
from actuator.utils import (root_logger, LOG_INFO, get_mapper)


class ProvisionerException(Exception):
    pass


class AbstractRunContext(object):
    pass


class BaseProvisionerProxy(object):
    """
    A local object that serves as a proxy to some cloud or virtualisation system,
    providing methods and object to the API for that system that allows resources to
    be provisioned.
    """
    # this must be the string name of the class mapper to use
    # to find the tasks associated with this provisioner's resources
    mapper_domain_name = None

    def __init__(self):
        self.run_contexts = {}
        self.class_mapper = get_mapper(self.mapper_domain_name)

    def get_context(self):
        """
        fetch a run context specific to this kind of provisioner proxy. if this
        thread has already created a context return that
        :return: a derived class of AbstractRunContext
        """
        context = self.run_contexts.get(threading.current_thread())
        if context is None:
            context = self.run_context_factory()
            self.run_contexts[threading.current_thread()] = context
        return context

    def run_context_factory(self):
        """
        Creates a new instance of the appropriate AbstractRunContext derived class
        must be overridden by the derived class in order to return the proper object
        :return: an instance of a derived class of AbstractRunContext
        """
        raise TypeError("Derived class must implement")

    def get_resource_taskclass(self, rsrc):
        """
        If the provisioner knows this resource, returns the task class object whose instances can provision it

        :param rsrc: An instance of a Provisionable derived class
        :return: either a callable that returns an instance of Task subclass, or None
            if the resource isn't one that this proxy knows or has an associated
            task for
        """
        return self.class_mapper.get(rsrc.__class__)


class ProvisioningTaskEngine(TaskEngine, GraphableModelMixin):
    no_punc = string.maketrans(string.punctuation, "_" * len(string.punctuation))
    exception_class = ProvisionerException
    exec_agent = "rsrc_provisioning_engine"
    repeat_count = 3

    def __init__(self, infra_model, provisioner_proxies, num_threads=5,
                 log_level=LOG_INFO, no_delay=True):
        """
        Creates a new provisioning task engine
        :param infra_model: the InfraModel that contains all of the resources to provision
        :param provisioner_proxies: a sequence of BaseProvisionerProxy objects that are able
            to provide the assitance needed for each resource to be provisioned
        :param num_threads: the number of threads to start when provisioning is to begin
        :param log_level: one of the logging levels from the logging module
        :param no_delay: bool; False if a short artificial delay should be injected prior
            to the performance of a task.
        """
        self.logger = root_logger.getChild("prov_task_engine")
        self.infra_model = infra_model
        self.event_handler = infra_model.get_event_handler()
        self.provisioner_proxies = provisioner_proxies
        super(ProvisioningTaskEngine, self).__init__("{}-engine".format(infra_model.name),
                                                     self,
                                                     num_threads=num_threads,
                                                     log_level=log_level,
                                                     no_delay=no_delay)
        self.rsrc_task_map = {}
        self.task_proxy_map = {}

    def get_event_handler(self):
        """
        Return the event handler object (if any) used to flag
        :return:
        """
        return self.event_handler

    @narrate("...which entailed collecting the tasks to provision the resources")
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
        for rsrc in all_resources:
            if rsrc in self.rsrc_task_map:
                # we reuse a resource task in case we're told to run again and we
                # want to be able to determine what has already been provisioned
                tasks.append(self.rsrc_task_map[rsrc])
                continue
            rsrc.fix_arguments()
            with narrate_cm(lambda cls: "-which requires looking for the task class for resource "
                                        "class {}".format(cls.__name__),
                            rsrc.__class__):
                task_class = None
                proxy = None
                for pp in self.provisioner_proxies:
                    task_class = pp.get_resource_taskclass(rsrc)
                    if task_class is not None:
                        proxy = pp
                        break
                else:
                    ref = AbstractModelReference.find_ref_for_obj(rsrc)
                    path = ref.get_path() if ref is not None else "NO PATH"
                    raise self.exception_class("Could not find a task for resource "
                                               "%s named %s at path %s" %
                                               (rsrc.__class__.__name__,
                                                rsrc.name, path))
            task = task_class(rsrc, repeat_count=self.repeat_count)
            tasks.append(task)
            self.rsrc_task_map[rsrc] = task
            self.task_proxy_map[task] = proxy
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

    @narrate(lambda _, t, **kw: "...when the task engine was asked to start preforming task {}".format(t.name))
    def _perform_task(self, task, logfile=None):
        self.logger.info("Starting provisioning task %s named %s, id %s" %
                         (task.__class__.__name__, task.name, str(task._id)))
        try:
            task.perform(self.task_proxy_map[task])
        finally:
            self.logger.info("Completed attempting to provision task %s named %s, id %s" %
                             (task.__class__.__name__, task.name, str(task._id)))

    @narrate(lambda _, t, **kw: "...when a provisioning task engine worker was asked to reverse task {}".format(t.name))
    def _reverse_task(self, task, logfile=None):
        self.logger.info("Starting reversing task %s named %s, id %s" %
                         (task.__class__.__name__, task.name, str(task._id)))
        try:
            task.reverse(self.task_proxy_map[task])
        finally:
            self.logger.info("Completed attempting to reverse task %s named %s, id %s" %
                             (task.__class__.__name__, task.name, str(task._id)))

