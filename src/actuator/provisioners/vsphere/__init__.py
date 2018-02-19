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

import threading
from pyVim import connect
from errator import narrate
from actuator.provisioners.core import (AbstractRunContext, BaseProvisionerProxy,
                                        ProvisionerException)
from actuator.provisioners.vsphere.resource_tasks import _vs_domain


class VSphereCredentials(object):
    def __init__(self, host, username, pwd):
        self.host = host
        self.username = username
        self.pwd = pwd


class VSphereRunContext(AbstractRunContext):
    ssl_patch_lock = threading.Lock()

    def __init__(self, credentials):
        assert isinstance(credentials, VSphereCredentials)
        self.credentials = credentials
        self._vcenter = None

    @property
    @narrate("...which required the acquisition of a connection to vCenter")
    def vcenter(self):
        if not self._vcenter:
            try:
                si = connect.SmartConnect(host=self.credentials.host,
                                          user=self.credentials.username,
                                          pwd=self.credentials.pwd)
            except Exception as e:
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(e):
                    try:
                        import ssl
                        with self.ssl_patch_lock:
                            dc = None
                            try:
                                dc = ssl._create_default_https_context
                                ssl._create_default_https_context = ssl._create_unverified_context
                                si = connect.SmartConnect(host=self.credentials.host,
                                                          user=self.credentials.username,
                                                          pwd=self.credentials.pwd)
                            finally:
                                ssl._create_default_https_context = dc
                    except Exception as e1:
                        raise Exception(e1)
                else:
                    raise
            self._vcenter = si
        return self._vcenter


class VSphereProvisionerProxy(BaseProvisionerProxy):
    mapper_domain_name = _vs_domain

    def __init__(self, name, creds=None, host=None, username=None, pwd=None):
        super(VSphereProvisionerProxy, self).__init__(name)
        if not creds and not (host and username and pwd):
            raise ProvisionerException("you must supply either a VSphereCredentials instance or else "
                                       "a host/username/pwd credentials set for vCenter")
        if not creds:
            creds = VSphereCredentials(host, username, pwd)
        elif not isinstance(creds, VSphereCredentials):
            raise ProvisionerException("The supplied creds object is not a kind of VSphereCredentials")

        self.creds = creds

    def run_context_factory(self):
        return VSphereRunContext(self.creds)


__all__ = ["VSphereProvisionerProxy", "VSphereCredentials"]
