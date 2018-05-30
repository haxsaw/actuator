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

"""
This module contains resource classes for provisioning Openstack resources.
"""
import collections
import ipaddress
import six
from errator import narrate

from actuator.modeling import ContextExpr
from actuator.infra import Provisionable, IPAddressable
from actuator.provisioners.core import ProvisionerException
from actuator.utils import _Persistable


class _OpenstackProvisionableInfraResource(Provisionable):
    """
    Base class for all Openstack provisionable resources.
    """
    def __init__(self, *args, **kwargs):
        """
        Create a new resource instance. The public attribute osid will hold the
        Openstack id of the resource once provisioned.
        """
        super(_OpenstackProvisionableInfraResource, self).__init__(*args, **kwargs)
        self.osid = None
        
    def _get_attrs_dict(self):
        d = super(_OpenstackProvisionableInfraResource, self)._get_attrs_dict()
        d["osid"] = str(self.osid)
        return d
        
    def set_osid(self, osid):
        """
        Set the Openstack id for the resource once it has been provisioned
        """
        self.osid = osid

    @staticmethod
    @narrate(lambda arg, klass, attrname, argname:
             "I started looking for a value for '{}'; it's either '{}' or in {}.{}"
             .format(argname, arg, klass, attrname))
    def _get_arg_msg_value(arg, klass, attrname, argname):
        # This method encapsulates a repeated access pattern; sometimes an attribute on an object
        # can be a plain string, sometimes an object from which we want to acquire a value from
        # a particular attribute. This method generalizes the value acquisition process, testing
        # if the value in question is an instance of a class from which we want to get the value
        # of a single attribute, or if the value we have is already a string and that's fine as
        # it is.
        #
        # arg is the value we need to examine; it may be the final value or an object where the value can be acquired
        # klass is the possible type of arg if arg isn't just a plain string
        # attrname is the name of the attribute to fetch from instances of klass to get our final value
        # argname is used for reporting an error if we can't find what we're expecting
        value = arg
        if value is not None:
            if isinstance(value, klass):
                if hasattr(value, attrname):
                    value = getattr(value, attrname)
            elif not isinstance(value, six.string_types):
                raise ProvisionerException("Arg %s didn't result in a string or a %s ref" %
                                           (argname, klass.__name__))
        return value
                

class NetworkInterface(_Persistable):
    """
    This class provides a place to store broken-out address fields into discrete
    attributes that can successfully have model references built on top of them.
    All attributes are meant to be public.
    """
    def __init__(self, _=None):
        self.name = None
        self.addr0 = None
        self.addr1 = None
        self.addr2 = None
        self.addr3 = None
        self.addr4 = None
        self.addr5 = None
        self.addr6 = None
        self.addr7 = None
        
    def _get_attrs_dict(self):
        d = super(NetworkInterface, self)._get_attrs_dict()
        d.update({"name": self.name,
                  "addr0": self.addr0,
                  "addr1": self.addr1,
                  "addr2": self.addr2,
                  "addr3": self.addr3,
                  "addr4": self.addr4,
                  "addr5": self.addr5,
                  "addr6": self.addr6,
                  "addr7": self.addr7})
        return d


