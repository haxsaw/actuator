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


__all__ = ["AzResourceGroup"]