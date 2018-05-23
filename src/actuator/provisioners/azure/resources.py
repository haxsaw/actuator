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
This module contains resource classes for provisioning Openstack resources.
"""
import collections
from actuator.infra import Provisionable, IPAddressable
from actuator.provisioners.core import ProvisionerException
from actuator.utils import _Persistable


class AzureProvisionableInfraResource(Provisionable):
    pass


class AzResourceGroup(AzureProvisionableInfraResource):
    def __init__(self, name, location, **kwargs):
        super(AzResourceGroup, self).__init__(name, **kwargs)
        self.location = None
        self._location = location

    def _get_attrs_dict(self):
        d = super(AzResourceGroup, self)._get_attrs_dict()
        d["location"] = self.location
        return d

    def _fix_arguments(self, provisioner=None):
        super(AzResourceGroup, self)._fix_arguments()
        self.location = self._get_arg_value(self._location)

    def get_init_args(self):
        args, kwargs = super(AzResourceGroup, self).get_init_args()
        args += (self._location,)
        return args, kwargs


class AzNetwork(AzureProvisionableInfraResource):
    def __init__(self, name, rsrc_grp, address_prefixes, location=None, **kwargs):
        super(AzNetwork, self).__init__(name, **kwargs)
        self.rsrc_grp = None
        self._rsrc_grp = rsrc_grp
        self.location = None
        self._location = location
        self.address_prefixes = None
        self._address_prefixes = address_prefixes

    def _get_attrs_dict(self):
        d = super(AzNetwork, self)._get_attrs_dict()
        d.update({"rsrc_grp": self.rsrc_grp,
                  "location": self.location,
                  "address_prefixes": self.address_prefixes})
        return d

    def _fix_arguments(self, _=None):
        super(AzNetwork, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        self.location = self._get_arg_value(self._location)
        if self.location is None:
            self.location = self.rsrc_grp.location
        self.address_prefixes = self._get_arg_value(self._address_prefixes)

    def get_init_args(self):
        args, kwargs = super(AzNetwork, self).get_init_args()
        args += (self._rsrc_grp, self._address_prefixes)
        kwargs["location"] = self.location
        return args, kwargs


class AzSubnet(AzureProvisionableInfraResource):
    def __init__(self, name, rsrc_grp, network, address_prefix, **kwargs):
        super(AzSubnet, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._network = network
        self.network = None
        self._address_prefix = address_prefix
        self.address_prefix = None
        # returned data values
        self.subnet_id = None

    def set_subnet_id(self, sid):
        self.subnet_id = sid

    def get_subnet_id(self):
        return self.subnet_id

    def _get_attrs_dict(self):
        d = super(AzSubnet, self)._get_attrs_dict()
        d.update({"rsrc_grp": self.rsrc_grp,
                  "network": self.network,
                  "address_prefix": self.address_prefix,
                  "subnet_id": self.subnet_id})
        return d

    def _fix_arguments(self, _=None):
        super(AzSubnet, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        self.network = self._get_arg_value(self._network)
        self.address_prefix = self._get_arg_value(self._address_prefix)

    def get_init_args(self):
        args, kwargs = super(AzSubnet, self).get_init_args()
        args += (self._rsrc_grp, self._network, self._address_prefix)
        return args, kwargs


class AzNIC(AzureProvisionableInfraResource):
    def __init__(self, name, rsrc_grp, network, subnets, location=None, **kwargs):
        super(AzNIC, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._network = network
        self.network = None
        self._subnets = subnets
        self.subnets = None
        self._location = location
        self.location = None
        # returned data
        self.nic_id = None

    def set_nic_id(self, nic_id):
        self.nic_id = nic_id

    def get_nic_id(self):
        return self.nic_id

    def _get_attrs_dict(self):
        d = super(AzNIC, self)._get_attrs_dict()
        d.date({"rsrc_grp": self.rsrc_grp,
                "network": self.network,
                "subnets": self.subnets,
                "location": self.location,
                "nic_id": self.nic_id})
        return d

    def _fix_arguments(self, _=None):
        super(AzNIC, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        self.network = self._get_arg_value(self._network)
        subnets = self._get_arg_value(self._subnets)
        if not isinstance(subnets, collections.Iterable):
            ProvisionerException("The subnets argument to AzNIC isn't iterable")
        self.subnets = [self._get_arg_value(sn)
                        for sn in subnets]
        self.location = self._get_arg_value(self._location)
        if self.location is None:
            self.location = self.rsrc_grp.location

    def get_init_args(self):
        args, kwargs = super(AzNIC, self).get_init_args()
        args += (self._rsrc_grp, self._network, self._subnets)
        kwargs["location"] = self._location
        return args, kwargs


__all__ = ["AzResourceGroup", "AzNetwork", "AzSubnet", "AzNIC"]
