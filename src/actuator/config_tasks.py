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
Created on Oct 22, 2014
'''

from actuator.config import _ConfigTask

class PingTask(_ConfigTask):
    pass


class CommandTask(_ConfigTask):
    def __init__(self, name, free_form, chdir=None, creates=None,
                 executable=None, removes=None, warn=None, **kwargs):
        super(CommandTask, self).__init__(name, **kwargs)
        self.free_form = None
        self._free_form = free_form
        self.chdir = None
        self._chdir = chdir
        self.creates = None
        self._creates = creates
        self.executable = None
        self._executable = executable
        self.removes = None
        self._removes = removes
        self.warn = None
        self._warn = warn
        
    def get_init_args(self):
        args, kwargs = super(CommandTask, self).get_init_args()
        args = args + (self._free_form,)
        kwargs["chdir"] = self._chdir
        kwargs["creates"] = self._creates
        kwargs["executable"] = self._executable
        kwargs["removes"] = self._removes
        kwargs["warn"] = self._warn
        return args, kwargs

    def fix_arguments(self):
        super(CommandTask, self).fix_arguments()
        self.free_form = self._get_arg_value(self._free_form)
        self.chdir = self._get_arg_value(self._chdir)
        self.creates = self._get_arg_value(self._creates)
        self.executable = self._get_arg_value(self._executable)
        self.removes = self._get_arg_value(self._removes)
        self.warn = self._get_arg_value(self._warn)
        