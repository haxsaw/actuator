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
    def __init__(self, name, command, **kwargs):
        super(RemoteExecTask, self).__init__(name, **kwargs)
        self.command = None
        self._commmand = command

    @narrate(lambda s: "...so we asked {} task {} for its init args".format(s.__class__.__name__,
                                                                            s.name))
    def get_init_args(self):
        args, kwargs = super(RemoteExecTask, self).get_init_args()
        args += (self._commmand,)
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix its arguments".format(s.__class__.__name__,
                                                                               s.name))
    def _fix_arguments(self):
        super(RemoteExecTask, self)._fix_arguments()
        self.command = self._get_arg_value(self._commmand)


class RemoteShellExecTask(RemoteExecTask):
    pass


class LocalExecTask(ExecuteTask):
    """
    Runs some command on the local host in a subprocess. A shell is not
    invoked so shell metachars are NOT expanded (use L{LocalShell} if metachar
    support is required).
    """
    def __init__(self, name, command=None, **kwargs):
        super(LocalExecTask, self).__init__(name, **kwargs)
        self._command = command
        self.command = None

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        args, kwargs = super(LocalExecTask, self).get_init_args()
        kwargs["command"] = self._command
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(LocalExecTask, self)._fix_arguments()
        self.command = self._get_arg_value(self._command)


class LocalShellExecTask(LocalExecTask):
    pass


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
           "RemoteExecTask"]
