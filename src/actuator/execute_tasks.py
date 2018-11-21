#
# Copyright (c) 2018 Tom Carroll
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

"""
Support for tasks in Actuator execution models.
"""

import time
from _errator import narrate

from actuator.execute import ExecuteTask


class RemoteExecTask(ExecuteTask):
    def __init__(self, name, free_form, chdir=None, **kwargs):
        super(RemoteExecTask, self).__init__(name, **kwargs)
        self.free_form = None
        self._free_form = command
        self.chdir = None
        self._chdir = chdir

    @narrate(lambda s: "...so we asked {} task {} for its init args".format(s.__class__.__name__,
                                                                            s.name))
    def get_init_args(self):
        args, kwargs = super(RemoteExecTask, self).get_init_args()
        args += (self._free_form,)
        kwargs["chdir"] = self._chdir
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix its arguments".format(s.__class__.__name__,
                                                                               s.name))
    def _fix_arguments(self):
        super(RemoteExecTask, self)._fix_arguments()
        self.free_form = self._get_arg_value(self._free_form)
        self.chdir = self._get_arg_value(self._chdir)


class RemoteShellExecTask(RemoteExecTask):
    pass


class RemoteScriptExecTask(RemoteExecTask):
    def __init__(self, name, free_form, chdir=None, proc_ns=True, executable=None, **kwargs):
        super(RemoteScriptExecTask, self).__init__(name, free_form, chdir=chdir, **kwargs)
        self.proc_ns = None
        self._proc_ns = proc_ns
        self.executable = None
        self._executable = executable

    @narrate(lambda s: "...so we asked {} task {} for its init args".format(s.__class__.__name__,
                                                                            s.name))
    def get_init_args(self):
        args, kwargs = super(RemoteScriptExecTask, self).get_init_args()
        kwargs["proc_ns"] = self._proc_ns
        kwargs["executable"] = self._executable
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix its arguments".format(s.__class__.__name__,
                                                                               s.name))
    def _fix_arguments(self):
        super(RemoteScriptExecTask, self)._fix_arguments()
        self.proc_ns = self._get_arg_value(self._proc_ns)
        self.executable = self._get_arg_value(self._executable)


class LocalExecTask(ExecuteTask):
    """
    Runs some command on the local host in a subprocess. A shell is not
    invoked so shell metachars are NOT expanded (use L{LocalShell} if metachar
    support is required).
    """
    def __init__(self, name, free_form, chdir=None, **kwargs):
        super(LocalExecTask, self).__init__(name, **kwargs)
        self.free_form = None
        self._free_form = free_form
        self.chdir = None
        self._chdir = chdir

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        args, kwargs = super(LocalExecTask, self).get_init_args()
        args += (self._free_form,)
        kwargs["chdir"] = self._chdir
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(LocalExecTask, self)._fix_arguments()
        self.free_form = self._get_arg_value(self._free_form)
        self.chdir = self._get_arg_value(self._chdir)


class LocalShellExecTask(LocalExecTask):
    pass


class LocalScriptExecTask(LocalExecTask):
    def __init__(self, name, free_form, chdir=None, proc_ns=True, **kwargs):
        super(LocalScriptExecTask, self).__init__(name, free_form, chdir=chdir, **kwargs)
        self.proc_ns = None
        self._proc_ns = proc_ns

    @narrate(lambda s: "...so we asked {} task {} for its init args".format(s.__class__.__name__,
                                                                            s.name))
    def get_init_args(self):
        args, kwargs = super(LocalScriptExecTask, self).get_init_args()
        kwargs["proc_ns"] = self._proc_ns
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix its arguments".format(s.__class__.__name__,
                                                                               s.name))
    def _fix_arguments(self):
        super(LocalScriptExecTask, self)._fix_arguments()
        self.proc_ns = self._get_arg_value(self._proc_ns)


class WaitForExecTaskTask(ExecuteTask):
    def __init__(self, name, awaited_task, **kwargs):
        super(WaitForExecTaskTask, self).__init__(name, **kwargs)
        self._awaited_task = awaited_task
        self.awaited_task = None

    def _fix_arguments(self):
        super(WaitForExecTaskTask, self)._fix_arguments()
        self.awaited_task = self._get_arg_value(self._awaited_task)

    def get_init_args(self):
        args, kwargs = super(WaitForExecTaskTask, self).get_init_args()
        args += (self._awaited_task,)
        return args, kwargs

    def _perform(self, engine):
        while not engine.stop:
            if self.awaited_task.performance_status != self.UNSTARTED:
                time.sleep(0.2)


__all__ = ["WaitForExecTaskTask", "LocalShellExecTask", "LocalExecTask", "RemoteShellExecTask",
           "RemoteExecTask", "LocalScriptExecTask", "RemoteScriptExecTask"]
