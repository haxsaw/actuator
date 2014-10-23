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

'''
Created on Oct 21, 2014
'''
from ansible.runner import Runner

from actuator.exec_agents.core import ExecutionAgent
from actuator.config_tasks import *


_class_module_map = {PingTask:"ping"}


class AnsibleExecutionAgent(ExecutionAgent):
    def _perform_task(self, task):
        modname = _class_module_map.get(task.__class__)
        task.fix_arguments()
        task.task_component.fix_arguments()
        hlist = [task.task_component.host_ref
                 if isinstance(task.task_component.host_ref, basestring)
                 else task.task_component.host_ref.value()]
        runner = Runner(module_name=modname,
                        host_list=hlist,
                        module_args='')
        result = runner.run()
        return
