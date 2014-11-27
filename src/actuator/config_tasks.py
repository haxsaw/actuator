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
from nose.util import src
from actuator.exec_agents.core import ExecutionException

'''
Created on Oct 22, 2014
'''

from actuator.config import _ConfigTask, ConfigException

class PingTask(_ConfigTask):
    pass


class ScriptTask(_ConfigTask):
    def __init__(self, name, free_form, creates=None, removes=None, **kwargs):
        super(ScriptTask, self).__init__(name, **kwargs)
        self.free_form = None
        self._free_form = free_form
        self.creates = None
        self._creates = creates
        self.removes = None
        self._removes = removes
        
    def get_init_args(self):
        args, kwargs = super(ScriptTask, self).get_init_args()
        args = args + (self._free_form,)
        kwargs["creates"] = self._creates
        kwargs["removes"] = self._removes
        return args, kwargs

    def _fix_arguments(self):
        super(ScriptTask, self)._fix_arguments()
        self.free_form = self._get_arg_value(self._free_form)
        self.creates = self._get_arg_value(self._creates)
        self.removes = self._get_arg_value(self._removes)
        

class CommandTask(ScriptTask):
    def __init__(self, name, free_form, chdir=None, creates=None,
                 executable=None, removes=None, warn=None, **kwargs):
        super(CommandTask, self).__init__(name, free_form, creates=creates,
                                          removes=removes, **kwargs)
        self.chdir = None
        self._chdir = chdir
        self.executable = None
        self._executable = executable
        self.warn = None
        self._warn = warn
        
    def get_init_args(self):
        args, kwargs = super(CommandTask, self).get_init_args()
        kwargs["chdir"] = self._chdir
        kwargs["executable"] = self._executable
        kwargs["warn"] = self._warn
        return args, kwargs

    def _fix_arguments(self):
        super(CommandTask, self)._fix_arguments()
        self.chdir = self._get_arg_value(self._chdir)
        self.executable = self._get_arg_value(self._executable)
        self.warn = self._get_arg_value(self._warn)


class ShellTask(CommandTask):
    pass


class CopyFileTask(_ConfigTask):
    def __init__(self, name, dest, backup=False, content=None,
                 directory_mode=None, follow=False, force=True, group=None,
                 mode=None, owner=None, selevel="s0", serole=None, setype=None,
                 seuser=None, src=None, validate=None,
                 **kwargs):
        super(CopyFileTask, self).__init__(name, **kwargs)
        if content is None and src is None:
            raise ConfigException("Either 'content' or 'src' must be provided")
        self.dest = None
        self._dest = dest
        self.backup = None
        self._backup = backup
        self.content = None
        self._content = content
        self.directory_mode = None
        self._directory_mode = directory_mode
        self.follow = None
        self._follow = follow
        self.force = None
        self._force = force
        self.group = None
        self._group = group
        self.mode = None
        self._mode = mode
        self.owner = None
        self._owner = owner
        self.selevel = None
        self._selevel = selevel
        self.serole = None
        self._serole = serole
        self.setype = None
        self._setype = setype
        self.seuser = None
        self._seuser = seuser
        self.src = None
        self._src = src
        self.validate = None
        self._validate = validate
        
    def get_init_args(self):
        args, kwargs = super(CopyFileTask, self).get_init_args()
        args = args + (self._dest,)
        kwargs["backup"] = self._backup
        kwargs["content"] = self._content
        kwargs["directory_mode"] = self._directory_mode
        kwargs["follow"] = self._follow
        kwargs["force"] = self._force
        kwargs["group"] = self._group
        kwargs["mode"] = self._mode
        kwargs["owner"] = self._owner
        kwargs["selevel"] = self._selevel
        kwargs["serole"] = self._serole
        kwargs["setype"] = self._setype
        kwargs["seuser"] = self._seuser
        kwargs["src"] = self._src
        kwargs["validate"] = self._validate
        return args, kwargs
    
    def _fix_arguments(self):
        super(CopyFileTask, self)._fix_arguments()
        self.dest = self._get_arg_value(self._dest)
        self.backup = self._get_arg_value(self._backup)
        self.backup = "yes" if self.backup else "no"
        self.content = self._get_arg_value(self._content)
        self.directory_mode = self._get_arg_value(self._directory_mode)
        self.follow = self._get_arg_value(self._follow)
        self.follow = "yes" if self.follow else "no"
        self.force = self._get_arg_value(self._force)
        self.force = "yes" if self.force else "no"
        self.group = self._get_arg_value(self._group)
        self.mode = self._get_arg_value(self._mode)
        self.owner = self._get_arg_value(self._owner)
        self.selevel = self._get_arg_value(self._selevel)
        self.serole = self._get_arg_value(self._serole)
        self.setype = self._get_arg_value(self._setype)
        self.seuser = self._get_arg_value(self._seuser)
        self.src = self._get_arg_value(self._src)
        self.validate = self._get_arg_value(self._validate)
    
    
class ProcessCopyFileTask(CopyFileTask):
    def __init__(self, *args, **kwargs):
        if "src" not in kwargs and "content" not in kwargs:
            raise ExecutionException("ProcessCopoyFileTask must be given either "
                                     "the 'src' or 'content' keyword arguments")
        super(ProcessCopyFileTask, self).__init__(*args, **kwargs)

