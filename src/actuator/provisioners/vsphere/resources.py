#
# Copyright (c) 2017 Tom Carroll
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

from errator import narrate

# from pyVim import connect
# from pyVmomi import vim

from actuator.infra import Provisionable, IPAddressable


class _VSphereProvisionableInfraResource(Provisionable):
    """
    Base class for all vSphere resources that can provisioned
    """
    def __init__(self, *args, **kwargs):
        """
        Create a new resource instance. The public attribute vsid will hold the
        vSphere id of the resource once provisioned.
        """
        super(_VSphereProvisionableInfraResource, self).__init__(*args, **kwargs)
        self.vsid = None

    @narrate("...which required getting the base vsphere provisionable attribute dict")
    def _get_attrs_dict(self):
        d = super(_VSphereProvisionableInfraResource, self)._get_attrs_dict()
        d["vsid"] = str(self.vsid)
        return d

    def set_vsid(self, vsid):
        """
        set the vSphere id for the resource once it has been provisioned
        """
        self.vsid = vsid


class Datastore(_VSphereProvisionableInfraResource):
    """
    names a data store where disk images can be placed
    """
    def __init__(self, name, dspath, **kwargs):
        super(Datastore, self).__init__(name, **kwargs)
        self._dspath = dspath
        self.dspath = None
        self.vs_datastore = None

    def get_dspath(self):
        return self.dspath

    def get_vs_datastore(self):
        return self.vs_datastore

    def set_vs_datastore(self, vs_datastore):
        self.vs_datastore = vs_datastore

    @narrate(lambda s, *kw: "...where we then fixed the arguments on the datastore "
                            "{}".format(s.name))
    def _fix_arguments(self, provisioner=None):
        self.dspath = self._get_arg_value(self._dspath)

    def get_fixed_args(self):
        return (self.name, self.dspath), {}

    def get_init_args(self):
        return (self.name, self._dspath), {}

    @narrate(lambda s: "...leading to acquiring the datastore {}'s attr dict".format(s.name))
    def _get_attrs_dict(self):
        d = super(Datastore, self)._get_attrs_dict()
        d.update({"dspath": self.dspath,
                  "vs_datastore": None})
        return d


class ResourcePool(_VSphereProvisionableInfraResource):
    """
    names a pool of hosts where the guest can be added
    """
    def __init__(self, name, pool_name=None, **kwargs):
        super(ResourcePool, self).__init__(name, **kwargs)
        self._pool_name = pool_name
        self.pool_name = None
        self.resource_pool = None

    def set_resource_pool(self, resource_pool):
        self.resource_pool = resource_pool

    def get_resource_pool(self):
        return self.resource_pool

    def get_pool_name(self):
        return self.pool_name

    def set_pool_name(self, name):
        self.pool_name = name

    @narrate(lambda s, *kw: "...where we then fixed the arguments on the resource pool "
                            "{}".format(s.name))
    def _fix_arguments(self):
        self.pool_name = self._get_arg_value(self._pool_name)

    def get_fixed_args(self):
        return (self.name,), {"pool_name": self.pool_name}

    @narrate(lambda s: "...leading to acquiring the resource pool {}'s attr dict".format(s.name))
    def get_init_args(self):
        return (self.name,), {"pool_name": self._pool_name}

    def _get_attrs_dict(self):
        d = super(ResourcePool, self)._get_attrs_dict()
        self.get_fixed_args()
        d.update({"pool_name": self.pool_name,
                  "resource_pool": None})
        return d


class TemplatedServer(_VSphereProvisionableInfraResource, IPAddressable):
    def __init__(self, name, template_name, data_store, resource_pool, **kwargs):
        super(TemplatedServer, self).__init__(name, **kwargs)
        self._template_name = template_name
        self.template_name = None
        self._data_store = data_store
        self.data_store = None
        self._resource_pool = resource_pool
        self.resource_pool = None
        self.server_ip = None

    def get_resource_pool(self):
        return self.resource_pool

    def get_data_store(self):
        return self.data_store

    def get_ip(self, context=None):
        return self.server_ip

    def set_ip(self, ip):
        self.server_ip = ip

    def get_template_name(self):
        return self.template_name

    @narrate(lambda s, *kw: "...where we then fixed the arguments on the templated "
                            "server {}{}".format(s.name))
    def _fix_arguments(self, provisioner=None):
        self.template_name = self._get_arg_value(self._template_name)
        self.data_store = self._get_arg_value(self._data_store)
        self.resource_pool = self._get_arg_value(self._resource_pool)

    def get_fixed_args(self):
        return (self.name, self.template_name,
                self.data_store, self.resource_pool), {}

    def get_init_args(self):
        return (self.name, self._template_name,
                self._data_store, self._resource_pool), {}

    @narrate(lambda s: "...leading to acquiring the templated server {}'s attr dict".format(s.name))
    def _get_attrs_dict(self):
        d = super(TemplatedServer, self)._get_attrs_dict()
        self.get_fixed_args()
        d.update({"name": self.name,
                  "template_name": self.template_name,
                  "data_store": self.data_store,
                  "resource_pool": self.resource_pool,
                  "server_ip": self.server_ip})
        return d

# to be finished later
#
# class Server(_VSphereProvisionableInfraResource):
#     def __init__(self, name, template_name, memoryMB, numCPUs, files,
#                  network, **kwargs):
#         super(Server, self).__init__(name, **kwargs)
#         self._template_name = template_name
#         self.template_name = None
#         self._memoryMB = memoryMB
#         self.memoryMB = None
#         self._numCPUs = numCPUs
#         self.numCPUs = None
#         self._files = files
#         self.files = None
#         self._network = network
#         self.network = None
#         self.ipv4 = None
#         self.ipv6 = None
#
#     # def _find_persistables(self):
#     #     for p in super(Server, self)._find_persistables():
#     #         yield p
#
#     def _get_attrs_dict(self):
#         d = super(Server, self)._get_attrs_dict()
#         _, _ = self.get_fixed_args()
#         d.update({"name": self.name,
#                   "template_name": self.template_name,
#                   "memoryMB": self.memoryMB,
#                   "numCPUs": self.numCPUs,
#                   "files": self.files,
#                   "network": self.network,
#                   "ipv4": self.ipv4,
#                   "ipv6": self.ipv6})
#         return d
#
#     def _fix_arguments(self, provisioner=None):
#         self.template_name = self._get_arg_value(self._template_name)
#         self.memoryMB = self._get_arg_value(self._memoryMB)
#         self.numCPUs = self._get_arg_value(self._numCPUs)
#         self.files = self._get_arg_value(self._files)
#         self.network = self._get_arg_value(self._network)
#
#     def get_init_args(self):
#         return ((self.name, self._template_name, self._memoryMB, self._numCPUs,
#                  self._files, self._network), {})
#
#     def get_fixed_args(self):
#         return ((self.name, self.template_name, self.memoryMB, self.numCPUs,
#                  self.files, self.network), {})

__all__ = ["Datastore", "ResourcePool", "TemplatedServer"]
