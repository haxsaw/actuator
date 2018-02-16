from actuator.provisioners.altcore import ProvisioningTaskEngine
from actuator.utils import _Persistable, LOG_INFO, root_logger
from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from errator import narrate
import datetime
import time


class ExecutionException(Exception):
    pass


class ActuatorOrchestration(_Persistable):
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
        self.infra_model_inst = infra_model_inst
        self.provisioner_proxies = provisioner_proxies
        self.pte = None
        self.namespace_model_inst = namespace_model_inst
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

    def set_provisioning_proxies(self, proxies):
        """
        Set a sequence
        :param proxies:
        :return:
        """
        self.provisioner_proxies = proxies

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
        if self.infra_model_inst is not None and self.provisioner_proxies is not None:
            try:
                self.status = self.PERFORMING_PROVISION
                self.logger.info("Starting provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                if self.pte is None:
                    self.pte = ProvisioningTaskEngine(self.infra_model_inst, self.provisioner_proxies)
                self.pte.perform_tasks()
                # self.provisioner.provision_infra_model(self.infra_model_inst)
                self.logger.info("Provisioning phase complete")
                did_provision = True
            except Exception, e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> Provisioner failed "
                                     "with '%s'; failed resources shown below" % e.message)
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
        if self.infra_model_inst is not None and self.pte is not None:
            try:
                self.status = self.PERFORMING_DEPROV
                self.logger.info("Starting de-provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                # we won't be persisting the task engine, so if teardown is being called
                # as a result of a reanimate, we'll need to re-build the pte
                if self.pte is None:
                    self.pte = ProvisioningTaskEngine(self.infra_model_inst, self.provisioner_proxies)
                self.pte.perform_reverses()
                self.logger.info("De-provisioning phase complete")
                did_teardown = True
            except Exception, e:
                self.status = self.ABORT_PROVISION
                self.logger.critical(">>> De-provisioning failed "
                                     "with '%s'; failed resources shown below" % e.message)
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
        return did_teardown
