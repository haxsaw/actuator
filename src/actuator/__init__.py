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

import time
from errator import narrate

from .modeling import (MultiComponent, MultiComponentGroup, ComponentGroup, ModelReference,
                       ctxt, ActuatorException, _Nexus, CallContext, ModelBaseMeta, ModelBase,
                       ModelComponent, ModelInstanceReference, AbstractModelingEntity)
from .infra import (InfraModel, InfraException, with_resources, StaticServer,
                    ResourceGroup, MultiResource, MultiResourceGroup,
                    with_infra_options, InfraModelMeta)
from .namespace import (Var, NamespaceModel, with_variables, NamespaceException, VariableContainer,
                        Role, with_roles, MultiRole, RoleGroup, MultiRoleGroup, _common_vars,
                        NamespaceModelMeta)
from .task import (TaskGroup)
from .config import (ConfigModel, with_searchpath, with_dependencies,
                     ConfigException, MultiTask, NullTask,
                     ConfigClassTask, with_config_options, ConfigModelMeta)
from .provisioners.core import (ProvisionerException, ProvisioningTaskEngine, ServiceProvisioningTaskEngine,
                                BaseProvisionerProxy)
from .exec_agents.core import ExecutionAgent, ExecutionException
from .exec_agents.paramiko.agent import ParamikoExecutionAgent
from .config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                           CopyFileTask, ProcessCopyFileTask)
from .utils import (LOG_CRIT, LOG_DEBUG, LOG_ERROR, LOG_INFO, LOG_WARN,
                    root_logger, adb, _Persistable, process_modifiers)
from actuator.service import ServiceModel

__version__ = "0.3"


class BaseProvisioningPrep(object):
    def __init__(self, orch):
        assert isinstance(orch, ActuatorOrchestration)
        self.orch = orch

    def provision_prep(self):
        """
        called prior to provisioning to ensure proper setup operations are taken
        :return: A ProvisioningTaskEngine() if there is provisioning to do, else None
        """
        return None


class ModelsProvisioningPrep(BaseProvisioningPrep):
    def provision_prep(self):
        orch = self.orch
        pte = None
        if orch.infra_model_inst is not None and orch.provisioner_proxies:
            orch.status = orch.PERFORMING_PROVISION
            orch.logger.info("Starting provisioning phase")
            if orch.namespace_model_inst:
                orch.namespace_model_inst.set_infra_model(orch.infra_model_inst)
                orch.namespace_model_inst.compute_provisioning_for_environ(orch.infra_model_inst)
            _ = orch.infra_model_inst.refs_for_components()
            pte = ProvisioningTaskEngine(orch.infra_model_inst, orch.provisioner_proxies,
                                         num_threads=orch.num_threads)
        elif orch.infra_model_inst is not None:
            # we can at least fix up the args
            if orch.namespace_model_inst:
                orch.namespace_model_inst.set_infra_model(orch.infra_model_inst)
                orch.namespace_model_inst.compute_provisioning_for_environ(orch.infra_model_inst)
            _ = orch.infra_model_inst.refs_for_components()
        else:
            orch.logger.info("No infra model or provisioner; skipping provisioning step")

        return pte


