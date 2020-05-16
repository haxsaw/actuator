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
Support for creating Actuator execution models.
"""

import six

from actuator.modeling import _Nexus
from actuator.remote_task import (RemoteTask, RemoteTaskException, RemoteTaskModel,
                                  RemoteTaskModelMeta, RemoteTaskClass, with_remote_options,
                                  with_dependencies, MultiRemoteTask)

with_execute_options = with_remote_options


class ExecuteException(RemoteTaskException):
    pass


class ExecuteTask(RemoteTask):
    """
    .. note:: ExecuteTask is derived from :py:class:`actuator.remote_task.RemoteTask`; see the documentation
        for that class for details. This class is just a veneer over that class.
    """
    pass


class ExecuteModelMeta(RemoteTaskModelMeta):
    _allowed_task_class = ExecuteTask

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(ExecuteModelMeta, mcs).__new__(mcs, name, bases, attr_dict)
        _Nexus._add_model_desc("exe", newbie)
        return newbie


class ExecuteModel(six.with_metaclass(ExecuteModelMeta, RemoteTaskModel)):
    """
    .. note:: ExecuteModel is derived from :py:class:`actuator.remote_task.RemoteTaskModel`; see
        the documentation for that class for details. This class is just a veneer over that class.
    """
    pass


class ExecuteClassTask(RemoteTaskClass, ExecuteTask):
    """
    .. note:: ExecuteClassTask is derived from :py:class:`actuator.remote_task.RemoteTaskClass`; see the documentation
        for that class for details. This class is just a veneer over that class
    """
    pass


class MultiTask(MultiRemoteTask, ExecuteTask):
    """
    .. note:: MultiTask is derived from :py:class:`actuator.remote_Task.MultiRemoteTask`; see the documentation
        for that class for details. This class is just a veneer over that class.

    """
    pass


__all__ = ["ExecuteModel", "with_dependencies", "with_execute_options", "ExecuteException",
           "ExecuteClassTask", "MultiTask", "ExecuteTask"]
