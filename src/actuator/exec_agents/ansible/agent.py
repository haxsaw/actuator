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
import pprint

from actuator.exec_agents.core import ExecutionAgent, AbstractTaskProcessor
from actuator.config_tasks import *
from actuator.utils import capture_mapping
from actuator.namespace import _ComputableValue

from ansible.runner import Runner

_ansible_domain = "ANSIBLE_AGENT"

_class_module_map = {PingTask:"ping"}


class TaskProcessor(AbstractTaskProcessor):
    """
    Base class for all Ansible task processing classes. Establishes the protocol
    for naming modules, making argument structures, and checking results. 
    """
    def module_name(self):
        """
        Returns the name of the Ansible module to use. The derived class must
        implement this and return a suitable string with the module name in it.
        """
        raise TypeError("Derived class must implement module_name()")
    
    def make_args(self, task, hlist):
        """
        Make the generic argument structure to use with the Ansible Runner object.
        
        @param task: the task object to process
        @param hlist: A list of host names/IPs to apply the task to.
        """
        kwargs = {"host_list":hlist,
                  "environment":task.task_variables(for_env=True)
                  }
        remote_user = task.get_remote_user()
        if remote_user is not None:
            kwargs["remote_user"] = remote_user
        remote_pass = task.get_remote_pass()
        if remote_pass is not None:
            kwargs["remote_pass"] = remote_pass
        private_key_file = task.get_private_key_file()
        if private_key_file is not None:
            kwargs["private_key_file"] = private_key_file
        kwargs.update(self._make_args(task))
        kwargs["forks"] = 1
        kwargs["timeout"] = 20
        return (), kwargs
    
    def _make_args(self, task):
        """
        Supplies the module-specific arguments for the processor. Must return
        a dict of Ansible Runner keyword args that are relevant to the module
        the class is for. The derived class must override this method.
        """
        raise TypeError("derived class must implement")
    
    def result_check(self, task, result, logfile=None):
        """
        Checks the result of a Ansible Runner invocation. If there is a problem,
        raise ExecutionException with helpful data in the response.
        
        @param task: the Task that was performed
        @param result: The result dict returned from the Runner
        @param logfile: If present, a file-like object that log messages will
            be written, regardless of the log level.
        @raise ExecutionException: Raised if the result looks bad; the result
            itself will be formatted and added to the exception in the 
            exception's 'response' attribute.
        """
        host = task.get_task_host()
        if len(result["dark"]):
            cmd_msg = (result["dark"][host]["msg"]
                       if "msg" in result["dark"][host]
                       else "-NO FURTHER INFO-")
            emessage = ("Unable to reach {hosts} for {module} {task}:{cmd_msg}"
                                     .format(hosts=":".join(result["dark"].keys()),
                                             task=task.name,
                                             module=self.module_name(),
                                             cmd_msg=cmd_msg))
            if logfile:
                logfile.write("{}\n".format(emessage))
            raise ExecutionException(emessage, response=pprint.pformat(result,
                                                                       indent=1,
                                                                       width=1))
        else:
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
                raise ExecutionException(emessage, response=pprint.pformat(result,
                                                                           indent=1,
                                                                           width=1))
            elif "rc" in result["contacted"][host] and result["contacted"][host]["rc"] != 0:
                emessage = ("{module} {task} failed on {host} with the following return code: {rc}"
                                .format(module=self.module_name(),
                                        task=task.name,
                                        host=host,
                                        rc=result["contacted"][host]["rc"]))
                if logfile:
                    logfile.write("{}\n".format(emessage))
                raise ExecutionException(emessage, response=pprint.pformat(result,
                                                                           indent=1,
                                                                           width=1))


@capture_mapping(_ansible_domain, PingTask)
class PingProcessor(TaskProcessor):
    """
    Supplies the processing details for the Ansible 'ping' module.
    """
    def module_name(self):
        return "ping"

    def _make_args(self, task):
        return {"module_name":self.module_name(),
                "module_args":""}
                
            
@capture_mapping(_ansible_domain, ScriptTask)
class ScriptProcessor(TaskProcessor):
    """
    Supplies the processing details for the Ansible 'script' module.
    """
    def module_name(self):
        return "script"
    
    def _make_args(self, task):
        return {"module_name":self.module_name(),
                "complex_args":{"creates":task.creates,
                                "removes":task.removes},
                "module_args":task.free_form}
    
            
@capture_mapping(_ansible_domain, CommandTask)
class CommandProcessor(ScriptProcessor):
    """
    Supplies the processing details for the Ansible "command" module.
    """
    def module_name(self):
        return "command"
    
    def _make_args(self, task):
        args = super(CommandProcessor, self)._make_args(task)
        cmplx = args["complex_args"]
        cmplx["chdir"] = task.chdir
        cmplx["executable"] = task.executable
        cmplx["warn"] = task.warn
        return args
    
    
@capture_mapping(_ansible_domain, ShellTask)
class ShellProcessor(CommandProcessor):
    """
    Supplies the processing details for the Ansible "shell" module.
    """
    def module_name(self):
        return "shell"
    
    def _make_args(self, task):
        args = super(ShellProcessor, self)._make_args(task)
        args["module_name"] = self.module_name()
        return args
        
        
@capture_mapping(_ansible_domain, CopyFileTask)
class CopyFileProcessor(TaskProcessor):
    """
    Supplies the processing detail for the Ansible 'copy' module.
    """
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
    
    
@capture_mapping(_ansible_domain, ProcessCopyFileTask)
class ProcessCopyFileProcessor(CopyFileProcessor):
    """
    Supplies the processing detail and namespace processing capabilities
    on top of the Ansible "copy" module.
    """
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
        result = cv.expand(task.get_task_role(), raise_on_unexpanded=True)
        
        complex_args["content"] = result
        try: del complex_args["src"]
        except: pass
        return args
    

class AnsibleExecutionAgent(ExecutionAgent):
    """
    Specific execution agent to run on top of Ansible.
    """

    @classmethod
    def get_exec_domain(cls):
        return _ansible_domain

    def _perform_with_args(self, task, _, kwargs):
        runner = Runner(**kwargs)
        result = runner.run()
        return result

