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
    os.environ['ANSIBLE_SSH_ARGS'] = ""


from modeling import MultiComponent, MultiComponentGroup, ComponentGroup, ctxt, ActuatorException
from infra import (InfraModel, InfraException, with_resources, StaticServer,
                   ResourceGroup, MultiResource, MultiResourceGroup)
from namespace import (Var, NamespaceModel, with_variables, NamespaceException, Role,
                       with_roles, MultiRole, RoleGroup,
                       MultiRoleGroup)
from config import (ConfigModel, with_searchpath, with_dependencies,
                    ConfigException, TaskGroup, NullTask,
                    MultiTask, ConfigClassTask)
from provisioners.core import ProvisionerException
from exec_agents.core import ExecutionAgent, ExecutionException
from config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                          CopyFileTask, ProcessCopyFileTask)