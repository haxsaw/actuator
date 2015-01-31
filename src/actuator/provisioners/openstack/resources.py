# 
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
Created on 7 Sep 2014
'''
import collections
import ipaddress

from actuator.infra import Provisionable, IPAddressable
from actuator.provisioners.core import ProvisionerException
from __builtin__ import int


class _OpenstackProvisionableInfraResource(Provisionable):
    def __init__(self, *args, **kwargs):
        super(_OpenstackProvisionableInfraResource, self).__init__(*args, **kwargs)
        self.osid = None
        
    def set_osid(self, id):
        self.osid = id
        
    def _get_arg_msg_value(self, arg, klass, attrname, argname):
        value = arg
        if value is not None:
            if isinstance(value, klass):
                if hasattr(value, attrname):
                    value = getattr(value, attrname)
            elif not isinstance(value, basestring):
                raise ProvisionerException("Arg %s didn't result in a string or a %s ref" %
                                           (argname, klass.__name__))
        return value
                
            


class NetworkInterface(object):
    """
    This class provides a place to store broken-out address fields into discrete attributes
    that can successfully have model references built on top of them.
    """
    def __init__(self, name=None):
        self.name = None
        self.addr0 = None
        self.addr1 = None
        self.addr2 = None
        self.addr3 = None
        self.addr4 = None
        self.addr5 = None
        self.addr6 = None
        self.addr7 = None


class Server(_OpenstackProvisionableInfraResource, IPAddressable):
    def __init__(self, name, imageName, flavorName, meta=None, files=None,
                 reservation_id=None, min_count=None, max_count=None, security_groups=None,
                 userdata=None, key_name=None, availability_zone=None, block_device_mapping=None,
                 block_device_mapping_v2=None, nics=None, scheduler_hints=None,
                 config_drive=None, disk_config=None, **kwargs):
        """
        secgroups: string, comma separated list of security group names
        """
        super(Server, self).__init__(name)
        self._imageName = imageName
        self.imageName = None
        self._flavorName = flavorName
        self.flavorName = None
        self._meta = meta
        self.meta = None
        self._files = files   #this one may be a list of files to suck up; we make the dict
        self.files = None   #this one may be a list of files to suck up; we make the dict
        self._reservation_id = reservation_id
        self.reservation_id = None
        self._min_count = min_count
        self.min_count = None
        self._max_count = max_count
        self.max_count = None
        self._security_groups = security_groups
        self.security_groups = None
        self._userdata = userdata
        self.userdata = None
        self._key_name = key_name
        self.key_name = None
        self._availability_zone = availability_zone
        self.availability_zone = None
        self._block_device_mapping = block_device_mapping
        self.block_device_mapping = None
        self._block_device_mapping_v2 = block_device_mapping_v2
        self.block_device_mapping_v2 = None
        self._nics = nics
        self.nics = None
        self._scheduler_hints = scheduler_hints
        self.scheduler_hints = None
        self._config_drive = config_drive
        self.config_drive = None
        self._disk_config = disk_config
        self.disk_config = None
        #@FIXME: disabling floating get_ip argument in order to avoid accidental
        #cycles in the dependency graph.
#         self._floating_ip=floating_ip
#         self.floating_ip=None
        #things determined by from provisioning
#         self.server_id = None
        self.addresses = None
        self.provisionedName = None
        self.iface0 = NetworkInterface()
        self.iface1 = NetworkInterface()
        self.iface2 = NetworkInterface()
        self.iface3 = NetworkInterface()
        
    def _fix_arguments(self, provisioner=None):
        self.imageName = self._get_arg_value(self._imageName)
        self.flavorName = self._get_arg_value(self._flavorName)
        self.meta = (self._get_arg_value(self._meta)
                     if self._meta is not None
                     else None)
        self.files = (self._get_arg_value(self._files)
                      if self._files is not None
                      else None)
        self.reservation_id = (self._get_arg_value(self._reservation_id)
                               if self._reservation_id is not None
                               else None)
        self.min_count = (self._get_arg_value(self._min_count)
                          if self._min_count is not None
                          else None)
        self.max_count = (self._get_arg_value(self._max_count)
                          if self._max_count is not None
                          else None)
        if self._security_groups is None:
            self.security_groups = []
        else:
            secgrps = self._get_arg_value(self._security_groups)
            if not isinstance(secgrps, collections.Iterable):
                ProvisionerException("Processing the security_groups argument didn't yield a list")
            self.security_groups = [self._get_arg_value(sg)
                                    for sg in secgrps]
            
        self.userdata = (self._get_arg_value(self._userdata)
                         if self._userdata is not None
                         else None)
        self.key_name = (self._get_arg_value(self._key_name)
                         if self._key_name is not None
                         else None)
        self.availability_zone = (self._get_arg_value(self._availability_zone)
                                  if self._availability_zone is not None
                                  else None)
        self.block_device_mapping = (self._get_arg_value(self._block_device_mapping)
                                     if self._block_device_mapping is not None
                                     else None)
        self.block_device_mapping_v2 = (self._get_arg_value(self._block_device_mapping_v2)
                                        if self._block_device_mapping_v2 is not None
                                        else None)
        
        if self._nics is None:
            self.nics = []
        else:
            nics = self._get_arg_value(self._nics)
            if not isinstance(nics, collections.Iterable):
                ProvisionerException("Processing the nics argument didn't yield a list")
            self.nics = [self._get_arg_value(nic)
                         for nic in nics]
                        
        self.scheduler_hints = (self._get_arg_value(self._scheduler_hints)
                                if self._scheduler_hints is not None
                                else None)
        self.config_drive = (self._get_arg_value(self._config_drive)
                             if self._config_drive is not None
                             else None)
        self.disk_config = (self._get_arg_value(self._disk_config)
                            if self._disk_config is not None
                            else None)
            
    def set_addresses(self, addresses):
        self.addresses = addresses
        
    def get_init_args(self):
        return ( (self.name, self._imageName, self._flavorName),
                 {"meta":self._meta, "files":self._files, "reservation_id":self._reservation_id,
                  "min_count":self._min_count, "max_count":self._max_count,
                  "security_groups":self._security_groups,
                  "userdata":self._userdata,
                  "key_name":self._key_name, "availability_zone":self._availability_zone,
                  "block_device_mapping":self._block_device_mapping,
                  "block_device_mapping_v2":self._block_device_mapping_v2,
                  "nics":self._nics,
                  "scheduler_hints":self._scheduler_hints,
                  "config_drive":self._config_drive, "disk_config":self._disk_config,})
#                   "floating_ip":self._floating_ip} )
        
    def get_fixed_args(self):
        return ( (self.name, self.imageName, self.flavorName),
                 {"meta":self.meta, "files":self.files, "reservation_id":self.reservation_id,
                  "min_count":self.min_count, "max_count":self.max_count,
                  "security_groups":self.security_groups,
                  "userdata":self.userdata,
                  "key_name":self.key_name, "availability_zone":self.availability_zone,
                  "block_device_mapping":self.block_device_mapping,
                  "block_device_mapping_v2":self.block_device_mapping_v2,
                  "nics":self.nics,
                  "scheduler_hints":self.scheduler_hints,
                  "config_drive":self.config_drive, "disk_config":self.disk_config,})
#                   "floating_ip":self.floating_ip} )

    def get_ip(self, context=None):
        return self.iface0.addr0
        
        
class Network(_OpenstackProvisionableInfraResource):
    def __init__(self, name, admin_state_up=True):
        super(Network, self).__init__(name)
        self.admin_state_up = None
        self._admin_state_up = admin_state_up
        
    def _fix_arguments(self, provisioner=None):
        self.admin_state_up = self._get_arg_value(self._admin_state_up)
        
        
    def get_init_args(self):
        return ((self.name,),
                {"admin_state_up":self._admin_state_up})
        
        
class SecGroup(_OpenstackProvisionableInfraResource):
    def __init__(self, name, description=None):
        super(SecGroup, self).__init__(name)
        self._description = description
        self.description = None
        
    def get_init_args(self):
        return ((self.name,),
                {"description":self._description})
    
    def _fix_arguments(self, provisioner=None):
        self.description = self._get_arg_value(self._description)
        

class SecGroupRule(_OpenstackProvisionableInfraResource):
    def __init__(self, name, secgroup, ip_protocol=None, from_port=None,
                 to_port=None, cidr=None):
        super(SecGroupRule, self).__init__(name)
        self._secgroup = secgroup
        self.secgroup = None
        self._ip_protocol = ip_protocol
        self.ip_protocol = None
        self._from_port = from_port
        self.from_port = None
        self._to_port = to_port
        self.to_port = None
        self._cidr = cidr
        self.cidr = None
        
    def get_init_args(self):
        return ((self.name, self._secgroup),
                {"ip_protocol":self._ip_protocol,
                 "from_port":self._from_port,
                 "to_port":self._to_port,
                 "cidr":self._cidr})
    
    def _fix_arguments(self, provisioner=None):
        self.secgroup = self._get_arg_value(self._secgroup)
        self.ip_protocol = self._get_arg_value(self._ip_protocol)
        self.from_port = self._get_arg_value(self._from_port)
        self.to_port = self._get_arg_value(self._to_port)
        self.cidr = self._get_arg_value(self._cidr)
        
        
class Subnet(_OpenstackProvisionableInfraResource):
    _ipversion_map = {ipaddress.IPv4Network:4, ipaddress.IPv6Network:6}
    def __init__(self, name, network, cidr, dns_nameservers=None, ip_version=4):
        """
        @param name: string; logical name for the subnet
        @param network: Network; a string containing the Openstack id of a network, or a callable
            that returns either a similar string or a Network object this subnet applies to
        @param cidr: string or callable; either a cidr-4 or cidr-6 string identifying the subnet
        @param dns_nameservers: list of strings of IP addresses of DNS nameservers, or may be
            a callable the produces a list of strings
        """
        super(Subnet, self).__init__(name)
        self._network = network
        self.network = None
        self._cidr = cidr
        self.cidr = None
        self._ip_version = ip_version
        self.ip_version = None
        self._dns_nameservers = dns_nameservers
        self.dns_nameservers = None
        
    def _fix_arguments(self, provisioner=None):
        self.network = self._get_arg_value(self._network)
        self.cidr = unicode(self._get_arg_value(self._cidr))
        self.ip_version = self._get_arg_value(self._ip_version)
        if self._dns_nameservers is None:
            self.dns_nameservers = []
        else:
            self.dns_nameservers = self._get_arg_value(self._dns_nameservers)
            if not (isinstance(self.dns_nameservers, collections.Iterable) and
                    reduce(lambda acc, item: acc and isinstance(item, basestring),
                           self.dns_nameservers, True)):
                raise ProvisionerException("The dns_nameservers arg is either not a "
                                           "list or else contains non-string objects")
        
    def get_init_args(self):
        return ((self.name, self._network, self._cidr), {'dns_nameservers':self._dns_nameservers,
                                                                'ip_version':self._ip_version})
    
    
class FloatingIP(_OpenstackProvisionableInfraResource, IPAddressable):
    def __init__(self, name, server, associated_ip, pool=None):
        """
        Creates a floating IP and attaches it to a server
        @param server: string with a Openstack server id, or a callable that returns either an
                Openstack server id string or a Server ref object
        @param associated_ip: string containing an IP on the server to associate with the floating get_ip,
                or a callable that returns the get_ip on a server (server.ifaceN.addrN)
        @param pool: optional; string name of the pool to allocate the IP from, or a callable that returns
                
        """
        super(FloatingIP, self).__init__(name)
        self._server = server
        self.server = None
        self._associated_ip = associated_ip
        self.associated_ip = None
        self._pool = pool
        self.pool = None
        self.ip = None
        
    def get_ip(self, context=None):
        return self.ip
        
    def _fix_arguments(self, provisioner=None):
        self.server = self._get_arg_value(self._server)
        self.associated_ip = self._get_arg_value(self._associated_ip)
        if self._pool is not None:
            self.pool = self._get_arg_value(self._pool)
        else:
            self.pool = self._pool
        
    def set_addresses(self, ip):
        self.ip = ip
        
    def get_init_args(self):
        return ((self.name, self._server, self._associated_ip), {"pool":self._pool})
    
    
class Router(_OpenstackProvisionableInfraResource):
    def __init__(self, name, admin_state_up=True):
        """
        @param admin_state_up: optional; True or False depending on whether or not the state of
            the router should be considered 'up'
        """
        super(Router, self).__init__(name)
        self._admin_state_up = admin_state_up
        self.admin_state_up = None
        
    def _fix_arguments(self, provisioner=None):
        self.admin_state_up = self._get_arg_value(self._admin_state_up)
        
    def get_init_args(self):
        return (self.name,), {"admin_state_up":self._admin_state_up}
    
    
class RouterGateway(_OpenstackProvisionableInfraResource):
    def __init__(self, name, router, external_network_name):
        """
        @param name: string; a logical name that will be used for the gateway
        @param router: a string with Openstack id of a router, or a callable that yields
                either a similar string or a ref to a Router object
        @param external_network_name: string; the name of the external network to 
                connect the router to
        """
        super(RouterGateway, self).__init__(name)
        self._router = router
        self.router = None
        self._external_network_name = external_network_name
        self.external_network_name = None
        
    def _fix_arguments(self, provisioner=None):
        self.router = self._get_arg_value(self._router)
        self.external_network_name = self._get_arg_value(self._external_network_name)
        
    def get_router(self):
        return self.router
    
    def get_external_network_name(self):
        return self.external_network_name
    
    def get_init_args(self):
        return ((self.name, self._router, self._external_network_name), {})
    
    
class RouterInterface(_OpenstackProvisionableInfraResource):
    def __init__(self, name, router, subnet):
        """
        @param name: string; a logical name for the interface
        @param router: a string or callable that yields a model reference whose value
                is a string; either is the name of a router, either created here or
                already running
        @param subnet: a string or a callable that yields a model reference whose
                value is a string; either way, the result is the name of a subnet
        """
        super(RouterInterface, self).__init__(name)
        self._router = router
        self.router = None
        self._subnet = subnet
        self.subnet = None
        
#     def fix_arguments(self, provisioner=None):
    def _fix_arguments(self, provisioner=None):
        self.router = self._get_arg_value(self._router)
        self.subnet = self._get_arg_value(self._subnet)
        return self
        
    def get_router(self):
        return self.router
    
    def get_subnet(self):
        return self.subnet
    
    def get_init_args(self):
        return ((self.name, self._router, self._subnet), {})
    
    
def _checktype(aType):
    def check_add_type(f):
        def exec_with_check(self, toAdd):
            if not isinstance(toAdd, aType):
                raise ProvisionerException("Received a %s, expected a %s" % (str(type(toAdd)), str(aType)))
            return f(self, toAdd)
        exec_with_check.__name__ = f.__name__
        exec_with_check.__doc__ = f.__doc__
        return exec_with_check
    return check_add_type
                
    
class _ResourceSorter(object):
    def __init__(self):
        self.networks = set()
        self.subnets = set()
        self.floating_ips = set()
        self.routers = set()
        self.router_gateways = set()
        self.router_interfaces = set()
        self.secgroups = set()
        self.secgroup_rules = set()
        self.servers = set()
        self.ports = set()
        self.sorter_map = {Network:self.add_network,
                           Subnet:self.add_subnet,
                           FloatingIP:self.add_floating_ip,
                           Router:self.add_router,
                           Server:self.add_server,
                           RouterGateway:self.add_router_gateway,
                           RouterInterface:self.add_router_interface,
                           SecGroup:self.add_secgroup,
                           SecGroupRule:self.add_secgroup_rule}
        
    def reset(self):
        self.networks.clear()
        self.subnets.clear()
        self.floating_ips.clear()
        self.routers.clear()
        self.router_gateways.clear()
        self.router_interfaces.clear()
        self.secgroups.clear()
        self.secgroup_rules.clear()
        self.servers.clear()
        self.ports.clear()
        
    def sort_provisionables(self, provisionable_iter):
        for prov in provisionable_iter:
            if not isinstance(prov, _OpenstackProvisionableInfraResource):
                continue
            self.sorter_map[prov.__class__](prov)
            
    @_checktype(RouterInterface)
    def add_router_interface(self, router_interface):
        self.router_interfaces.add(router_interface)
            
    @_checktype(RouterGateway)
    def add_router_gateway(self, router_gateway):
        self.router_gateways.add(router_gateway)

    @_checktype(Network)
    def add_network(self, network):
        self.networks.add(network)
    
    @_checktype(Subnet)
    def add_subnet(self, subnet):
        self.subnets.add(subnet)
        
    @_checktype(FloatingIP)
    def add_floating_ip(self, floating_ip):
        self.floating_ips.add(floating_ip)
        
    @_checktype(Router)
    def add_router(self, router):
        self.routers.add(router)
        
    def add_secgroup(self, secgroup):
        self.secgroups.add(secgroup)
        
    def add_secgroup_rule(self, secgroup_rule):
        self.secgroup_rules.add(secgroup_rule)
        
    @_checktype(Server)
    def add_server(self, server):
        self.servers.add(server)
        
    def add_port(self, port):
        self.ports.add(port)
        
        
