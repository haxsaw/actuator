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
Created on 7 Sep 2014

@author: tom
'''
from actuator.infra import Provisionable
from actuator.modeling import ContextExpr


class ProvisionableWithFixer(Provisionable):
    def _fix_arguments(self, provisioner=None):
        for k, v in self.__dict__.items():
            setattr(self, k, self._get_arg_value(v))


class Server(ProvisionableWithFixer):
    def __init__(self, logicalName, **kwargs):
        super(Server, self).__init__(logicalName)
        self.provisionedName = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs
        
    def get_init_args(self):
        return ((self.name,), self.kwargs)
    
    
class Database(ProvisionableWithFixer):
    def __init__(self, logicalName, **kwargs):
        super(Database, self).__init__(logicalName)
        self.provisionedName = None
        self.port = None
        self.adminUser = None
        self.adminPassword = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs
        
    def get_init_args(self):
        return ((self.name,), self.kwargs)
    
    
class Queue(ProvisionableWithFixer):
    def __init__(self, logicalName, **kwargs):
        super(Queue, self).__init__(logicalName)
        self.provisionedName = None
        self.qmanager = None
        self.host = None
        self.port = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs

    def get_init_args(self):
        return((self.name,), self.kwargs)
    
        
