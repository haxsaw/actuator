#
# Copyright (c) 2019 Tom Carroll
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
This module contains resource classes for provisioning Google Cloud Platform resources.
"""
import collections
from actuator.infra import Provisionable
from actuator.utils import IPAddressable
from actuator.provisioners.core import ProvisionerException


class GCPProvisionableInfraResource(Provisionable):
    def __init__(self, name, *args, **kwargs):
        try:
            zone = kwargs.pop('zone')
        except KeyError:
            zone = None
        super(GCPProvisionableInfraResource, self).__init__(name, *args, **kwargs)
        self._zone = zone
        self.zone = None
        # comes from GCP
        self.self_link = None
        self.gcp_id = None
        self.gcp_name = None

    def _get_attrs_dict(self):
        d = super(GCPProvisionableInfraResource, self)._get_attrs_dict()
        d.update({"gcp_id": self.gcp_id,
                  "self_link": self.self_link,
                  'zone': self.zone,
                  'gcp_name': self.gcp_name})
        return d

    def _fix_arguments(self, _=None):
        super(GCPProvisionableInfraResource, self)._fix_arguments()
        self.zone = self._get_arg_value(self._zone)

    def get_init_args(self):
        args, kwargs = super(GCPProvisionableInfraResource, self).get_init_args()
        kwargs['zone'] = self._zone
        return args, kwargs


class GCPServer(GCPProvisionableInfraResource, IPAddressable):
    def __init__(self, name, disk_image, machine_type, *args, description=None, **kwargs):
        super(GCPServer, self).__init__(name, *args, **kwargs)
        self.disk_image = None
        self._disk_image = disk_image
        self.machine_type = None
        self._machine_type = machine_type
        self.description = None
        self._description = description
        # received from GCP
        self.gcp_data = None

    def get_ip(self, context=None):
        return self.gcp_data['networkInterfaces'][0]['networkIP'] if self.gcp_data is not None else None

    def get_cidr4(self, *_):
        ip = self.get_ip()
        return "{}/32".format(ip) if ip is not None else None

    def get_gcp_data(self):
        return self.gcp_data

    def _get_attrs_dict(self):
        d = super(GCPServer, self)._get_attrs_dict()
        d.update({"disk_image": self.disk_image,
                  "machine_type": self.machine_type,
                  "description": self.description,
                  "gcp_data": self.gcp_data})
        return d

    def _fix_arguments(self, _=None):
        super(GCPServer, self,)._fix_arguments()
        self.disk_image = self._get_arg_value(self._disk_image)
        self.machine_type = self._get_arg_value(self._machine_type)
        self.description = self._get_arg_value(self._description)

    def get_init_args(self):
        args, kwargs = super(GCPServer, self).get_init_args()
        args += (self._disk_image, self._machine_type)
        kwargs.update({"description": self._description})
        return args, kwargs


class GCPIPAddress(GCPProvisionableInfraResource, IPAddressable):
    """
    This can define both INTERNAL and EXTERNAL IP addresses for an instance. The address
    may get created directly, or acquired from default values in the associated server.
    In the case of an association, this will only be the external IP address.
    """
    def __init__(self, name, instance, *args, **kwargs):
        super(GCPIPAddress, self).__init__(name, *args, **kwargs)
        self.instance = None
        self._instance = instance
        # determined dynamically
        self.ip = None

    def get_ip(self):
        return self.ip

    def set_ip(self, ip):
        self.ip = ip

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip) if self.ip is not None else None

    def _get_attrs_dict(self):
        d = super(GCPIPAddress, self)._get_attrs_dict()
        d.update({"instance": self.instance,
                  "ip": self.ip})
        return d

    def _fix_arguments(self, _=None):
        super(GCPIPAddress, self)._fix_arguments()
        self.instance = self._get_arg_value(self._instance)

    def get_init_args(self):
        args, kwargs = super(GCPIPAddress, self).get_init_args()
        args += (self._instance,)
        return args, kwargs


class GCPSSHPublicKey(GCPProvisionableInfraResource):
    def __init__(self, name, public_key_filename, expirationTimeInUSecs, delete_on_depro=False):
        pass


__all__ = ["GCPServer", "GCPIPAddress"]
