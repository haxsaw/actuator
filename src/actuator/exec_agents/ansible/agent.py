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
    def module_name(self):
        raise TypeError("Derived class must implement module_name()")
    
    def make_args(self, task, hlist):
        kwargs = {"host_list":hlist,
                  "environment":{k:v.get_value(task.task_component)
                                 for k, v in task.task_component.get_visible_vars().items()}}
        kwargs.update(self._make_args(task))
        return kwargs
    
    def _make_args(self, task):
        raise TypeError("derived class must implement")
    
    def result_check(self, task, result):
        if len(result["dark"]):
            raise ExecutionException("Unable to reach {hosts} for {module} {task}"
                                     .format(hosts=":".join(result["dark"].keys()),
                                             task=task.name,
                                             module=self.module_name()))
        else:
            host = task.get_task_host()
            if "msg" in result["contacted"][host]:
                raise ExecutionException("{module} {task} failed on {host} with the following message: {msg}"
                                         .format(module=self.module_name(),
                                                 task=task.name,
                                                 msg=result["contacted"][host]["msg"],
                                                 host=host))


@capture_mapping(_agent_domain, PingTask)
class PingProcessor(TaskProcessor):
    def module_name(self):
        return "ping"

    def _make_args(self, task):
        return {"module_name":self.module_name(),
                "module_args":""}
                
            
@capture_mapping(_agent_domain, ScriptTask)
class ScriptProcessor(TaskProcessor):
    def module_name(self):
        return "script"
    
    def _make_args(self, task):
        return {"module_name":self.module_name(),
                "complex_args":{"creates":task.creates,
                                "removes":task.removes},
                "module_args":task.free_form}
    
            
@capture_mapping(_agent_domain, CommandTask)
class CommandProcessor(ScriptProcessor):
    def module_name(self):
        return "command"
    
    def _make_args(self, task):
        args = super(CommandProcessor, self)._make_args(task)
        cmplx = args["complex_args"]
        cmplx["chdir"] = task.chdir
        cmplx["executable"] = task.executable
        cmplx["warn"] = task.warn
        return args
    
    
@capture_mapping(_agent_domain, ShellTask)
class ShellProcessor(CommandProcessor):
    def module_name(self):
        return "shell"
    
    def _make_args(self, task):
        args = super(ShellProcessor, self)._make_args(task)
        args["module_name"] = self.module_name()
        return args
        
        
@capture_mapping(_agent_domain, CopyFileTask)
class CopyFileProcessor(TaskProcessor):
    def module_name(self):
        return "copy"
    
    def _make_args(self, task):
        args = {}
        args["module_name"] = self.module_name()
        args["module_args"] = ""
        args["complex_args"] = cmplx = {}
        cmplx["dest"] = task.dest
        cmplx["backup"] = task.backup
#         cmplx["follow"] = task.follow
        cmplx["force"] = task.force
        if task.content is not None: cmplx["content"] = task.content
        if task.directory_mode is not None: cmplx["directory_mode"] = task.directory_mode
        if task.group is not None: cmplx["group"] = task.group
        if task.mode is not None: cmplx["mode"] = task.mode
        if task.owner is not None: cmplx["owner"] = task.owner
        if task.selevel is not None: cmplx["selevel"] = task.selevel
        if task.serole is not None: cmplx["serole"] = task.serole
        if task.setype is not None: cmplx["setype"] = task.setype
        if task.seuser is not None: cmplx["seuser"] = task.seuser
        if task.src is not None: cmplx["src"] = task.src
        if task.validate is not None: cmplx["validate"] = task.validate
        return args
    
#     def result_check(self, task, result):
#         if len(result["dark"]):
#             raise ExecutionException("Unable to reach {hosts} for {module} {cmd}"
#                                      .format(hosts=":".join(result["dark"].keys()),
#                                              cmd=task.free_form,
#                                              module=self.module_name()))
#         else:
#             host = task.get_task_host()
#             if "msg" in result["contacted"][host]:
#                 raise ExecutionException("{module} {cmd} failed on {host} with the following message: {msg}"
#                                          .format(module=self.module_name(),
#                                                  cmd=task.free_form,
#                                                  msg=result["contacted"][host]["msg"],
#                                                  host=host))


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
