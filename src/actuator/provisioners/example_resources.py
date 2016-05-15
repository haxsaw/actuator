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


class ProvisionableWithFixer(Provisionable):
    def _fix_arguments(self, provisioner=None):
        for k, v in self.__dict__.items():
            # setattr(self, k[1:], self._get_arg_value(v))
            if k.startswith("_") and hasattr(self, k[1:]):
                setattr(self, k[1:], self._get_arg_value(v))


class Network(ProvisionableWithFixer):
    def __init__(self, name, ipv6=False, cidr=None):
        super(Network, self).__init__(name)
        # self.ipv6 = ipv6
        self._ipv6 = ipv6
        self.ipv6 = None
        # self.cidr = cidr
        self._cidr = cidr
        self.cidr = None

    def _get_attrs_dict(self):
        d = super(Network, self)._get_attrs_dict()
        d.update({"ipv6": self.ipv6,
                  "cidr": self.cidr})
        return d

    def get_init_args(self):
        return (self.name,), {"ipv6": self.ipv6,
                              "cidr": self.cidr}


class Server(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Server, self).__init__(name)
        self.provisionedName = None
        # self.__dict__.update(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, None)
            setattr(self, "_{}.format(k)", v)
        self.kwargs = kwargs

    def _get_attrs_dict(self):
        d = super(Server, self)._get_attrs_dict()
        d.update({"provisionedName": self.provisionedName,
                  "kwargs": None})
        for k in self.kwargs.keys():
            d[k] = getattr(self, k)
        return d

    def get_init_args(self):
        return (self.name,), self.kwargs


class Database(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Database, self).__init__(name)
        self._provisionedName = None
        self.provisionedName = None
        self._port = None
        self.port = None
        self._adminUser = None
        self.adminUser = None
        self._adminPassword = None
        self.adminPassword = None
        for k, v in kwargs.items():
            setattr(self, k, None)
            setattr(self, "_{}.format(k)", v)
        self.kwargs = kwargs

    def _get_attrs_dict(self):
        d = super(Database, self)._get_attrs_dict()
        d.update({"provisionedName": self.provisionedName,
                  "port": self.port,
                  "adminUser": self.adminUser,
                  "adminPassword": self.adminPassword,
                  "kwargs": None})
        return d

    def get_init_args(self):
        return (self.name,), self.kwargs


class Queue(ProvisionableWithFixer):
    def __init__(self, name, **kwargs):
        super(Queue, self).__init__(name)
        self._provisionedName = None
        self.provisionedName = None
        self._qmanager = None
        self.qmanager = None
        self._host = None
        self.host = None
        self._port = None
        self.port = None
        for k, v in kwargs.items():
            setattr(self, k, None)
            setattr(self, "_{}.format(k)", v)
        self.kwargs = kwargs

    def _get_attrs_dict(self):
        d = super(Queue, self)._get_attrs_dict()
        d.update({"provisionedName": self.provisionedName,
                  "qmanager": self.qmanager,
                  "host": self.host,
                  "port": self.port,
                  "kwargs": None})
        return d

    def get_init_args(self):
        return (self.name,), self.kwargs