class Server(_OpenstackProvisionableInfraResource, IPAddressable):
    """
    Represents an Openstack server instance.
    
    This resource class seeks to provide a simplified interface for the creation
    of Openstack servers. Many arguments to __init__() have been replaced with
    string values that are looked up to find the appropriate objects for the
    Openstack API, reducing the complexity of getting going. The differences
    will be documented in the docstrings for the affected methods. Where unchanged,
    the doc from the novaclient doc is copied directly.
    
    For full details see:
    http://docs.openstack.org/developer/python-novaclient/ref/v1_1/servers.html
    """
    def __init__(self, name, imageName, flavorName, meta=None,
                 min_count=1, max_count=1, security_groups=None,
                 userdata=None, key_name=None, availability_zone=None, block_device_mapping=None,
                 block_device_mapping_v2=None, nics=None, scheduler_hints=None,
                 config_drive=None, disk_config=None, **kwargs):
        """
        Define an Openstack server instance. The arguments to this call are
        analogs
        secgroups: string, comma separated list of security group names
        
        @param name: String; the logical name for the server. This name may be modified if
            the server is a template for a MultiResource.
        @param imageName: String; the name of the image to boot with. The Nova API
            normally requires an Image object here, but currently just the
            string name of the image is required, as the lookups for the Image
            are done internally.
        @param flavorName: String; the name of the flavor to boot onto. The Nova API
            normally requires a Flavor object here, but currently just the
            string name of the image is required, as the lookups for the Flavor
            are done internally.
        @keyword meta: A dict of arbitrary key/value metadata to store for this
            server. A maximum of five entries is allowed, and both keys and
            values must be 255 characters or less.
        @keyword userdata: user data to pass to be exposed by the metadata
            server this can be a file type object as well or a string.
        @keyword key_name: (optional extension) string or KeyPair referenence;
            identifies the public side of an ssh keypair to inject into the
            instance. If a string, must be the name of an already-existing key
            in Openstack.
        @keyword availability_zone: String name of the availability zone for
            instance placement.
        @keyword block_device_mapping: (optional extension) A dict of block
            device mappings for this server. See the novaclient doc noted above
            for information as to the format of keys and values
        @keyword block_device_mapping_v2: (optional extension) A dict of block
            device mappings for this server. See the novaclient doc noted above
            for information as to the format of keys and values
        @keyword nics: (optional extension) Differs from novaclient: an ordered
            list of references to Actuator L{Network} objects, must usually
            using a context expression (like 'ctxt.model.network1'). Required to
            actually reach the server you're creating.
        @keyword scheduler_hints: (optional extension) arbitrary key-value pairs
            specified by the client to help boot an instance. (NOTE: this is
            verbatim from the Openstack doc; one can only assume this is a dict)
        @keyword config_drive: (optional extension) value for config drive either
            boolean, or volume-id
        @keyword disk_config: (optional extension) control how the disk is
            partitioned when the server is created. possible values are 'AUTO'
            or 'MANUAL'.
        """
        super(Server, self).__init__(name, **kwargs)
        self._imageName = imageName
        self.imageName = None
        self._flavorName = flavorName
        self.flavorName = None
        self._meta = meta
        self.meta = None
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
        # @FIXME: disabling floating get_ip argument in order to avoid accidental
        # cycles in the dependency graph.
#         self._floating_ip=floating_ip
#         self.floating_ip=None
        # things determined by from provisioning
#         self.server_id = None
        self.addresses = None
        self.provisionedName = None
        self.iface0 = NetworkInterface()
        self.iface1 = NetworkInterface()
        self.iface2 = NetworkInterface()
        self.iface3 = NetworkInterface()
        
    def _find_persistables(self):
        for p in super(Server, self)._find_persistables():
            yield p
        for ni in (self.iface0, self.iface1, self.iface2, self.iface3):
            for p in ni.find_persistables():
                yield p
        
    def _get_attrs_dict(self):
        d = super(Server, self)._get_attrs_dict()
        _, kwargs = self.get_fixed_args()
        d.update({"name": self.name,
                  "imageName": self.imageName,
                  "flavorName": self.flavorName})
        d.update(kwargs)
        return d
    
    def encode_attr(self, k, v):
        if k == "userdata":
            retval = ({vk: (self._get_arg_value(vv)
                            if isinstance(vv, ContextExpr)
                            else vv) for vk, vv in v.items()}
                      if v is not None
                      else v)
            return retval 
        else:
            return super(Server, self).encode_attr(k, v)

    @narrate(lambda s, p=None: "...which resulted in fixing the arguments for server %s" % s.name)
    def _fix_arguments(self, provisioner=None):
        super(Server, self)._fix_arguments()
        self.imageName = self._get_arg_value(self._imageName)
        self.flavorName = self._get_arg_value(self._flavorName)
        self.meta = (self._get_arg_value(self._meta)
                     if self._meta is not None
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
                ProvisionerException("Processing the security_groups argument on server %s "
                                     "didn't yield a list" % self.name)
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
                                     else [])
        self.block_device_mapping_v2 = (self._get_arg_value(self._block_device_mapping_v2)
                                        if self._block_device_mapping_v2 is not None
                                        else [])
        
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
        """
        Internal; sets the returned dict of addresses for this server
        """
        self.addresses = addresses
        
    def get_init_args(self):
        _, kwargs = super(Server, self).get_init_args()
        kwargs.update({"meta": self._meta,
                       "min_count": self._min_count,
                       "max_count": self._max_count,
                       "security_groups": self._security_groups,
                       "userdata": self._userdata,
                       "key_name": self._key_name,
                       "availability_zone": self._availability_zone,
                       "block_device_mapping": self._block_device_mapping,
                       "block_device_mapping_v2": self._block_device_mapping_v2,
                       "nics": self._nics,
                       "scheduler_hints": self._scheduler_hints,
                       "config_drive": self._config_drive,
                       "disk_config": self._disk_config})
        return (self.name, self._imageName, self._flavorName), kwargs

    def get_fixed_args(self):
        """
        Similar to L{get_init_args} except that the arguments returned are the
        'fixed' values; that is, the arguments that resulted after evaluating all
        context expressions, calling all callables, etc.
        """
        kwargs = {}
        kwargs.update({"meta": self.meta,
                       "min_count": self.min_count,
                       "max_count": self.max_count,
                       "security_groups": self.security_groups,
                       "userdata": self.userdata,
                       "key_name": self.key_name,
                       "availability_zone": self.availability_zone,
                       "block_device_mapping": self.block_device_mapping,
                       "block_device_mapping_v2": self.block_device_mapping_v2,
                       "nics": self.nics,
                       "scheduler_hints": self.scheduler_hints,
                       "config_drive": self.config_drive,
                       "disk_config": self.disk_config})
        return (self.name, self.imageName, self.flavorName), kwargs

    def get_ip(self, context=None):
        """
        Returns the first ip on the first interface. If specific interfaces/ips
        are required, access the appropriate address on self.iface[0-3]
        """
        return self.iface0.addr0

    def get_cidr4(self, _=None):
        return "{}/32".format(self.iface0.addr0) if self.iface0.addr0 is not None else None
        
        
