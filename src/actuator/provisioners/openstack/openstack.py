'''
Created on 7 Sep 2014

@author: tom
'''
import time
import uuid


from actuator.provisioners.openstack import openstack_class_factory as ocf
NovaClient = ocf.get_nova_client_class()
NeutronClient = ocf.get_neutron_client_class()
from actuator.provisioners.openstack.components import _ComponentSorter

from actuator.infra import InfraSpec
from actuator.provisioners.core import BaseProvisioner, ProvisionerException, BaseProvisioningRecord


class OpenstackProvisioningRecord(BaseProvisioningRecord):
    def __init__(self, id):
        super(OpenstackProvisioningRecord, self).__init__(id)
        self.network_ids = dict()
        self.subnet_ids = dict()
        self.floating_ip_ids = dict()
        self.router_ids = dict()
        self.secgroup_ids = dict()
        self.server_ids = dict()
        self.port_ids = dict()
        
    def __getstate__(self):
        d = super(OpenstackProvisioningRecord, self).__getstate__()
        d.update( {"network_ids":self.network_ids,
                   "subnet_ids":self.subnet_ids,
                   "floating_ip_ids":self.floating_ip_ids,
                   "router_ids":self.router_ids,
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
        
    def add_router_id(self, pid, osid):
        self.router_ids[pid] = osid
        
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
        

class OpenstackProvisioner(BaseProvisioner):
    def __init__(self, username, password, tenant_name, auth_url):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url
        self.nvclient = NovaClient("1.1", self.username, self.password, self.tenant_name,
                                    self.auth_url)
        self.nuclient = NeutronClient(username=self.username, password=self.password,
                                        auth_url=self.auth_url, tenant_name=self.tenant_name)
        self.workflow_sorter = _ComponentSorter()
        self.osmaps = _OSMaps(self)

    def _deprovision(self, record):
        pass
    
    def _provision_sec_groups(self, record):
        for sg in self.workflow_sorter.secgroups:
            sg.fix_arguments()
            response = self.nvclient.security_groups.create(name=sg.logicalName,
                                                            description=sg.description)
            sg.set_osid(response.id)
            record.add_secgroup_id(sg._id, sg.osid)
    
    def  _process_server_addresses(self, server, addr_dict):
        for i, (k, v) in enumerate(addr_dict.items()):
            iface = getattr(server, "iface%d" % i)
            iface.name = k
            for j, iface_addr in enumerate(v):
                setattr(iface, "addr%d" % j, iface_addr['addr'])
                
    def _provision_router_interfaces(self, record):
        for ri in self.workflow_sorter.router_interfaces:
            ri.fix_arguments()
            router_id = ri.router
            subnet = ri.subnet
            _ = self.nuclient.add_interface_router(router_id, {u'subnet_id':subnet,
                                                               u'name':ri.logicalName})
                
    def _provision_networks(self, record):
        for network in self.workflow_sorter.networks:
            network.fix_arguments()
            msg = {u'network': {u'name':network.logicalName, u'admin_state_up':network.admin_state_up}}
            response = self.nuclient.create_network(body=msg)
            network.set_osid(response['network']['id'])
            record.add_network_id(network._id, network.osid)
            
    def _provision_subnets(self, record):
        for subnet in self.workflow_sorter.subnets:
            subnet.fix_arguments()
            msg = {'subnets': [{'cidr':subnet.cidr,
                                'ip_version':subnet.ip_version,
                                'network_id':subnet.network,
                                'dns_nameservers':subnet.dns_nameservers,
                                'name':subnet.logicalName}]}
            sn = self.nuclient.create_subnet(body=msg)
            subnet.set_osid(sn["subnets"][0]["id"])
            record.add_subnet_id(subnet._id, subnet.osid)
            
    def _provision_routers(self, record):
        for router in self.workflow_sorter.routers:
            router.fix_arguments()
            msg = {u'router': {u'admin_state_up':router.admin_state_up,
                               u'name':router.logicalName}}
            reply = self.nuclient.create_router(body=msg)
            router.set_osid(reply["router"]["id"])
            record.add_router_id(router._id, router.osid)
            
    def _provision_router_gateways(self, record):
        self.osmaps.refresh_networks()
        self.osmaps.refresh_routers()
        for rg in self.workflow_sorter.router_gateways:
            rg.fix_arguments()
            router_id = rg.router
            ext_net = self.osmaps.network_map.get(rg.external_network_name)
            msg = {u'network_id':ext_net.id}
            _ = self.nuclient.add_gateway_router(router_id, msg)
            
    def _provision_servers(self, record):
        if self.workflow_sorter.servers:
            self.osmaps.refresh_images()
            self.osmaps.refresh_flavors()
            self.osmaps.refresh_networks()
            for server in self.workflow_sorter.servers:
                server.fix_arguments()
                args, kwargs = server.get_init_args()
                name, image_name, flavor_name = args
                image = self.osmaps.image_map.get(image_name)
                if image is None:
                    raise ProvisionerException("Image %s doesn't seem to exist" % image_name, record=record)
                flavor = self.osmaps.flavor_map.get(flavor_name)
                if flavor is None:
                    raise ProvisionerException("Flavor %s doesn't seem to exist" % flavor_name, record=record)
                secgroup_list = []
                if server.security_groups:
                    self.osmaps.refresh_secgroups()
                    for sgname in server.security_groups:
                        sg = self.osmaps.secgroup_map.get(sgname)
                        if sg is None:
                            raise ProvisionerException("Security group %s doesn't seem to exist" % sgname,
                                                       record=record)
                        secgroup_list.append(sg.id)
                    kwargs["security_groups"] = secgroup_list
                nics_list = []
                
                if server.nics:
                    for nicname in server.nics:
                        nic = self.osmaps.network_map.get(nicname)
                        if nic is None:
                            raise ProvisionerException("NIC %s doesn't seem to exist" % nicname,
                                                       record=record)
                        nics_list.append({'net-id':nic.id})
                    kwargs['nics'] = nics_list
                    
                srvr = self.nvclient.servers.create(name, image, flavor, **kwargs)
                server.set_osid(srvr.id)
                record.add_server_id(server._id, server.osid)
                while not srvr.addresses:
                    time.sleep(0.25)
                    srvr.get()
                server.set_addresses(srvr.addresses)
                self._process_server_addresses(server, srvr.addresses)
                
    def _provision_floating_ips(self, record):
        for floating_ip in self.workflow_sorter.floating_ips:
            floating_ip.fix_arguments()
            fip = self.nvclient.floating_ips.create(floating_ip.pool)
            floating_ip.set_addresses(fip.ip)
            floating_ip.set_osid(fip.id)
            record.add_floating_ip_id(floating_ip._id, floating_ip.osid)
            associated_ip = floating_ip.associated_ip
            if associated_ip is not None:
                server = self.nvclient.servers.get(floating_ip.server)
                self.nvclient.servers.add_floating_ip(server, fip, associated_ip)
        
    def _provision(self, infraspec_instance):
        assert isinstance(infraspec_instance, InfraSpec)
        record = OpenstackProvisioningRecord(uuid.uuid4())
        self.workflow_sorter.sort_provisionables(infraspec_instance.provisionables())
        infraspec_instance.refs_for_provisionables()
        #@FIXME the above computation of refs_for_provisionables() leaves some items
        #unable to work properly, notably finding containers.
#         infraspec_instance.validate_args()
        
        #now do the provisioning in order
        self._provision_networks(record)
        
        self._provision_subnets(record)
        
        self._provision_sec_groups(record)
        
        self._provision_servers(record)

        self._provision_routers(record)
        
        self._provision_router_gateways(record)
        
        self._provision_router_interfaces(record)
        
        self._provision_floating_ips(record)

        return record
                        
                                               
