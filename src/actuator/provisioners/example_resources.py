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
Example classes mainly used in testing.
'''
from actuator.infra import Provisionable
from actuator.modeling import ContextExpr


class ProvisionableWithFixer(Provisionable):
    def _fix_arguments(self, provisioner=None):
        for k, v in self.__dict__.items():
            setattr(self, k, self._get_arg_value(v))


class Server(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Server, self).__init__(name)
        self.provisionedName = None
        self.__dict__.update(kwargs)
        self.kwargs = kwargs
        
    def _get_attrs_dict(self):
        d = super(Server, self)._get_attrs_dict()
        d.update( {"provisionedName":self.provisionedName,
                   "kwargs":None} )
        for k in self.kwargs.keys():
            d[k] = getattr(self, k)
        return d
        
    def get_init_args(self):
        return ((self.name,), self.kwargs)
    
    
class Database(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Database, self).__init__(name)
        self.provisionedName = None
        self.port = None
        self.adminUser = None
        self.adminPassword = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs
        
    def get_init_args(self):
        return ((self.name,), self.kwargs)
    
    
class Queue(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Queue, self).__init__(name)
        self.provisionedName = None
        self.qmanager = None
        self.host = None
        self.port = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs

    def get_init_args(self):
        return((self.name,), self.kwargs)
    
        