class Network(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack Neutron Network.
    
    This is a simplified version of the interface to create Openstack networks.
    Most arguments currently just assume their default values. This uses the
    Neutron client APIs.
    
    For full details, see:
    http://docs.openstack.org/user-guide/content/sdk_neutron_apis.html#sdk_neutron_create_network
    """
    def __init__(self, name, admin_state_up=True, **kwargs):
        """
        Create a new Openstack network.
        
        @param name: string; logical name for the network
        @keyword admin_state_up: boolean; true to indicate that network should be up.
        """
        super(Network, self).__init__(name, **kwargs)
        self.admin_state_up = None
        self._admin_state_up = admin_state_up
        
    def _get_attrs_dict(self):
        d = super(Network, self)._get_attrs_dict()
        d["admin_state_up"] = self.admin_state_up
        return d
    
    def _fix_arguments(self, provisioner=None):
        super(Network, self)._fix_arguments()
        self.admin_state_up = self._get_arg_value(self._admin_state_up)

    def get_init_args(self):
        args, kwargs = super(Network, self).get_init_args()
        kwargs["admin_state_up"] = self._admin_state_up
        return args, kwargs
        
        
class SecGroup(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack Nova security group.
    
    For full details see:
    http://docs.openstack.org/developer/python-novaclient/ref/v1_1/security_groups.html
    """
    def __init__(self, name, description="", **kwargs):
        """
        Create a new security group
        
        @param name: string; logical name for the security group
        @keyword description: optional string; a description for the sec group
        """
        super(SecGroup, self).__init__(name, **kwargs)
        self._description = description
        self.description = None
        
    def _get_attrs_dict(self):
        d = super(SecGroup, self)._get_attrs_dict()
        d["description"] = self.description
        return d
        
    def get_init_args(self):
        _, kwargs = super(SecGroup, self).get_init_args()
        kwargs["description"] = self._description
        return (self.name,), kwargs

    def _fix_arguments(self, provisioner=None):
        super(SecGroup, self)._fix_arguments()
        self.description = self._get_arg_value(self._description)
        

class SecGroupRule(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack Security Group Rule
    
    This interace differs from Openstack's in that it allows references to
    other Actuator resources instead of using either OS ids or OS objects.
    
    For full details of security group rules see:
    http://docs.openstack.org/developer/python-novaclient/ref/v1_1/security_group_rules.html 
    """
    def __init__(self, name, secgroup, ip_protocol=None, from_port=None,
                 to_port=None, cidr=None, **kwargs):
        """
        Create a new SecGroupRule on a SecGroup
        
        @param name: string; logical name for the rule
        @param secgroup: reference to an Actuator L{SecGroup} in a model.
            Generally these tend to be context expressions, for example
            'ctxt.model.secgroup'
        @keyword ip_protocol: string; an IP protocol name, one of 'tcp', 'udp'
            or 'icmp'
        @keyword from_port: integer; source port number
        @keyword to_port: integer; destination port number
        @keyword cidr: destination IP address(es) in CIDR notation; this narrows
            down the set of destination IP's without it, there is no narrowing
        """
        super(SecGroupRule, self).__init__(name, **kwargs)
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
        _, kwargs = super(SecGroupRule, self).get_init_args()
        kwargs.update({"ip_protocol": self._ip_protocol,
                       "from_port": self._from_port,
                       "to_port": self._to_port,
                       "cidr": self._cidr})
        return (self.name, self._secgroup), kwargs
        
    def _get_attrs_dict(self):
        d = super(SecGroupRule, self)._get_attrs_dict()
        d.update({"secgroup": self.secgroup,
                  "ip_protocol": self.ip_protocol,
                  "from_port": self.from_port,
                  "to_port": self.to_port,
                  "cidr": self.cidr})
        return d
    
    def _fix_arguments(self, provisioner=None):
        super(SecGroupRule, self)._fix_arguments()
        self.secgroup = self._get_arg_value(self._secgroup)
        self.ip_protocol = self._get_arg_value(self._ip_protocol)
        self.from_port = int(self._get_arg_value(self._from_port))
        self.to_port = int(self._get_arg_value(self._to_port))
        self.cidr = self._get_arg_value(self._cidr)
        
        
class Subnet(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack Neutron subnet
    
    Uses references to Actuator L{Network}s instead of OS ids values.
    
    For details see:
    http://docs.openstack.org/user-guide/content/sdk_neutron_apis.html#delete-network
    """
    _ipversion_map = {ipaddress.IPv4Network: 4, ipaddress.IPv6Network: 6}

    def __init__(self, name, network, cidr, dns_nameservers=None, ip_version=4, enable_dhcp=True, **kwargs):
        """
        @param name: string; logical name for the subnet
        @param network: Network; a string containing the Openstack id of a
            network, a reference to an Actuator L{Network}, or a callable that
            takes a L{actuator.modeling.CallContext} and returns one of the
            above. If a reference, most likely a context expression such as
            'ctxt.model.network'.
        @param cidr: string or callable that takes an L{actuator.modeling.CallContext}
            and returns a string; either a cidr-4 or cidr-6 string identifying
            the subnet address range
        @param dns_nameservers: list of strings of IP addresses of DNS nameservers,
            or may be a callable that takes an L{actuator.modeling.CallContext}
            and returns a list of strings
        """
        super(Subnet, self).__init__(name, **kwargs)
        self._network = network
        self.network = None
        self._cidr = cidr
        self.cidr = None
        self._ip_version = ip_version
        self.ip_version = None
        self._dns_nameservers = dns_nameservers
        self.dns_nameservers = None
        self._enable_dhcp = enable_dhcp
        self.enable_dhcp = None
        
    def _get_attrs_dict(self):
        d = super(Subnet, self)._get_attrs_dict()
        d.update({"network": self.network,
                  "cidr": self.cidr,
                  "ip_version": self.ip_version,
                  "dns_nameservers": self.dns_nameservers,
                  "enable_dhcp": self.enable_dhcp})
        return d
        
    def _fix_arguments(self, provisioner=None):
        super(Subnet, self)._fix_arguments()
        self.network = self._get_arg_value(self._network)
        try:
            self.cidr = unicode(self._get_arg_value(self._cidr))
        except NameError:
            self.cidr = self._get_arg_value(self._cidr)
        self.ip_version = self._get_arg_value(self._ip_version)
        self.enable_dhcp = self._get_arg_value(self._enable_dhcp)
        if self._dns_nameservers is None:
            self.dns_nameservers = []
        else:
            self.dns_nameservers = self._get_arg_value(self._dns_nameservers)
            if not (isinstance(self.dns_nameservers, collections.Iterable) and
                    all(isinstance(item, six.string_types) for item in self.dns_nameservers)):
                raise ProvisionerException("The dns_nameservers arg is either not a "
                                           "list or else contains non-string objects")
        
    def get_init_args(self):
        _, kwargs = super(Subnet, self).get_init_args()
        kwargs.update({'dns_nameservers': self._dns_nameservers,
                       'ip_version': self._ip_version,
                       'enable_dhcp': self._enable_dhcp})
        return (self.name, self._network, self._cidr), kwargs
    
    
class FloatingIP(_OpenstackProvisionableInfraResource, IPAddressable):
    """
    Represents an Openstack floating IP and the server it should be associated
    with.
    
    This call actually encompasses a few Openstack operations; first the allocation
    of the floating IP and then the association of that IP to the IP on a
    particular server.
    
    For details on creating floating IPs, see:
    http://docs.openstack.org/developer/python-novaclient/ref/v1_1/floating_ips.html
    
    For details on attaching them to a server, see:
    http://docs.openstack.org/developer/python-novaclient/ref/v1_1/servers.html
    """
    def __init__(self, name, server, associated_ip, pool=None, **kwargs):
        """
        Represents a floating IP and the server/ip it should be associated with
        @param name: logical name for the floating ip
        @param server: string with a Openstack server id, a reference to an
            Actuator L{Server} object, or a callable that that takes a CallContext
            and returns either an Openstack server id string or a L{Server} ref
            object. If a reference, most likely a context expression such as:
            'ctxt.model.some_server'
        @param associated_ip: string containing an IP on the server to associate
            with the floating ip, a reference to address attribute on the server,
            or a callable that takes an L{actuator.modeling.CallContext}
            returns one of the above. If a reference, most likely context expression
            such as 'ctxt.model.some_server.iface0.addr0'. Regardless of the
            means it is provided, the IP address must be one of the server named
            in the 'server' argument.
        @keyword pool: optional; string name of the pool to allocate the IP from,
            or a callable that returns a string with this name. Only optional if
            there is a default pool.
        """
        super(FloatingIP, self).__init__(name, **kwargs)
        self._server = server
        self.server = None
        self._associated_ip = associated_ip
        self.associated_ip = None
        self._pool = pool
        self.pool = None
        self.ip = None
        
    def _get_attrs_dict(self):
        d = super(FloatingIP, self)._get_attrs_dict()
        d.update({"server": self.server,
                  "associated_ip": self.associated_ip,
                  "pool": self.pool,
                  "ip": self.ip})
        return d
        
    def get_ip(self, context=None):
        """
        Return the IP for this floating ip resource.
        """
        return self.ip

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip) if self.ip is not None else None
        
    def _fix_arguments(self, provisioner=None):
        super(FloatingIP, self)._fix_arguments()
        self.server = self._get_arg_value(self._server)
        self.associated_ip = self._get_arg_value(self._associated_ip)
        if self._pool is not None:
            self.pool = self._get_arg_value(self._pool)
        else:
            self.pool = self._pool
        
    def set_addresses(self, ip):
        """
        Used internally. Set the ip address to use for this floating ip.
        """
        self.ip = ip
        
    def get_init_args(self):
        _, kwargs = super(FloatingIP, self).get_init_args()
        kwargs["pool"] = self._pool
        return (self.name, self._server, self._associated_ip), kwargs
    
    
class Router(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack router
    
    For details see:
    http://docs.openstack.org/user-guide/content/sdk_neutron_apis.html#create-router-add-port-to-subnet
    """
    def __init__(self, name, admin_state_up=True, **kwargs):
        """
        @param name: string; logical name for the router
        @param admin_state_up: optional; True or False depending on whether
        or not the state of the router should be considered 'up'. Default is
        True, or the router is up.
        """
        super(Router, self).__init__(name, **kwargs)
        self._admin_state_up = admin_state_up
        self.admin_state_up = None
        
    def _get_attrs_dict(self):
        d = super(Router, self)._get_attrs_dict()
        d["admin_state_up"] = self.admin_state_up
        return d
        
    def _fix_arguments(self, provisioner=None):
        super(Router, self)._fix_arguments()
        self.admin_state_up = self._get_arg_value(self._admin_state_up)
        
    def get_init_args(self):
        _, kwargs = super(Router, self).get_init_args()
        kwargs["admin_state_up"] = self._admin_state_up
        return (self.name,), kwargs
    
    
class RouterGateway(_OpenstackProvisionableInfraResource):
    """
    Represents an Openstack RouterGateway, which provides the path to the
    world.
    
    This resource uses references to Actuator L{Router}s for arguments instead
    of the OS id of the router.
    
    For more details, see:
    
    """
    def __init__(self, name, router, external_network_name, **kwargs):
        """
        @param name: string; logical name that will be used for the gateway
        @param router: a string with Openstack id of a router, a reference to
            to an Actuator L{Router} or a callable that that takes an
            L{actuator.modeling.CallContext} annd yields either of the above.
            If a reference, most likely a context expression, such as:
            'ctxt.model.router'
        @param external_network_name: string; the name of the external network to 
                connect the router to. Will depend on your Openstack provider.
        """
        super(RouterGateway, self).__init__(name, **kwargs)
        self._router = router
        self.router = None
        self._external_network_name = external_network_name
        self.external_network_name = None
        
    def _get_attrs_dict(self):
        d = super(RouterGateway, self)._get_attrs_dict()
        d.update({"router": self.router,
                  "external_network_name": self.external_network_name})
        return d
        
    def _fix_arguments(self, provisioner=None):
        super(RouterGateway, self)._fix_arguments()
        self.router = self._get_arg_value(self._router)
        self.external_network_name = self._get_arg_value(self._external_network_name)
        
    def get_router(self):
        """
        Return the router for this gateway. If the router hasn't been fixed,
        return the 'unfixed' value for the router.
        """
        return self.router if self.router is not None else self._router
    
    def get_external_network_name(self):
        """
        Returns the external network name. If the network name hasn't been
        fixed yet, return the unfixed network parameter.
        """
        return self.external_network_name if self.external_network_name is not None else self._external_network_name
    
    def get_init_args(self):
        _, kwargs = super(RouterGateway, self).get_init_args()
        return (self.name, self._router, self._external_network_name), kwargs
    
    
class RouterInterface(_OpenstackProvisionableInfraResource):
    """
    Represents and Openstack router interface, which associates a router with
    a subnet.
    
    Can use both Openstack ids for the required arguments as well as references
    to Actuator objects.
    """
    def __init__(self, name, router, subnet, **kwargs):
        """
        @param name: string; logical name for the interface
        @param router: a string with an Openstack router id, an Actuator reference
            to a L{Router}, or callable that takes an L{actuator.modeling.CallContext}
            and yields one of thhe above. If a reference, most likely a context
            expression such as 'ctxt.model.router'.
        @param subnet: a string witth an Openstack subnet id, an Actuator
            reference to a L{Subnet} object, or a callable that takes an
            L{actuator.modeling.CallContext} and returns one of the above.
            If a reference, most likely a context expression such as
            'ctxt.model.subnet'.
        """
        super(RouterInterface, self).__init__(name, **kwargs)
        self._router = router
        self.router = None
        self._subnet = subnet
        self.subnet = None
        
    def _get_attrs_dict(self):
        d = super(RouterInterface, self)._get_attrs_dict()
        d["router"] = self.router
        d["subnet"] = self.subnet
        return d
        
    def _fix_arguments(self, provisioner=None):
        super(RouterInterface, self)._fix_arguments()
        self.router = self._get_arg_value(self._router)
        self.subnet = self._get_arg_value(self._subnet)
        return self
        
    def get_router(self):
        """
        Return the router used; if the args haven't been fixed, return
        the unfixed argument for the router
        """
        return self.router if self.router is not None else self._router
    
    def get_subnet(self):
        """
        Returnn the subnet used; if the args haven't been fixed, return the
        unfixed argument for the subnet.
        """
        return self.subnet if self.subnet is not None else self._subnet
    
    def get_init_args(self):
        _, kwargs = super(RouterInterface, self).get_init_args()
        return (self.name, self._router, self._subnet), kwargs
    

class KeyPair(_OpenstackProvisionableInfraResource):
    """
    This class represents an Openstack Keypair. More specifically, it represents
    the public side of a keypair.
    
    It allows you to put a public key on Openstack for subsequent use in other
    resources.
    
    NOTE: Since KeyPairs have the semantic of not always overwriting existing
        public keys, they likewise won't de-provision them when the infra
        is de-provisioned.
    """
    def __init__(self, name, priv_key_name, os_name=None, pub_key_file=None,
                 pub_key=None, force=False, **kwargs):
        """
        Creates a KeyPair resource. It allows you to bind a private key name
        to a public key, either the actual key or the path to a file where the
        key is stored.
        
        @param name: Actuator name of the KeyPair
        @param priv_key_name: A string or a callable that takes an 
            L{actuator.modeling.CallContext} and returns a string; this is the
            name of the private key that matches with the public key that is going
            into Openstack. This value has nothing to do with provisioning; it's
            simply there to allow private key names to be mapped to public keys
            in the model easily
        @param os_name: optional; a string or a callable that takes an
            L{actuator.modeling.CallContext} and returns a string. This is the
            name that will be supplied to Openstack for the key. This differs
            from the 'name' parameter in that this name is fixed; the actual
            value for 'name' may get mangled if the KeyPair the template in
            a L{actuator.infra.MultiResource}. This name will never get touched.
            However, be aware that if you have more than one instance of this
            resource they will all have this same name. If not supplied, then
            the value of the 'name' parameter is used to name the key in OpenStack.
            The default None; the 'name' parameter will be used.
        @param pub_key_file: optional; a string or a callable that takes an
            L{actuator.modeling.CallContext} and returns a string. This is the
            path to the public key file to send to OpenStack. This path must
            be visible and the file must have read perms. Only one of pub_key_file
            or pub_key *must* be specified. The default is None; the resource
            will look for a pub_key parameter.
        @param pub_key: optional; a string or a callable that takes an
            L{actuator.modeling.CallContext} and returns a string. This is the
            actual public key to send to OpenStack. Only one of pub_key or
            pub_key_file *must* be specified. The default is None; the resource
            will look for a pub_key_file parameter.
        @param force: optional; boolean, or a callable that takes an
            L{actuator.modeling.CallContext} and returns a boolean. This
            indicates what to do at provisioning time if they key already
            exists; if set to True and the key exists, then the existing key is
            first deleted before the supplied key is sent to OpenStack. If False
            and the key exists, then nothing more is done and provisioning is
            considered complete. Default is False, do not force sending the
            key.
        """
        super(KeyPair, self).__init__(name, **kwargs)
        self.priv_key_name = None
        self._priv_key_name = priv_key_name
        self.os_name = None
        self._os_name = os_name
        self.pub_key_file = None
        self._pub_key_file = pub_key_file
        self.pub_key = None
        self._pub_key = pub_key
        self.force = None
        self._force = force
        if self._pub_key is None and self._pub_key_file is None:
            raise ProvisionerException("KeyPair %s must be supplied with either "
                                       "a pub_key_file or pub_key argument" % name)
        if self._pub_key is not None and self._pub_key_file is not None:
            raise ProvisionerException("KeyPair %s with only one of "
                                       "pub_key_file or pub_key" % name)
            
    def get_key_name(self):
        return self.name if self.os_name is None else self.os_name
    
    def _get_attrs_dict(self):
        d = super(KeyPair, self)._get_attrs_dict()
        d.update({"priv_key_name": self.priv_key_name,
                  "os_name": self.os_name,
                  "pub_key_file": self.pub_key_file,
                  "pub_key": self.pub_key,
                  "force": self.force})
        return d
        
    def _fix_arguments(self, provisioner=None):
        super(KeyPair, self)._fix_arguments()
        self.priv_key_name = self._get_arg_value(self._priv_key_name)
        self.os_name = self._get_arg_value(self._os_name)
        self.pub_key_file = self._get_arg_value(self._pub_key_file)
        self.pub_key = self._get_arg_value(self._pub_key)
        self.force = self._get_arg_value(self._force)
        
    def get_init_args(self):
        __doc__ = _OpenstackProvisionableInfraResource.get_init_args.__doc__
        _, kwargs = super(KeyPair, self).get_init_args()
        kwargs.update({"os_name": self._os_name,
                       "pub_key_file": self._pub_key_file,
                       "pub_key": self._pub_key,
                       "force": self._force})
        return (self.name, self._priv_key_name), kwargs
