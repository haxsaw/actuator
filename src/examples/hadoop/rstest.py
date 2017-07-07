from actuator.provisioners.openstack.openstack_class_factory import get_shade_cloud as gsc
from actuator.provisioners.openstack.support import _OSMaps
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
# c = gsc("rackspace")
c = gsc("citycloud")
# prov = OpenstackProvisioner(cloud_name="rackspace")


class FauxProvisioner(object):
    def __init__(self, cloud):
        self.cloud = cloud


prov = FauxProvisioner(c)
osm = _OSMaps(prov)
