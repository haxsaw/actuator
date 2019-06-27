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
    def __init__(self, name, disk_image, machine_type, description=None, **kwargs):
        super(GCPServer, self).__init__(name, **kwargs)
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
    def __init__(self, name, public_key_filename=None, public_key_data=None,
                 expirationTimeInSecs=60*60, delete_on_depro=False,
                 alternate_credentials_file=None, **kwargs):
        """
        import a publio key to allow ssh'ing into instances

        Specify a public key to import into GCP to facilitate ssh access to a machine. By default,
        the key will be for the user whose credentials are used to access GCP, but an alternate
        credentials file can be supplied so that the key will be set up for a different user.

        During initiation processing, Actuator will check the available public keys and if the same
        key can be found already present in GCP, no further action is taken.

        @param name: string; the Actuator name to give the resource
        @param public_key_filename: string; the path to a readable public key file whose data will be loaded
            into GCP. One of public_key_filename or public_key_data must be specified during
            creation. Failure to supply one or the other will result in a ProvisionerException
        @param public_key_data: string; the actual contents of a public key; the data will be sent to
            GCP with no further interpretation. One of public_key_data or public_key_filename must
            be specified during creation. Failure to supply one or the other will result in a
            ProvisionerException.
        @param expirationTImeInSecs: integer, default 1 hour. The number of seconds from now in which
            the public key should expire. THe default is to expire in 1 hour.
        @param delete_on_depro: bool, default False. If True, then when tearing down a system delete
            the public key. Default is False-- leave the public key in GCP when doing a teardown.
        @param alternate_credentials_file: string, default None. If supplied, must be the path
            to a GCP credentials JSON file that is to be the target of the public key import. Normally,
            the public key is imported into the account used for the orchestration of system
            standup. Supply this value to specifiy a different project/user target for importing the
            key.
        """
        super(GCPSSHPublicKey, self).__init__(name, **kwargs)
        if public_key_data is None and public_key_filename is None:
            raise ProvisionerException("Can create the GCPSSHPublicKey instance; you must supply one "
                                       "of public_key_filename or public_key_data when creating this "
                                       "resource. These may be context expressions for values in the "
                                       "namespace model.")
        self._public_key_filename = public_key_filename
        self.public_key_fileame = None
        self._public_key_data = public_key_data
        self.public_key_data = None
        self._expirationTimeInSecs = expirationTimeInSecs
        self.expirationTimeInSecs = None
        self._delete_on_depro = delete_on_depro
        self.delete_on_depro = None
        self._alternate_credentials_file = alternate_credentials_file
        self.alternate_credentials_file = None

    def get_init_args(self):
        args, kwargs = super(GCPSSHPublicKey, self).get_init_args()
        kwargs.update({"public_key_filename": self._public_key_filename,
                       "public_key_data": self._public_key_data,
                       "expirationTimeInSecs": self._expirationTimeInSecs,
                       "delete_on_depro": self._delete_on_depro,
                       "alternate_credentials_file": self._alternate_credentials_file})
        return args, kwargs

    def _get_attrs_dict(self):
        d = super(GCPSSHPublicKey, self)._get_attrs_dict()
        d.update({'public_key_filename': self.public_key_fileame,
                  'public_key_data': self.public_key_data,
                  'expirationTimeInSecs': self.expirationTimeInSecs,
                  'delete_on_depro': self.delete_on_depro,
                  'alternate_credentials_file': self.alternate_credentials_file})
        return d

    def _fix_arguments(self, _=None):
        super(GCPSSHPublicKey, self)._fix_arguments()
        self.public_key_data = self._get_arg_value(self._public_key_data)
        self.public_key_fileame = self._get_arg_value(self._public_key_filename)
        try:
            self.expirationTimeInSecs = int(self._get_arg_value(self._expirationTimeInSecs))
        except ValueError as e:
            raise ProvisionerException("Couldn't convert expirationTimeInSecs to an int; %s"
                                       % str(e))
        try:
            self.delete_on_depro = bool(self._get_arg_value(self._delete_on_depro))
        except ValueError as e:
            raise ProvisionerException("Couldn't convert delete_on_depro to a bool; %s"
                                       % str(3))
        self.alternate_credentials_file = self._get_arg_value(self._alternate_credentials_file)


__all__ = ["GCPServer", "GCPIPAddress", "GCPSSHPublicKey"]
