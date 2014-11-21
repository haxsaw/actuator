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

from modeling import MultiComponent, MultiComponentGroup, ComponentGroup, ctxt, ActuatorException
from infra import (InfraSpec, InfraException, with_infra_components, StaticServer)
from namespace import (Var, NamespaceSpec, with_variables, NamespaceException, Component,
                       with_components, NSMultiComponent, NSComponentGroup,
                       NSMultiComponentGroup)
from config import (ConfigSpec, with_searchpath, with_dependencies, MakeDir, Template,
                    CopyAssets, ConfigJob, ConfigException, TaskGroup, NullTask,
                    MultiTask, ConfigClassTask)
from provisioners.core import ProvisionerException
from exec_agents.core import ExecutionAgent, ExecutionException
from config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                          CopyFileTask)