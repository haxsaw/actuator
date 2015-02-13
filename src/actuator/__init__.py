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

NOTE: be sure to import this package before importing any Ansible modules.
Actuator requires Python 3.2 semantics for the subprocess module in order for
Ansible to work the way it needs to, and by importing Actuator first, it can
patch in subprocess32 (a drop-in replacement for subprocess) to be used instead
of subprocess, ensuring that Ansible behaves properly.
"""

import sys
#patch in the subprocess32 module so that it gets picked up
#instead of the 2.7.x subprocess module
import subprocess
import subprocess32
subprocess32._args_from_interpreter_flags = subprocess._args_from_interpreter_flags
sys.modules["subprocess"] = subprocess32
del subprocess

import os
#The use of ssh's ControlMaster option seems to be fairly unstable, as least
#with current Ubuntu-based distros. Hence, by default Actuator disables Ansible's
#use of ControlMaster by setting the ANSIBLE_SSH_ARGS env var to a value of it's
#own. However, you can allow regular processing on ANSIBLE_SSH_ARGS by supplying
#a non-empty value for the ACTUATOR_ALLOW_SSH_ARGS env var, but you need to
#include the values shown below for ANSIBLE_SSH_ARGS to ensure that Actuator
#will be able to 1) log into new hosts without being asked "are you sure?" by
#ssh, and 2) not actually store those new hosts into the known_hosts file
if not os.environ.get("ACTUATOR_ALLOW_SSH_ARGS"):
    os.environ['ANSIBLE_SSH_ARGS'] = "-oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null"
import traceback
import time


from modeling import (MultiComponent, MultiComponentGroup, ComponentGroup,
                      ctxt, ActuatorException)
from infra import (InfraModel, InfraException, with_resources, StaticServer,
                   ResourceGroup, MultiResource, MultiResourceGroup)
from namespace import (Var, NamespaceModel, with_variables, NamespaceException,
                       Role, with_roles, MultiRole, RoleGroup, MultiRoleGroup)
from config import (ConfigModel, with_searchpath, with_dependencies,
                    ConfigException, TaskGroup, NullTask, MultiTask,
                    ConfigClassTask, with_config_options)
from provisioners.core import ProvisionerException, BaseProvisioner
from exec_agents.core import ExecutionAgent, ExecutionException
from exec_agents.ansible.agent import AnsibleExecutionAgent
from config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                          CopyFileTask, ProcessCopyFileTask)
from utils import (LOG_CRIT, LOG_DEBUG, LOG_ERROR, LOG_INFO, LOG_WARN, root_logger)


__version__ = "0.2.a1"

class ActuatorOrchestration(object):
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
    def __init__(self, infra_model_inst=None, provisioner=None,
                 namespace_model_inst=None, config_model_inst=None,
                 log_level=LOG_INFO, no_delay=False, num_threads=5,
                 post_prov_pause=60):
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
        
        if self.config_model_inst is not None:
            self.config_ea = AnsibleExecutionAgent(config_model_instance=self.config_model_inst,
                                                   namespace_model_instance=self.namespace_model_inst,
                                                   num_threads=num_threads,
                                                   no_delay=no_delay,
                                                   log_level=log_level)
            
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
                                               
    def initiate_system(self):
        """
        Stand up (initiate) the system from the models
        
        Starts the process of system initiation. By default, logs progress 
        messages to stdout. If errors are raised, then they will be logged with
        level CRITICAL.
        
        @return: True if initiation was successful, False otherwise.
        """
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
                    for t, et, ev, tb in self.provisioner.agent.get_aborted_tasks():
                        self.logger.critical("Task %s named %s id %s" %
                                             (t.__class__.__name__, t.name, str(t._id)),
                                             exc_info=(et, ev, tb))
                else:
                    self.logger.critical("No further information")
                self.logger.critical("Aborting orchestration")
                return False
        else:
            self.logger.info("No infra model or provisioner; skipping provisioning step")
            
        if self.config_model_inst is not None and self.namespace_model_inst is not None:
            pause = self.post_prov_pause
            if pause and did_provision:
                self.logger.info("Pausing %d secs before starting config" % pause)
                while pause:
                    time.sleep(5)
                    pause = max(pause-5, 0)
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
                for t, et, ev, tb in self.config_ea.get_aborted_tasks():
                    self.logger.critical("Task %s named %s id %s" %
                                         (t.__class__.__name__, t.name, str(t._id)),
                                         exc_info=(et, ev, tb))
                    self.logger.critical("Response: %s" % ev.response)
                    self.logger.critical("")
                self.logger.critical("Aborting orchestration")
                return False
            
        self.logger.info("Orchestration complete")
        self.status = self.COMPLETE
        return True
    
                