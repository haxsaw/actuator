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

import os.path
import json

from actuator.exec_agents.core import ExecutionAgent
from actuator.config import StructuralTask
from actuator.config_tasks import *
from actuator.utils import capture_mapping, get_mapper
from actuator.namespace import _ComputableValue

from ansible.runner import Runner

_agent_domain = "ANSIBLE_AGENT"

_class_module_map = {PingTask:"ping"}


class TaskProcessor(object):
    def module_name(self):
        raise TypeError("Derived class must implement module_name()")
    
    def make_args(self, task, hlist):
        kwargs = {"host_list":hlist,
                  "environment":task.task_variables()}
        kwargs.update(self._make_args(task))
        return kwargs
    
    def _make_args(self, task):
        raise TypeError("derived class must implement")
    
    def result_check(self, task, result, logfile=None):
        if len(result["dark"]):
            emessage = ("Unable to reach {hosts} for {module} {task}"
                                     .format(hosts=":".join(result["dark"].keys()),
                                             task=task.name,
                                             module=self.module_name()))
            if logfile:
                logfile.write("{}\n".format(emessage))
            raise ExecutionException(emessage)
        else:
            host = task.get_task_host()
            if "msg" in result["contacted"][host]:
                emessage = ("{module} {task} failed on {host} with the following emessage: {msg}"
                                .format(module=self.module_name(),
                                        task=task.name,
                                        msg=(result["contacted"][host]["msg"]
                                             if result["contacted"][host]["msg"]
                                             else "NO MESSAGE"),
                                        host=host))
                if logfile:
                    logfile.write("{}\n".format(emessage))
                raise ExecutionException(emessage)
            elif "rc" in result["contacted"][host] and result["contacted"][host]["rc"] != 0:
                emessage = ("{module} {task} failed on {host} with the following return code: {rc}"
                                .format(module=self.module_name(),
                                        task=task.name,
                                        host=host,
                                        rc=result["contacted"][host]["rc"]))
                if logfile:
                    logfile.write("{}\n".format(emessage))
                raise ExecutionException(emessage)


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
    
    
@capture_mapping(_agent_domain, ProcessCopyFileTask)
class ProcessCopyFileProcessor(CopyFileProcessor):
    def _make_args(self, task):
        args = super(ProcessCopyFileProcessor, self)._make_args(task)
        complex_args = args["complex_args"]
        if "src" in complex_args:
            if not os.path.exists(complex_args["src"]):
                raise ExecutionException("Can't find the file {}".format(complex_args["src"]))
            content = file(complex_args["src"], "r").read()
        else:
            content = complex_args["content"]

        cv = _ComputableValue(content)
        result = cv.expand(task.get_task_component(), raise_on_unexpanded=True)
        
        complex_args["content"] = result
        try: del complex_args["src"]
        except: pass
        return args
    

class AnsibleExecutionAgent(ExecutionAgent):
    def _perform_task(self, task, logfile=None):
        task.fix_arguments()
        if isinstance(task, StructuralTask):
            task.perform()
        else:
            cmapper = get_mapper(_agent_domain)
            processor = cmapper[task.__class__]()
#             task.fix_arguments()
            task.task_component.fix_arguments()
            task_host = task.get_task_host()
            if task_host is not None:
                msg = "Task {} being run on {}".format(task.name, task_host)
                if logfile:
                    logfile.write("{}\n".format(msg))
#                 print msg
                hlist = [task_host]
            else:
                raise ExecutionException("We need a default execution host")
            kwargs = processor.make_args(task, hlist)
            kwargs["forks"] = 1
            if logfile:
                logfile.write(">>>Params:\n{}\n".format(json.dumps(kwargs)))
            
#             msg = json.dumps(kwargs)
#             args = [sys.executable,
#                     json_runner.__file__]
#             proc = subprocess32.Popen(args, stdin=subprocess32.PIPE,
#                                       stdout=subprocess32.PIPE,
#                                       stderr=subprocess32.PIPE)
#             proc.stdin.write(msg)
#             proc.stdin.flush()
#             proc.stdin.close()
#             reply = proc.stdout.read()
#             result = json.loads(reply)
            
            runner = Runner(**kwargs)
            result = runner.run()
            if logfile:
                logfile.write(">>>Result:\n{}\n".format(json.dumps(result)))
            processor.result_check(task, result, logfile=logfile)
        return
