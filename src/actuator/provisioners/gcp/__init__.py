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
Google Cloud Platform provisioner for Actuator
"""
from actuator.provisioners.core import (BaseProvisionerProxy, AbstractRunContext, ProvisionerException)
from actuator.provisioners.gcp import gcp_class_factory as gcf
from actuator.provisioners.gcp.resource_tasks import _gcp_domain


class GCPRunContext(AbstractRunContext):
    def __init__(self, creds):
        self.creds = creds

    @property
    def compute(self):
        return gcf.get_compute_client(self.creds)

    @property
    def storage(self):
        return gcf.get_storage_client(self.creds)

    @property
    def oslogin(self):
        return gcf.get_oslogin_client(self.creds)


class GCPProvisionerProxy(BaseProvisionerProxy):
    mapper_domain_name = _gcp_domain

    def __init__(self, name, project, service_account_json_creds, zone=None):
        """
        make a new Google Cloud Platform provisioner proxy
        :param name: name to give the proxy in order to match up with specific
            GCP resource cloud names
        :param project: string; name of the project the credentials apply to
        :param service_account_json_creds: path to the user-readable JSON file containing
            the authentication credentials needed to connect to GCP
        """
        super(GCPProvisionerProxy, self).__init__(name)
        self.creds = gcf.GCPCredentials(service_account_json_creds)
        self.project = project
        self.zone = zone

    def run_context_factory(self):
        return GCPRunContext(self.creds)

    def get_zone(self, rsrc):
        zone = rsrc.zone
        if zone is None:
            zone = self.zone
        if zone is None:
            raise ProvisionerException("Resource {} has no zone and there is no default zone for proxy {}"
                                       .format(rsrc.name, self.name))
        return zone


__all__ = ["GCPProvisionerProxy"]
