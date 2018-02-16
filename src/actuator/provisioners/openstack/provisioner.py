import uuid
from errator import narrate
from actuator.provisioners.altcore import (BaseProvisionerProxy,
                                           AbstractRunContext)
from actuator.provisioners.openstack.resource_tasks import (ProvisioningTask,
                                                            _rt_domain)
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

    def run_context_factory(self):
        return OpenStackRunContext(OpenstackProvisioningRecord(uuid.uuid4()), self.os_creds)