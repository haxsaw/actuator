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
Openstack provisioner for Actuator
"""

import uuid
from errator import narrate
from actuator.provisioners.core import (BaseProvisionerProxy,
                                        AbstractRunContext)
from actuator.provisioners.openstack.resource_tasks import _rt_domain
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.provisioners.openstack.support import (_OSMaps,
                                                     OpenstackProvisioningRecord)


class OpenstackCredentials(object):
    def __init__(self, cloud_name=None, config_files=None):
        self.cloud_name = cloud_name
        self.config_files = config_files


class OpenStackRunContext(AbstractRunContext):
    def __init__(self, record, os_creds):
        self.os_creds = os_creds
        self.record = record
        self.maps = _OSMaps(self)

    @property
    @narrate(lambda s: "...which required loading the cloud definitions file '%s'" % (str(s.os_creds.cloud_name),))
    def cloud(self):
        if self.os_creds.cloud_name:
            cloud = ocf.get_shade_cloud(self.os_creds.cloud_name,
                                        config_files=self.os_creds.config_files)
        else:
            cloud = None
        return cloud


class OpenStackProvisionerProxy(BaseProvisionerProxy):
    mapper_domain_name = _rt_domain

    def __init__(self, cloud_name, config_files=None):
        super(OpenStackProvisionerProxy, self).__init__()
        self.os_creds = OpenstackCredentials(cloud_name=cloud_name, config_files=config_files)

    @narrate(lambda _: "...which required getting an OpenStack run context")
    def run_context_factory(self):
        return OpenStackRunContext(OpenstackProvisioningRecord(uuid.uuid4()), self.os_creds)


__all__ = ["OpenStackProvisionerProxy"]
