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

from modeling import ModelBase, ModelComponent
from task import Orable, _Dependency, Task


class ExecModel(ModelBase):
    pass


class BaseExecModelComponent(ModelComponent, Orable):
    def _or_result_class(self):
        return _Dependency


class SimpleCommand(BaseExecModelComponent):
    def __init__(self, name, role, command, **kwargs):
        super(SimpleCommand, self).__init__(name, **kwargs)
        self.role = role
        self.commmand = command

    def get_init_args(self):
        args, kwargs = super(SimpleCommand, self).get_init_args()
        args += (self.role, self.commmand)
        return args, kwargs