class ServiceProvisioningPrep(BaseProvisioningPrep):
    def provision_prep(self):
        orch = self.orch
        if orch.service is None:
            raise ActuatorException("There is no service to initiate")

        for svc in orch.service.all_services():
            svc.namespace.compute_provisioning_for_environ(svc.infra.value())
            _ = svc.infra.refs_for_components()

        pte = ServiceProvisioningTaskEngine(orch.service, orch.provisioner_proxies,
                                            num_threads=orch.num_threads, log_level=orch.log_level,
                                            no_delay=True)
        return pte


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

    def __init__(self, infra_model_inst=None, provisioner_proxies=(), namespace_model_inst=None,
                 config_model_inst=None, service=None, log_level=LOG_INFO, no_delay=False, num_threads=5,
                 post_prov_pause=60, client_keys=None):
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
        @keyword provisioner_proxies: Optional; a sequence of L{actuator.provisioners.core.BaseProvisionerProxy}
            derived class instances. These are the provisioners that will be used to provision
            the resources in the infra model. This list can be provided later in order to plug
            proxies in just before using an orchstrator that has be reanimated from an external store.
        @keyword namespace_model_inst: Optional; an instance of a subclass of
            L{actuator.namespace.NamespaceModel}. If absent, then only infra model
            processing will be possible (if one was supplied).
        @keyword config_model_instance: Optional; an instance of a subclass of
            L{actuator.config.ConfigModel}. If absent, no configuration will be carried
            out, but the namespace can be interrogated after orchestration to
            determine values from any provisioned infra
        @keyword service: Optional; an instance of a subclass of L{actuator.ServiceModel}.
            If provided, this service will be what the orchestrator stands up. The
            service argument and the infra_model_inst/namespace_model_inst/config_model_inst
            arguments are mutually exclusive; if a service is specified along with any
            of the other arguments, an exception is raised as their proper relationship
            can't be determined.
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
        @keyword client_keys: optional dict. Client-supplied key-value dict, the
            contents of which will be ignored by Actuator. The dict will be persisted
            along with all other data in the orchestrator, hence both keys and values
            must be objects that can be stored to/from JSON

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
        if service is not None and (infra_model_inst is not None or
                                    config_model_inst is not None or
                                    namespace_model_inst is not None):
            raise ExecutionException("You can only supply either a service or some combination of "
                                     "infra/config/namespace models, but not both")
        if service is not None and not isinstance(service, ServiceModel):
            raise ExecutionException("The service argument is not an instance of a ServiceModel class")
        self.service = service

        if not (infra_model_inst is None or isinstance(infra_model_inst, InfraModel)):
            raise ExecutionException("infra_model_inst is not an instance of InfraModel")
        self.infra_model_inst = infra_model_inst

        if any([not isinstance(pp, BaseProvisionerProxy) for pp in provisioner_proxies]):
            raise ExecutionException("one or more provisioner proxies is not of a type derived from "
                                     "BaseProvisionerProxy")
        self.provisioner_proxies = provisioner_proxies
        self.pte = None  # will hold the ProvisioningTaskEngine

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
        self.client_keys = client_keys if client_keys is not None else {}
        assert isinstance(self.client_keys, dict), "client_keys is not a dict"
        self.initiate_start_time = None
        self.initiate_end_time = None
        self.num_threads = num_threads

        if self.config_model_inst is not None:
            self.config_ea = ParamikoExecutionAgent(config_model_instance=self.config_model_inst,
                                                    namespace_model_instance=self.namespace_model_inst,
                                                    num_threads=self.num_threads,
                                                    no_delay=no_delay,
                                                    log_level=log_level)

    def set_provisioner_proxies(self, proxies):
        if any([not isinstance(pp, BaseProvisionerProxy) for pp in proxies]):
            raise ExecutionException("one or more of the proxies is not of a type derived from "
                                     "BaseProvisionerProxy")
        self.provisioner_proxies = proxies

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
                  "client_keys": self.client_keys,
                  "infra_model_inst": self.infra_model_inst,
                  "namespace_model_inst": self.namespace_model_inst,
                  "config_model_inst": self.config_model_inst,
                  "service": self.service,
                  "logger": None,
                  "provisioner": None,
                  "initiate_start_time": self.initiate_start_time,
                  "initiate_end_time": self.initiate_end_time,
                  "provisioner_proxies": (),
                  "num_threads": self.num_threads,
                  "pte": None})
        return d

    def _find_persistables(self):
        for p in [self.infra_model_inst, self.config_model_inst,
                  self.namespace_model_inst, self.service]:
            if p:
                for q in p.find_persistables():
                    yield q

    def finalize_reanimate(self):
        self.logger = root_logger.getChild("orchestrator")
        if not hasattr(self, "provisioner_proxies"):
            self.provisioner_proxies = ()

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

        # start with the infrastructure
        if self.pte is None:   # we want to be sure to re-use existing task engines as they have important state
            if self.service is not None:
                prepper = ServiceProvisioningPrep(self)
            else:
                prepper = ModelsProvisioningPrep(self)
            self.pte = prepper.provision_prep()
        if self.pte:
            try:
                self.logger.info("Starting provisioning phase")
                self.pte.perform_tasks()
                self.logger.info("Provisioning phase complete")
                did_provision = True
            except ProvisionerException as e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> Provisioner failed "
                                     "with '%s'; failed resources shown below" % str(e))
                if self.pte is not None:
                    for t, et, ev, tb, _ in self.pte.get_aborted_tasks():
                        self.logger.critical("Task %s named %s id %s" %
                                             (t.__class__.__name__, t.name, str(t._id)),
                                             exc_info=(et, ev, tb))
                else:
                    self.logger.critical("No further information")
                self.logger.critical("Aborting orchestration")
                self.initiate_end_time = str(datetime.datetime.utcnow())
                return False

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
            except ExecutionException as e:
                self.status = self.ABORT_CONFIG
                self.logger.critical(">>> Config exec agent failed with '%s'; "
                                     "failed tasks shown below" % str(e))
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
        # if self.infra_model_inst is not None and self.pte is not None:
        if self.infra_model_inst is not None:
            if self.pte is None:
                self.pte = ProvisioningTaskEngine(self.infra_model_inst, self.provisioner_proxies,
                                                  num_threads=self.num_threads)
            try:
                self.status = self.PERFORMING_DEPROV
                self.logger.info("Starting de-provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                self.pte.perform_reverses()
                self.logger.info("De-provisioning phase complete")
                did_teardown = True
            except ProvisionerException as e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> De-provisioning failed "
                                     "with '%s'; failed resources shown below" % str(e))
                if self.pte is not None:
                    for t, et, ev, tb, _ in self.pte.get_aborted_tasks():
                        self.logger.critical("Task %s named %s id %s" %
                                             (t.__class__.__name__, t.name, str(t._id)),
                                             exc_info=(et, ev, tb))
                else:
                    self.logger.critical("No further information")
                self.logger.critical("Aborting deprovisioning orchestration")
                return False
        else:
            self.logger.info("No infra model or provisioner; skipping de-provisioning step")
            did_teardown = True
        return did_teardown
