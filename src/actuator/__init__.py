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
#use of ControlMaster by setting the ANSIBLE_SSH_ARGS env var to "". However, you
#can allow regular processing on ANSIBLE_SSH_ARGS by supplying a non-empty
#value for the ACTUATOR_ALLOW_SSH_ARGS env var.
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


class ActuatorOrchestration(object):
    def __init__(self, infra_model_inst=None, provisioner=None,
                 namespace_model_inst=None, config_model_inst=None,
                 log_level=LOG_INFO, no_delay=False, num_threads=5,
                 post_prov_pause=60):
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
        
        if self.config_model_inst is not None:
            self.config_ea = AnsibleExecutionAgent(config_model_instance=self.config_model_inst,
                                                   namespace_model_instance=self.namespace_model_inst,
                                                   num_threads=num_threads,
                                                   no_delay=no_delay,
                                                   log_level=log_level)
                                               
    def initiate_system(self, **kwargs):
        self.logger.info("Orchestration starting")
        if self.infra_model_inst is not None:
            try:
                self.logger.info("Starting provisioning phase")
                if self.namespace_model_inst:
                    self.namespace_model_inst.set_infra_model(self.infra_model_inst)
                    self.namespace_model_inst.compute_provisioning_for_environ(self.infra_model_inst)
                _ = self.infra_model_inst.refs_for_components()
                self.provisioner.provision_infra_model(self.infra_model_inst)
                self.logger.info("Provisioning phase complete")
            except ProvisionerException, e:
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
                return
            
        pause = self.post_prov_pause
        if pause:
            self.logger.info("Pausing %d secs before starting config" % pause)
            while pause:
                time.sleep(5)
                pause = max(pause-5, 0)
                self.logger.info("%d secs until config begins" % pause)
        
        if self.config_model_inst is not None:
            try:
                self.logger.info("Starting config phase")
                self.config_ea.perform_config()
                self.logger.info("Config phase complete")
            except ExecutionException, e:
                self.logger.critical(">>> Config exec agent failed with '%s'; "
                                     "failed tasks shown below" % e.message)
                for t, et, ev, tb in self.config_ea.get_aborted_tasks():
                    self.logger.critical("Task %s named %s id %s" %
                                         (t.__class__.__name__, t.name, str(t._id)),
                                         exc_info=(et, ev, tb))
                    self.logger.critical("Response: %s" % ev.response)
                    self.logger.critical("")
                self.logger.critical("Aborting orchestration")
                return
            
        self.logger.info("Orchestration complete")
                