# The MIT License (MIT)
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
Base package for Actuator.

Contains most of the imported symbols from sub-packages and the orchestrator.
"""

import datetime
import collections

import time
from errator import narrate
from modeling import (MultiComponent, MultiComponentGroup, ComponentGroup, ModelReference,
                      ctxt, ActuatorException, _Nexus, CallContext, ModelBaseMeta, ModelBase,
                      ModelComponent, ModelInstanceReference, AbstractModelingEntity)
from infra import (InfraModel, InfraException, with_resources, StaticServer,
                   ResourceGroup, MultiResource, MultiResourceGroup,
                   with_infra_options, InfraModelMeta)
from namespace import (Var, NamespaceModel, with_variables, NamespaceException, VariableContainer,
                       Role, with_roles, MultiRole, RoleGroup, MultiRoleGroup, _common_vars,
                       NamespaceModelMeta)
from task import (TaskGroup)
from config import (ConfigModel, with_searchpath, with_dependencies,
                    ConfigException, MultiTask, NullTask,
                    ConfigClassTask, with_config_options, ConfigModelMeta)
from provisioners.core import ProvisionerException, BaseProvisioner
from exec_agents.core import ExecutionAgent, ExecutionException
from exec_agents.paramiko.agent import ParamikoExecutionAgent
from config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                          CopyFileTask, ProcessCopyFileTask)
from utils import (LOG_CRIT, LOG_DEBUG, LOG_ERROR, LOG_INFO, LOG_WARN,
                   root_logger, adb, _Persistable, process_modifiers)

__version__ = "0.2.a2"


class ServiceMeta(ModelBaseMeta):
    model_ref_class = ModelReference

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(ServiceMeta, mcs).__new__(mcs, name, bases, attr_dict,
                                                 as_component=(AbstractModelingEntity,
                                                               ModelBaseMeta))
        if "infra" in attr_dict and not isinstance(attr_dict["infra"], (InfraModel, InfraModelMeta)):
            raise ActuatorException("The 'infra' attribute is not a kind of InfraModel class")
        if "namespace" in attr_dict and not isinstance(attr_dict["namespace"], (NamespaceModel, NamespaceModelMeta)):
            raise ActuatorException("The 'namespace' attribute is not a kind of NamespaceModel class")
        if "config" in attr_dict and not isinstance(attr_dict["config"], (ConfigModel, ConfigModelMeta)):
            raise ActuatorException("The 'config' attribute is not a kind of ConfigModel class")
        process_modifiers(newbie)
        _Nexus._add_model_desc("svc", newbie)
        return newbie


class Service(ModelComponent, ModelBase, VariableContainer):
    __metaclass__ = ServiceMeta
    ref_class = ModelInstanceReference
    infra = InfraModel
    namespace = NamespaceModel
    config = ConfigModel

    def __init__(self, name, infra=(("_UNNAMED_",), {}), namespace=(("_UNNAMED_",), {}),
                 config=(("_UNNAMED_",), {}), services=None, **kwargs):
        """
        Creates a new instance of a service model
        :param name: string; name of the service model
        :param infra: optional; if specified, can be either an instance of an InfraModel, or a
            list [[], {}], which contains positional and keyword arguments, used as the
            arguments that are passed to self.infra, which must be some kind of InfraModel class.
            NOTE: the first element in the list must have at least a string, used as the name for
            the infra model
        :param namespace: optional; if specified, can be either an instance of a NamespaceModel,
            or a can be a list [[], {}], which contains positional and keyword arguments, used as
            the arguments that are passed to self.namespace, which must be some kind of NamespaceModel
            class. NOTE: the first element of the list must have at least a string, used as the name
            for the namespace model
        :param config: optional; if specified, can be either an instance of a ConfigModel, or can be a
            list [[], {}], which contains  positional and keyword arguments, used as the arguments
            that are passed to self.config, which must be some kind of ConfigModel class. NOTE:
            the first element of the list must have at least a string, used as the name of the
            config model
        :param services: optional; a dict whose keys are names of services and whose values can
            be one of two things: they can be a Service instance, or they can be a sequence of
            [(), {}] parameters that can be used to instantiate a service. In this latter
            case, the Service that is "self" must have an attribute of the same name that is
            a Service model class to which these parameters will be applied to create a service
            instance. The new instance will be added as a new attribute of self with the name
            of the key in the services dict.
        """
        super(Service, self).__init__(name, **kwargs)

        self.service_names = set()
        self.services = {} if services is None else dict(services)

        if isinstance(infra, InfraModel):
            self.infra = infra
        elif isinstance(self.infra.value(), InfraModel):
            # then the model was created with an instance, not a class; clone the class and keep the clone
            clone = self.infra.clone()
            self.infra = clone
        elif isinstance(infra, collections.Sequence):
            self.infra = self.infra.value()(*infra[0], **infra[1])
        else:
            raise ActuatorException("the 'infra' arg is not a kind of InfraModel or a sequence, and the "
                                    "infra attribute is not an instance of an infra model")
        self._infra = infra

        if isinstance(namespace, NamespaceModel):
            self.namespace = namespace
        elif isinstance(self.namespace.value(), NamespaceModel):
            clone = self.namespace.clone()
            self.namespace = clone
        elif isinstance(namespace, collections.Sequence):
            self.namespace = self.namespace.value()(*namespace[0], **namespace[1])
        else:
            raise ActuatorException("the 'namespace' arg is not a kind of NamespaceModel or a sequence, and "
                                    "the namespace attribute is not an instance of a namespace model")
        self._namespace = namespace

        if isinstance(config, ConfigModel):
            self.config = config
        elif isinstance(self.config.value(), ConfigModel):
            clone = self.config.clone()
            self.config = clone
        elif isinstance(config, collections.Sequence):
            self.config = self.config.value()(*config[0], **config[1])
        else:
            raise ActuatorException("the 'config' arg is not a kind of ConfigModel or a sequence, and the "
                                    "config attribute is not an instance of a config model")
        self._config = config

        self.infra.nexus.merge_from(self.nexus)
        self.namespace.set_infra_model(self.infra.value())
        self.config.set_namespace(self.namespace.value())
        self.nexus = self.config.nexus.value()

        # now, users can do three different things with services: they can spec a
        # service class as an attribute and provide the init params to this method,
        # they can spec the class as an attribute but provide a service instance to
        # this method, or they can just supply the instance and have no attribute.
        # where we want to get to is a situation where we can do the right things
        # in both cloning and persisting/reanimating circumstances, so we need to
        # process these cases carefully. What we'd like to eventually have is the
        # services dict only have non-service values in it
        #
        # first, we'll look for class attributes that are either service classes or instances
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, (Service, ServiceMeta)):
                if isinstance(v, ServiceMeta):
                    # then we have an inner service to instantiate; look for the args or an inst
                    if k not in self.services:
                        raise ActuatorException("No init args for service '{}'".format(k))
                    args = self.services[k]
                    if isinstance(args, Service):
                        newsvc = args
                        del self.services[k]  # this is a service which we
                    elif isinstance(args, collections.Sequence):
                        newsvc = getattr(self, k).value()(*args[0], **args[1])
                    else:
                        raise ActuatorException("services entry for service '{}' isn't an instance "
                                                "of a kind of a Service or sequence of args".format(k))
                else:  # must be a Service instance; clone it
                    newsvc = v.clone()
                setattr(self, k, newsvc)
                self.service_names.add(k)
                newsvc.nexus.set_parent(self.nexus)
        # next, see if there are any services remaining the services param that we haven't
        # taken care of yet
        for k, v in self.services.items():
            if k in self.service_names:
                continue  # already covered
            if isinstance(v, Service):
                # something someone just decided to toss in here
                setattr(self, k, v)
                self.service_names.add(k)
            else:
                # ruh-roh; this shouldn't happen. if this is a sequence, it means these are
                # args for a service class, but we should have found those in the previous
                # for loop, so we have args but no class to apply them to. if they aren't
                # a sequence, then we don't know what to do with them anyway
                raise ActuatorException("services arg with key {} and value {} doesn't "
                                        "have a corresponding service model class on this "
                                        "service instance".format(k, str(v)))

        for k, v in self.__dict__.items():
            if isinstance(v, VariableContainer):
                v._set_parent(self)

        if _common_vars in self.__class__.__dict__:
            self.add_variable(*self.__class__.__dict__[_common_vars])

    def get_init_args(self):
        return ((self.name,),
                {"infra": (self._infra.value()
                           if isinstance(self._infra, ModelInstanceReference)
                           else self._infra),
                 "namespace": (self._namespace.value()
                               if isinstance(self._namespace, ModelInstanceReference)
                               else self._namespace),
                 "config": (self._config.value()
                            if isinstance(self._config, ModelInstanceReference)
                            else self._config),
                 "services": self.services})

    def finalize_reanimate(self):
        self.service_names = set(self.service_names)

    def _fix_arguments(self):
        self.namespace.compute_provisioning_for_environ(self.infra.value())
        for k in self.service_names:
            v = getattr(self, k).value()
            v.namespace.compute_provisioning_for_environ(v.infra.value())

    def _get_attrs_dict(self):
        d = super(Service, self)._get_attrs_dict()
        d.update({"name": self.name,
                  "infra": self.infra.value(),
                  "_infra": (self._infra.value()
                             if isinstance(self._infra, ModelInstanceReference)
                             else self._infra),
                  "namespace": self.namespace.value(),
                  "_namespace": (self._namespace.value()
                                 if isinstance(self._namespace, ModelInstanceReference)
                                 else self._namespace),
                  "config": self.config.value(),
                  "_config": (self._config.value()
                              if isinstance(self._config, ModelInstanceReference)
                              else self._config),
                  "service_names": list(self.service_names),
                  "services": self.services,
                  "nexus": self.nexus})
        # now add the actual services themselves
        for k in self.service_names:
            d[k] = getattr(self, k).value()
        return d

    def _find_persistables(self):
        for p in super(Service, self)._find_persistables():
            yield p

        for p in [self.infra, self._infra, self.namespace, self._namespace,
                  self.config, self._config, self.nexus]:
            if p and not isinstance(p, collections.Iterable):
                for q in p.find_persistables():
                    yield q

        for k in self.service_names:
            p = getattr(self, k).value()
            yield p
            for q in p.find_persistables():
                yield q


class ActuatorOrchestration(_Persistable):
    """
    Processes Actuator models to stand up the system being model (initiate a system).
    
    This class provides the overall controls to process a set of Actuator models,
    along with a provisioner, to stand up an instance of they system they model.
    
    When the standup is being processed, log messages are sent to stdout using
    the standard Python logging module. You can change where messages are sent
    by installing a different handler on the root logger. See the logging section
    of the Python manual for more info.
    """
    NOT_STARTED = 0
    PERFORMING_PROVISION = 1
    PERFORMING_CONFIG = 2
    PERFORMING_EXEC = 3
    COMPLETE = 4
    ABORT_PROVISION = 5
    ABORT_CONFIG = 6
    ABORT_EXEC = 7
    PERFORMING_DEPROV = 8
    ABORT_DEPROV = 9
    DEPROV_COMPLETE = 10

    def __init__(self, infra_model_inst=None, provisioner=None,
                 namespace_model_inst=None, config_model_inst=None,
                 log_level=LOG_INFO, no_delay=False, num_threads=5,
                 post_prov_pause=60, tags=None):
        """
        Create an instance of the orchestrator to operate on the supplied models/provisioner
        
        This method creates a new orchestrator, which is then ready to initiate
        the system described by the models provided to it. Some reasonableness
        checks are done on the arguments to ensure that there are no conflicting
        semantics being requested, otherwise the method simply returns an
        orchestrator ready to go.
    
        @keyword infra_model_instance: Optional; an instance of a subclass of
            L{actuator.infra.InfraModel}. If absent, all host information must be
            contained as values for host_refs in the NamespaceModel that resolve to
            either an IP address or a resolvable host name.
        @keyword provisioner: Optional; an  instance of a subclass of
            L{actuator.provisioners.core.BaseProvisioner}, such as the Openstack
            provisioner. If absent and an infra model has been supplied, then all
            resources in the model must be StaticServers, or else the resource will
            not get provisioned.
        @keyword namespace_model_inst: Optional; an instance of a subclass of
            L{actuator.namespace.NamespaceModel}. If absent, then only infra model
            processing will be possible (if one was supplied).
        @keyword config_model_instance: Optional; an instance of a subclass of
            L{actuator.config.ConfigModel}. If absent, no configuration will be carried
            out, but the namespace can be interrogated after orchestration to
            determine values from any provisioned infra
        @keyword log_level: Optional; default is LOG_INFO. One of the symbolic log
            constants from the top level actuator package. These are LOG_CRIT,
            LOG_ERROR, LOG_WARN, LOG_INFO, and LOG_DEBUG. The default supplies
            progress on each provisioning and configuration task.
        @keyword no_delay: Optional; boolean, default is False. Flags if a short,
            random delay of up to 2.5 seconds should be inserted prior to performing
            a task. May be desirable in cases where many tasks may hit a single
            host at one time, which spreads out the load of establishing ssh
            connections, helping to avoid timeouts.
        @keyword num_threads: Optional; int, default is 5. Each task, whether resource
            provisioning or configuration, is carried out in a separate thread. The
            more parallel tasks your model has the higher this number can be to have
            a positive impact on the overall task completion rate. There is no value
            in making this larger than the largest number of tasks you may have
            running in parallel.
        @keyword post_prov_pause: Optional: int, default is 60. The number of seconds
            to pause after provision is done before starting on configuration. The
            reason this is useful is because virtual/cloud systems may complete
            provisioning, but they may not have all route information propagated
            for newly provisioned hosts/floating ips right away. This pause gives
            virtual/cloud systems a chance to stabilize before starting on
            configuration tasks. If no provisioning was done (a static infra model
            or simply no infra/provisioner), then the pause is skipped.
        @keyword tags: optional list of strings. These are just text strings that
            get associated with the orchestrator instance. These are generally
            useful when the orchestrator has been persisted as the tags can be
            used to identify orchestrators with particular tag values.

        @raise ExecutionException: In the following circumstances this method
        will raise actuator.ExecutionException:
            - The value supplied for infra_model_inst is not an instance of
                L{actuator.infra.InfraModel}
            - The value supplied for provisioner is not an instance of the
                L{actuator.provisioners.core.BaseProvisioner} base class
            - The value supplied for namespace_model_inst is not an instance of
                L{actuator.namespace.NamespaceModel}
            - The value supplied for config_model_inst is not an instance of
                L{actuator.config.ConfigModel}
                
        @return: initialized orchestrator instance
        """
        if not (infra_model_inst is None or isinstance(infra_model_inst, InfraModel)):
            raise ExecutionException("infra_model_inst is no an instance of InfraModel")
        self.infra_model_inst = infra_model_inst

        if not (provisioner is None or isinstance(provisioner, BaseProvisioner)):
            raise ExecutionException("provisioner is not an instance of BaseProvisioner")
        self.provisioner = provisioner

        if not (namespace_model_inst is None or isinstance(namespace_model_inst, NamespaceModel)):
            raise ExecutionException("namespace_model_inst is not an instance of NamespaceModel")
        self.namespace_model_inst = namespace_model_inst

        if not (config_model_inst is None or isinstance(config_model_inst, ConfigModel)):
            raise ExecutionException("config_model_inst is not an instance of ConfigModel")
        self.config_model_inst = config_model_inst

        self.log_level = log_level
        root_logger.setLevel(log_level)
        self.logger = root_logger.getChild("orchestrator")
        self.post_prov_pause = post_prov_pause
        self.status = self.NOT_STARTED
        self.tags = list(tags) if tags is not None else []
        self.initiate_start_time = None
        self.initiate_end_time = None

        if self.config_model_inst is not None:
            self.config_ea = ParamikoExecutionAgent(config_model_instance=self.config_model_inst,
                                                    namespace_model_instance=self.namespace_model_inst,
                                                    num_threads=num_threads,
                                                    no_delay=no_delay,
                                                    log_level=log_level)

    def set_event_handler(self, handler):
        if self.infra_model_inst:
            self.infra_model_inst.set_event_handler(handler)
        if self.config_model_inst:
            self.config_model_inst.set_event_handler(handler)

    def _get_attrs_dict(self):
        d = super(ActuatorOrchestration, self)._get_attrs_dict()
        d.update({"log_level": self.log_level,
                  "post_prov_pause": self.post_prov_pause,
                  "status": self.status,
                  "tags": self.tags,
                  "infra_model_inst": self.infra_model_inst,
                  "namespace_model_inst": self.namespace_model_inst,
                  "config_model_inst": self.config_model_inst,
                  "logger": None,
                  "provisioner": None,
                  "initiate_start_time": self.initiate_start_time,
                  "initiate_end_time": self.initiate_end_time})
        return d

    def _find_persistables(self):
        for p in [self.infra_model_inst, self.config_model_inst, self.namespace_model_inst]:
            if p:
                for q in p.find_persistables():
                    yield q

    def finalize_reanimate(self):
        self.logger = root_logger.getChild("orchestrator")
        if not hasattr(self, "provisioner"):
            self.provisioner = None

    def set_provisioner(self, provisioner):
        if not isinstance(provisioner, BaseProvisioner):
            raise ExecutionException("provisioner is not an instance of BaseProvisioner")
        self.provisioner = provisioner

    def is_running(self):
        """
        Predicate method to call to check if the initiation is still running.
        
        @return: True is the initiation is still running, False otherwise
        """
        return self.status in [self.PERFORMING_CONFIG, self.PERFORMING_EXEC,
                               self.PERFORMING_PROVISION]

    def is_complete(self):
        """
        Predicate method to check if the run is complete with no error
        
        @return: True is the run completed successfully; False otherwise
        """
        return self.status == self.COMPLETE

    def get_errors(self):
        """
        Returns the error details of any failed tasks during initiation.
        
        @return: A list of 4-tuples: (t, et, ev, tb), where:
            t is the task that experienced the error
            et is the exception type
            ev is the exception value
            tb is the traceback from where the exception was raised
        """
        errors = []
        if self.status in [self.ABORT_CONFIG, self.ABORT_EXEC,
                           self.ABORT_PROVISION]:
            if self.status == self.ABORT_PROVISION:
                errors = self.provisioner.agent.get_aborted_tasks()
            elif self.status == self.ABORT_CONFIG:
                errors = self.config_ea.get_aborted_tasks()
        return errors

    @narrate("The orchestrator was asked to initiate the system")
    def initiate_system(self):
        """
        Stand up (initiate) the system from the models
        
        Starts the process of system initiation. By default, logs progress 
        messages to stdout. If errors are raised, then they will be logged with
        level CRITICAL.
        
        @return: True if initiation was successful, False otherwise.
        """
        self.initiate_start_time = str(datetime.datetime.utcnow())
        self.logger.info("Orchestration starting")
        did_provision = False
        if self.infra_model_inst is not None and self.provisioner is not None:
            try:
                self.status = self.PERFORMING_PROVISION
                self.logger.info("Starting provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                self.provisioner.provision_infra_model(self.infra_model_inst)
                self.logger.info("Provisioning phase complete")
                did_provision = True
            except ProvisionerException, e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> Provisioner failed "
                                     "with '%s'; failed resources shown below" % e.message)
                if self.provisioner.agent is not None:
                    for t, et, ev, tb, _ in self.provisioner.agent.get_aborted_tasks():
                        self.logger.critical("Task %s named %s id %s" %
                                             (t.__class__.__name__, t.name, str(t._id)),
                                             exc_info=(et, ev, tb))
                else:
                    self.logger.critical("No further information")
                self.logger.critical("Aborting orchestration")
                self.initiate_end_time = str(datetime.datetime.utcnow())
                return False
        elif self.infra_model_inst is not None:
            # we can at least fix up the args
            if self.namespace_model_inst:
                self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
            _ = self.infra_model_inst.refs_for_components()
        else:
            self.logger.info("No infra model or provisioner; skipping provisioning step")

        if self.config_model_inst is not None and self.namespace_model_inst is not None:
            pause = self.post_prov_pause
            if pause and did_provision:
                self.logger.info("Pausing %d secs before starting config" % pause)
                while pause:
                    time.sleep(5)
                    pause = max(pause - 5, 0)
                    self.logger.info("%d secs until config begins" % pause)
            try:
                self.status = self.PERFORMING_CONFIG
                self.logger.info("Starting config phase")
                self.config_ea.perform_config()
                self.logger.info("Config phase complete")
            except ExecutionException, e:
                self.status = self.ABORT_CONFIG
                self.logger.critical(">>> Config exec agent failed with '%s'; "
                                     "failed tasks shown below" % e.message)
                for t, et, ev, tb, story in self.config_ea.get_aborted_tasks():
                    self.logger.critical("Task %s named %s id %s" %
                                         (t.__class__.__name__, t.name, str(t._id)),
                                         exc_info=(et, ev, tb))
                    self.logger.critical("Response: %s" % ev.response
                                         if hasattr(ev, "response")
                                         else "NO RESPONSE")
                    self.logger.critical("Its story was:{}".format("\n".join(story)))
                    self.logger.critical("")
                self.logger.critical("Aborting orchestration")
                self.initiate_end_time = str(datetime.datetime.utcnow())
                return False

        self.logger.info("Orchestration complete")
        self.status = self.COMPLETE
        self.initiate_end_time = str(datetime.datetime.utcnow())
        return True

    def teardown_system(self):
        self.logger.info("Teardown orchestration starting")
        did_teardown = False
        if self.infra_model_inst is not None and self.provisioner is not None:
            try:
                self.status = self.PERFORMING_DEPROV
                self.logger.info("Starting de-provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                self.provisioner.deprovision_infra_model(self.infra_model_inst)
                self.logger.info("De-provisioning phase complete")
                did_teardown = True
            except ProvisionerException, e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> De-provisioning failed "
                                     "with '%s'; failed resources shown below" % e.message)
                if self.provisioner.agent is not None:
                    for t, et, ev, tb, _ in self.provisioner.agent.get_aborted_tasks():
                        self.logger.critical("Task %s named %s id %s" %
                                             (t.__class__.__name__, t.name, str(t._id)),
                                             exc_info=(et, ev, tb))
                else:
                    self.logger.critical("No further information")
                self.logger.critical("Aborting deprovisioning orchestration")
                return False
        else:
            self.logger.info("No infra model or provisioner; skipping de-provisioning step")
        return did_teardown
