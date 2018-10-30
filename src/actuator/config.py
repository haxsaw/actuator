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

"""
Support for creating Actuator configuration models.
"""

import six
from actuator.modeling import _Nexus
from actuator.remote_task import (RemoteTask, RemoteTaskException, RemoteTaskModel,
                                  RemoteTaskModelMeta, RemoteTaskClass, with_remote_options,
                                  with_dependencies, MultiRemoteTask, with_searchpath,
                                  StructuralTask)

with_config_options = with_remote_options


class ConfigException(RemoteTaskException):
    pass


class ConfigTask(RemoteTask):
    pass


class ConfigModelMeta(RemoteTaskModelMeta):
    _allowed_task_class = ConfigTask

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(ConfigModelMeta, mcs).__new__(mcs, name, bases, attr_dict)
        _Nexus._add_model_desc("cfg", newbie)
        return newbie


class ConfigModel(six.with_metaclass(ConfigModelMeta, RemoteTaskModel)):
    pass


class ConfigClassTask(RemoteTaskClass, ConfigTask):
    def __init__(self, name, cfg_class, init_args=None, **kwargs):
        super(ConfigClassTask, self).__init__(name, cfg_class, init_args=init_args, **kwargs)


class MultiTask(MultiRemoteTask, ConfigTask):
    pass


class NullTask(ConfigTask):
    """
    Non-functional task that's mostly good for testing
    """

    def __init__(self, name, path="", **kwargs):
        super(NullTask, self).__init__(name, **kwargs)
        self.path = path

    def _perform(self, engine):
        return


__all__ = ["ConfigModel", "ConfigException", "ConfigTask", "ConfigClassTask", "MultiTask",
           "with_dependencies", "with_searchpath", "with_config_options"]
