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
Created on Jan 6, 2015
'''
from actuator.provisioners.core import BaseProvisioningRecord


class OpenstackProvisioningRecord(BaseProvisioningRecord):
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
        
    def add_port_id(self, pid, osid):
        "map the provisionable id (pid) to the id of the provisioned Openstack item (osid)"
        self.port_ids[pid] = osid
        
    def add_server_id(self, pid, osid):
        self.server_ids[pid] = osid
        
    def add_secgroup_id(self, pid, osid):
        self.secgroup_ids[pid] = osid
        
    def add_secgroup_rule_id(self, pid, osid):
        self.secgroup_rule_ids[pid] = osid
        
    def add_router_id(self, pid, osid):
        self.router_ids[pid] = osid
        
    def add_router_iface_id(self, pid, osid):
        self.router_iface_ids[pid] = osid
        
    def add_floating_ip_id(self, pid, osid):
        self.floating_ip_ids[pid] = osid
        
    def add_subnet_id(self, pid, osid):
        self.subnet_ids[pid] = osid
        
    def add_network_id(self, pid, osid):
        self.network_ids[pid] = osid
        
        
class _OSMaps(object):
    def __init__(self, os_provisioner):
        self.os_provisioner = os_provisioner
        self.image_map = {}
        self.flavor_map = {}
        self.network_map = {}
        self.secgroup_map = {}
        self.secgroup_rule_map = {}
        self.router_map = {}
        self.subnets_map = {}
        
    def refresh_all(self):
        self.refresh_flavors()
        self.refresh_images()
        self.refresh_networks()
        self.refresh_secgroups()
        self.refresh_routers()
        self.refresh_subnets()
        
    def refresh_subnets(self):
        response = self.os_provisioner.nuclient.list_subnets()
        self.subnets_map = {d['name']:d for d in response['subnets']}
        
    def refresh_routers(self):
        response = self.os_provisioner.nuclient.list_routers()
        self.router_map = {d['id']:d['id'] for d in response["routers"]}
        
    def refresh_networks(self):
        networks = self.os_provisioner.nvclient.networks.list()
        self.network_map = {n.label:n for n in networks}
        for network in networks:
            self.network_map[network.id] = network

    def refresh_images(self):
        self.image_map = {i.name:i for i in self.os_provisioner.nvclient.images.list()}

    def refresh_flavors(self):
        self.flavor_map = {f.name:f for f in self.os_provisioner.nvclient.flavors.list()}

    def refresh_secgroups(self):
        secgroups = list(self.os_provisioner.nvclient.security_groups.list())
        self.secgroup_map = {sg.name:sg for sg in secgroups}
        self.secgroup_map.update({sg.id:sg for sg in secgroups})
