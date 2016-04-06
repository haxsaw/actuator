# Copyright (c) 2014 Tom Carroll
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
'''
Support for the Openstack provisioner.

This module's main contents are a class that captures the Openstack ids
of Openstack resources that have been provisioned for a model, and a class that
can retrieves and caches identifiers for Openstack resources that may be needed
when provisioning infra for a model.
'''

from actuator.provisioners.core import BaseProvisioningRecord


class OpenstackProvisioningRecord(BaseProvisioningRecord):
    """
    Primitive record of provisioned Openstack resources. Currently only capture
    the ids of the resources.
    """
    def __init__(self, id):
        super(OpenstackProvisioningRecord, self).__init__(id)
        self.network_ids = dict()
        self.subnet_ids = dict()
        self.floating_ip_ids = dict()
        self.router_ids = dict()
        self.router_iface_ids = dict()
        self.secgroup_ids = dict()
        self.secgroup_rule_ids = dict()
        self.server_ids = dict()
        self.port_ids = dict()
        #keypairs are deliberately left out for now
        
    def __getstate__(self):
        d = super(OpenstackProvisioningRecord, self).__getstate__()
        d.update( {"network_ids":self.network_ids,
                   "subnet_ids":self.subnet_ids,
                   "floating_ip_ids":self.floating_ip_ids,
                   "router_ids":self.router_ids,
                   "router_iface_ids":self.router_iface_ids,
                   "secgroup_ids":self.secgroup_ids,
                   "server_ids":self.server_ids,
                   "port_ids":self.port_ids} )
        return d
    
    def __setstate__(self, d):
        super(OpenstackProvisioningRecord, self).__setstate__(d)
        keys = d.keys()
        for k in keys:
            setattr(self, k, set(d[k]))
            del d[k]
        
    def add_port_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.port_ids[rid] = osid
        
    def add_server_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.server_ids[rid] = osid
        
    def add_secgroup_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.secgroup_ids[rid] = osid
        
    def add_secgroup_rule_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.secgroup_rule_ids[rid] = osid
        
    def add_router_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.router_ids[rid] = osid
        
    def add_router_iface_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.router_iface_ids[rid] = osid
        
    def add_floating_ip_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.floating_ip_ids[rid] = osid
        
    def add_subnet_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.subnet_ids[rid] = osid
        
    def add_network_id(self, rid, osid):
        """
        Maps an Actuator resource id to the associated Openstack resource id
        
        @param rid: Actuator resource id
        @param osid: Openstack resource id
        """
        self.network_ids[rid] = osid
        
        
class _OSMaps(object):
    """
    Utility class that creates a cache of Openstack resources. The resources
    are mapped by their "natural" key to their appropriate Openstack API
    client object (nova, neutron, etc).
    """
    def __init__(self, os_provisioner):
        self.os_provisioner = os_provisioner
        self.image_map = {}
        self.flavor_map = {}
        self.network_map = {}
        self.secgroup_map = {}
        self.secgroup_rule_map = {}
        self.router_map = {}
        self.subnet_map = {}
        self.keypair_map = {}
        
    def refresh_all(self):
        """
        Refresh all maps
        """
        self.refresh_flavors()
        self.refresh_images()
        self.refresh_networks()
        self.refresh_secgroups()
        self.refresh_routers()
        self.refresh_subnets()
        self.refresh_keypairs()
        
    def refresh_keypairs(self):
        """
        Refresh the keypairs map, keypair_map.
        Keys are the keypair name, values are nova Keypair values.
        """
        response = self.os_provisioner.nvclient.keypairs.list()
        self.keypair_map = {kp.name: kp for kp in response}
        
    def refresh_subnets(self):
        """
        Refresh the subnets map, subnet_map.
        Keys are the subnet name, value is the neutron subnet dict.
        """
        response = self.os_provisioner.nuclient.list_subnets()
        self.subnet_map = {d['name']:d for d in response['subnets']}
        
    def refresh_routers(self):
        """
        Refresh the routers map, router_map
        Keys are the Openstack ID for the router, values are the same ID
        """
        response = self.os_provisioner.nuclient.list_routers()
        self.router_map = {d['id']:d['id'] for d in response["routers"]}
        
    def refresh_networks(self):
        """
        Refresh the networks map, network_map.
        Keys are the network id, values are nova Network objects
        """
        networks = self.os_provisioner.nvclient.networks.list()
        self.network_map = {n.label:n for n in networks}
        for network in networks:
            self.network_map[network.id] = network

    def refresh_images(self):
        """
        Refresh the images map, image_map
        Keys are image names, values are nova Image objects.
        """
        self.image_map = {i.name:i for i in self.os_provisioner.nvclient.images.list()}

    def refresh_flavors(self):
        """
        Refresh the flavors map, flavor_map
        Keys are flavor names, values are nova Flavor objects
        """
        self.flavor_map = {f.name:f for f in self.os_provisioner.nvclient.flavors.list()}

    def refresh_secgroups(self):
        """
        Refresh the sec groups map, secgroup_map
        Keys are secgroup names and secgroup ids, values are nova SecGroup
        objects.
        """
        secgroups = list(self.os_provisioner.nvclient.security_groups.list())
        self.secgroup_map = {sg.name:sg for sg in secgroups}
        self.secgroup_map.update({sg.id:sg for sg in secgroups})
