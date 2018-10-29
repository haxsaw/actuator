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

import six
from actuator.modeling import _Nexus
from actuator.remote_task import (RemoteTask, RemoteTaskException, RemoteTaskModel,
                                  RemoteTaskModelMeta, RemoteTaskClass, with_remote_options,
                                  with_dependencies, MultiTask)

with_execute_options = with_remote_options


class ExecuteException(RemoteTaskException):
    pass


class ExecuteTask(RemoteTask):
    pass


class ExecuteModelMeta(RemoteTaskModelMeta):
    _allowed_task_class = ExecuteTask

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(ExecuteModelMeta, mcs).__new__(mcs, name, bases, attr_dict)
        _Nexus._add_model_desc("exe", newbie)
        return newbie


class ExecuteModel(six.with_metaclass(ExecuteModelMeta, RemoteTaskModel)):
    pass


class ExecuteTaskClass(RemoteTaskClass):
    pass


class SimpleCommandTask(ExecuteTask):
    def __init__(self, name, role, command, **kwargs):
        super(SimpleCommandTask, self).__init__(name, **kwargs)
        self.role = role
        self.commmand = command

    def get_init_args(self):
        args, kwargs = super(SimpleCommandTask, self).get_init_args()
        args += (self.role, self.commmand)
        return args, kwargs


__all__ = ["ExecuteModel", "with_dependencies", "with_execute_options", "ExecuteException",
           "ExecuteTaskClass", "SimpleCommandTask", "RemoteTaskException", "MultiTask"]
