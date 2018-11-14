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
from actuator.infra import Provisionable
from actuator.utils import IPAddressable
from actuator.provisioners.core import ProvisionerException


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
    def __init__(self, name, rsrc_grp, network, subnets, public_ip=None, location=None, **kwargs):
        super(AzNIC, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._network = network
        self.network = None
        self._subnets = subnets
        self.subnets = None
        # @FIXME: public_ip may need to be a list of the same length as subnets. if there
        # wind up being subnets that don't need a public IP, then the list should contain
        # a None in the same position as that subnet. This could be tricky from a declarative
        # perspective
        self._public_ip = public_ip
        self.public_ip = None
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
        d.update({"rsrc_grp": self.rsrc_grp,
                  "network": self.network,
                  "subnets": self.subnets,
                  "public_ip": self.public_ip,
                  "location": self.location,
                  "nic_id": self.nic_id})
        return d

    def _fix_arguments(self, _=None):
        super(AzNIC, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        self.network = self._get_arg_value(self._network)
        subnets = self._get_arg_value(self._subnets)
        if not isinstance(subnets, collections.Iterable):
            raise ProvisionerException("The subnets argument to AzNIC isn't iterable")
        self.subnets = [self._get_arg_value(sn)
                        for sn in subnets]
        self.location = self._get_arg_value(self._location)
        self.public_ip = self._get_arg_value(self._public_ip)
        if self.location is None:
            self.location = self.rsrc_grp.location

    def get_init_args(self):
        args, kwargs = super(AzNIC, self).get_init_args()
        args += (self._rsrc_grp, self._network, self._subnets)
        kwargs["location"] = self._location
        kwargs["public_ip"] = self._public_ip
        return args, kwargs


class AzServer(AzureProvisionableInfraResource, IPAddressable):
    def __init__(self, name, rsrc_grp, nics, publisher=None, offer=None, sku=None, version=None,
                 vm_size=None, admin_user=None, admin_password=None, location=None,
                 pub_key_data=None, **kwargs):
        super(AzServer, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._nics = nics
        self.nics = None
        self._publisher = publisher
        self.publisher = None
        self._offer = offer
        self.offer = None
        self._sku = sku
        self.sku = None
        self._version = version
        self.version = None
        self._vm_size = vm_size
        self.vm_size = None
        self._admin_user = admin_user
        self.admin_user = None
        self._admin_password = admin_password
        self.admin_password = None
        self._location = location
        self.location = None
        self._pub_key_data = pub_key_data
        self.pub_key_data = None
        # pulled back from Azure
        self.ip = None

    def set_ip(self, ip):
        self.ip = ip

    def get_ip(self, context=None):
        return self.ip

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip) if self.ip is not None else None

    def _get_attrs_dict(self):
        d = super(AzServer, self)._get_attrs_dict()
        d.update({"rsrc_grp": self.rsrc_grp,
                  "nics": self.nics,
                  "publisher": self.publisher,
                  "offer": self.offer,
                  "sku": self.sku,
                  "version": self.version,
                  "vm_size": self.vm_size,
                  "admin_user": self.admin_user,
                  "admin_password": self.admin_password,
                  "location": self.location,
                  "pub_key_data": self.pub_key_data,
                  "ip": self.ip})
        return d

    def _fix_arguments(self, _=None):
        super(AzServer, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        nics = self._get_arg_value(self._nics)
        if not isinstance(nics, collections.Iterable):
            raise ProvisionerException("The nics argument did not resolve into an iterable of AzNIC objects")
        self.nics = [self._get_arg_value(nic)
                     for nic in nics]
        self.publisher = self._get_arg_value(self._publisher)
        self.offer = self._get_arg_value(self._offer)
        self.sku = self._get_arg_value(self._sku)
        self.version = self._get_arg_value(self._version)
        self.vm_size = self._get_arg_value(self._vm_size)
        self.admin_user = self._get_arg_value(self._admin_user)
        self.admin_password = self._get_arg_value(self._admin_password)
        self.location = self._get_arg_value(self._location)
        if self.location is None:
            self.location = self.rsrc_grp.location
        self.pub_key_data = self._get_arg_value(self._pub_key_data)

    def get_init_args(self):
        args, kwargs = super(AzServer, self).get_init_args()
        args += (self._rsrc_grp, self._nics)
        kwargs.update({"publisher": self._publisher,
                       "offer": self._offer,
                       "sku": self._sku,
                       "version": self._version,
                       "vm_size": self._vm_size,
                       "admin_user": self._admin_user,
                       "admin_password": self._admin_password,
                       "location": self._location,
                       "pub_key_data": self._pub_key_data})
        return args, kwargs


class AzPublicIP(AzureProvisionableInfraResource, IPAddressable):
    def __init__(self, name, rsrc_grp, location=None, **kwargs):
        super(AzPublicIP, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._location = location
        self.location = None
        # from Azure
        self.id = None
        self.ip = None

    def set_id(self, az_id):
        self.id = az_id

    def get_id(self):
        return self.id

    def set_ip(self, ip):
        self.ip = ip

    def get_ip(self, context=None):
        return self.ip

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip) if self.ip is not None else None

    def _get_attrs_dict(self):
        d = super(AzPublicIP, self)._get_attrs_dict()
        d.update({"rsrc_grp": self.rsrc_grp,
                  "location": self.location,
                  "id": self.id,
                  "ip": self.ip})
        return d

    def _fix_arguments(self, _=None):
        super(AzPublicIP, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        self.location = self._get_arg_value(self._location)
        if self.location is None:
            self.location = self.rsrc_grp.location

    def get_init_args(self):
        args, kwargs = super(AzPublicIP, self).get_init_args()
        args += (self._rsrc_grp,)
        kwargs["location"] = self._location
        return args, kwargs


class AzSecurityRule(AzureProvisionableInfraResource):
    def __init__(self, name, protocol, direction, destination_port_range, access, priority,
                 source_port_range="*", source_address_prefix="*", description="", **kwargs):
        super(AzSecurityRule, self).__init__(name, **kwargs)
        self._description = description
        self.description = None
        self._source_port_range = source_port_range
        self.source_port_range = None
        self._destination_port_range = destination_port_range
        self.destination_port_range = None
        self._protocol = protocol
        self.protocol = None
        self._source_address_prefix = source_address_prefix
        self.source_address_prefix = None
        self._access = access
        self.access = None
        self._priority = priority
        self.priority = None
        self._direction = direction
        self.direction = None
        # local data
        self.azure_obj = None

    def set_azure_obj(self, obj):
        self.azure_obj = obj

    def get_azure_obj(self):
        return self.azure_obj

    def _get_attrs_dict(self):
        d = super(AzSecurityRule, self)._get_attrs_dict()
        d.update({"description": self.description,
                  "source_port_range": self.source_port_range,
                  "destination_port_range": self.destination_port_range,
                  "protocol": self.protocol,
                  "source_address_prefix": self.source_address_prefix,
                  "access": self.access,
                  "priority": self.priority,
                  "direction": self.direction,
                  "azure_obj": self.azure_obj})
        return d

    def _fix_arguments(self, _=None):
        super(AzSecurityRule, self)._fix_arguments()
        self.protocol = self._get_arg_value(self._protocol)
        self.direction = self._get_arg_value(self._direction)
        self.destination_port_range = self._get_arg_value(self._destination_port_range)
        self.access = self._get_arg_value(self._access)
        self.priority = int(self._get_arg_value(self._priority))
        self.source_port_range = self._get_arg_value(self._source_port_range)
        self.source_address_prefix = self._get_arg_value(self._source_address_prefix)
        self.description = self._get_arg_value(self._description)

    def get_init_args(self):
        args, kwargs = super(AzSecurityRule, self).get_init_args()
        args += (self._protocol, self._direction, self._destination_port_range, self._access, self._priority)
        kwargs.update({"source_port_range": self._source_port_range,
                       "source_address_prefix": self._source_address_prefix,
                       "description": self._description})
        return args, kwargs


class AzSecurityGroup(AzureProvisionableInfraResource):
    def __init__(self, name, rsrc_grp, rules, **kwargs):
        super(AzSecurityGroup, self).__init__(name, **kwargs)
        self._rsrc_grp = rsrc_grp
        self.rsrc_grp = None
        self._rules = list(rules)
        self.rules = None

    def _get_attrs_dict(self):
        d = super(AzSecurityGroup, self)._get_attrs_dict()
        d.update({"rsrc_grp": self.rsrc_grp,
                  "rules": self.rules})
        return d

    def _fix_arguments(self, _=None):
        super(AzSecurityGroup, self)._fix_arguments()
        self.rsrc_grp = self._get_arg_value(self._rsrc_grp)
        rules = self._get_arg_value(self._rules)
        self.rules = [self._get_arg_value(rule) for rule in rules]

    def get_init_args(self):
        args, kwargs = super(AzSecurityGroup, self).get_init_args()
        args += (self._rsrc_grp, self._rules)
        return args, kwargs


__all__ = ["AzResourceGroup", "AzNetwork", "AzSubnet", "AzNIC", "AzServer", "AzPublicIP",
           "AzSecurityRule", "AzSecurityGroup", "AzureProvisionableInfraResource"]
