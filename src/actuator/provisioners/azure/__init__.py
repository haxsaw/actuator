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
Azure provisioner for Actuator
"""

from actuator.provisioners.core import (BaseProvisionerProxy, AbstractRunContext)
from actuator.provisioners.azure import azure_class_factory as acf
from actuator.provisioners.azure.resource_tasks import _azure_domain


class AzureRunConext(AbstractRunContext):
    def __init__(self, credentials):
        self.credentials = credentials

    @property
    def network(self):
        return acf.get_network_client(self.credentials)

    @property
    def compute(self):
        return acf.get_compute_client(self.credentials)

    @property
    def resource(self):
        return acf.get_resource_client(self.credentials)


class AzureProvisionerProxy(BaseProvisionerProxy):
    mapper_domain_name = _azure_domain

    def __init__(self, name, subscription_id=None, client_id=None, secret=None, tenant=None):
        super(AzureProvisionerProxy, self).__init__(name)
        self.azure_creds = acf.get_azure_credentials(subscription_id=subscription_id,
                                                     client_id=client_id,
                                                     secret=secret,
                                                     tenant=tenant)

    def run_context_factory(self):
        return AzureRunConext(self.azure_creds)


__all__ = ["AzureProvisionerProxy"]
