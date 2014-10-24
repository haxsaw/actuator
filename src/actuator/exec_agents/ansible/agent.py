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

from actuator.exec_agents.core import ExecutionAgent, ExecutionException
from actuator.config_tasks import *
from actuator.utils import capture_mapping, get_mapper

_agent_domain = "ANSIBLE_AGENT"

_class_module_map = {PingTask:"ping"}


class TaskProcessor(object):
    def make_args(self, task, hlist):
        kwargs = {"host_list":hlist}
        kwargs.update(self._make_args(task))
        return kwargs
    
    def _make_args(self, task):
        raise TypeError("derived class must implement")
    
    def result_check(self, task, result):
        raise TypeError("derived class must implement")


@capture_mapping(_agent_domain, PingTask)
class PingProcessor(TaskProcessor):
    def _make_args(self, task):
        return {"module_name":"ping",
                "module_args":""}
    
    def result_check(self, task, result):
        if len(result['dark']):
            raise ExecutionException("Task {task} couldn't reach hosts at {hosts}"
                                     .format(task=task.name,
                                             hosts=":".join(result["dark"].keys())))
            
@capture_mapping(_agent_domain, CommandTask)
class CommandProcessor(TaskProcessor):
    args_to_use = set(["free_form", "chdir", "creates", "executable", "removes",
                       "warn"])
    def _make_args(self, task):
        return {"complex_args":{"chdir":task.chdir,
                                "creates":task.creates,
                                "executable":task.executable,
                                "removes":task.removes,
                                "warn":task.warn},
                "module_args":task.free_form}
    
    def result_check(self, task, result):
        if len(result["dark"]):
            raise ExecutionException("Unable to reach {hosts} for command {cmd}"
                                     .format(hosts=":".join(result["dark"].keys()),
                                             cmd=task.free_form))
        else:
            host = task.get_task_host()
            if "msg" in result["contacted"][host]:
                raise ExecutionException("Command {cmd} failed on {host} with the following message: {msg}"
                                         .format(cmd=task.free_form,
                                                 msg=result["contacted"][host]["msg"],
                                                 host=host))


class AnsibleExecutionAgent(ExecutionAgent):
    def _perform_task(self, task):
        cmapper = get_mapper(_agent_domain)
        processor = cmapper[task.__class__]()
        task.fix_arguments()
        task.task_component.fix_arguments()
        task_host = task.get_task_host()
        if task_host is not None:
            hlist = [task_host]
        else:
            raise ExecutionException("We need a default execution host")
        kwargs = processor.make_args(task, hlist)
        runner = Runner(**kwargs)
        result = runner.run()
        processor.result_check(task, result)
        return
