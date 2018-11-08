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

from errator import narrate
from collections import Iterable

from actuator.infra import IPAddressable
from actuator.provisioners.core import Provisionable, ProvisionerException
from actuator.utils import _Persistable


class AWSProvisionableInfraResource(Provisionable):
    def __init__(self, name, *args, **kwargs):
        super(AWSProvisionableInfraResource, self).__init__(name, *args, **kwargs)
        self.aws_id = None

    def _get_attrs_dict(self):
        d = super(AWSProvisionableInfraResource, self)._get_attrs_dict()
        d["aws_id"] = self.aws_id
        return d


class VPC(AWSProvisionableInfraResource):
    def __init__(self, name, cidr_block, *args, amazon_provided_ipv6_cidr_block=False,
                 instance_tenancy="default", **kwargs):
        """
        Create an AWS VPC
        :param name: string; name to use for the vpc in the model
        :param cidr_block: string; an IPv4 CIDR string that specifies the network address range for the vpc
        :param amazon_provided_ipv6_cidr_block: optional boolean, default False. If True, requests Amazon supply a
            /56 IPv6 CIDR block.
        :param instance_tenancy: optional string, default 'default'. If 'default', indicates are launched as
            shared tenancy by default, but may have any tenancy specified for a specific instance.
            May also be 'dedicated', instances are launched as dedicated by default, and only dedicated
            instances may run in a dedicated vpc
        """
        super(VPC, self).__init__(name, *args, **kwargs)
        self.cidr_block = None
        self._cidr_block = cidr_block
        self.amazon_provided_ipv6_cidr_block = None
        self._amazon_provided_ipv6_cidr_block = amazon_provided_ipv6_cidr_block
        self.instance_tenancy = None
        self._instance_tenancy = instance_tenancy

    def get_init_args(self):
        args, kwargs = super(VPC, self).get_init_args()
        args += (self._cidr_block,)
        kwargs.update({"amazon_provided_ipv6_cidr_block": self._amazon_provided_ipv6_cidr_block,
                       "instance_tenancy": self._instance_tenancy})
        return args, kwargs

    def _fix_arguments(self):
        super(VPC, self)._fix_arguments()
        self.cidr_block = self._get_arg_value(self._cidr_block)
        self.amazon_provided_ipv6_cidr_block = self._get_arg_value(self._amazon_provided_ipv6_cidr_block)
        self.instance_tenancy = self._get_arg_value(self._instance_tenancy)

    def _get_attrs_dict(self):
        d = super(VPC, self)._get_attrs_dict()
        d["cidr_block"] = self.cidr_block
        d["amazon_provided_ipv6_cidr_block"] = self.amazon_provided_ipv6_cidr_block
        d["instance_tenancy"] = self.instance_tenancy
        return d


class SecurityGroup(AWSProvisionableInfraResource):
    def __init__(self, name, description, vpc, *args, **kwargs):
        super(SecurityGroup, self).__init__(name, *args, **kwargs)
        self.description = None
        self._description = description
        self.vpc = None
        self._vpc = vpc

    def get_init_args(self):
        args, kwargs = super(SecurityGroup, self).get_init_args()
        args += (self._description, self._vpc)
        return args, kwargs

    def _fix_arguments(self):
        super(SecurityGroup, self)._fix_arguments()
        self.description = self._get_arg_value(self._description)
        self.vpc = self._get_arg_value(self._vpc)

    def _get_attrs_dict(self):
        d = super(SecurityGroup, self)._get_attrs_dict()
        d["description"] = self.description
        d["vpc"] = self.vpc
        return d


class KeyPair(AWSProvisionableInfraResource):
    def __init__(self, name, *args, ensure_unique=False, **kwargs):
        super(KeyPair, self).__init__(name, *args, **kwargs)
        self.ensure_unique = None
        self._ensure_unique = ensure_unique

    def get_init_args(self):
        args, kwargs = super(KeyPair, self).get_init_args()
        kwargs["ensure_unique"] = self._ensure_unique
        return args, kwargs

    def _fix_arguments(self):
        super(KeyPair, self)._fix_arguments()
        self.ensure_unique = bool(self._get_arg_value(self._ensure_unique))

    def _get_attrs_dict(self):
        d = super(KeyPair, self)._get_attrs_dict()
        d["ensure_unique"] = self.ensure_unique
        return d


class SecurityGroupRule(AWSProvisionableInfraResource):
    def __init__(self, name, security_group, kind, cidrip, from_port, to_port, ip_protocol, *args, **kwargs):
        """
        Create a rule on the named security group
        :param name: string; name of the group. The final name will be the full model path to the rule
        :param security_group: a SecurityGroup, a model reference to a security group, or a context expression that
            refers to a SecurityGroup
        :param kind: string; one of 'ingress' or 'egress'
        :param cidrip: the CIDR that the rule is to be applied to
        :param from_port: beginning port in a range to apply the rule
        :param to_port: ending port in a range to applye rule; if only one port, then from_port and to_port
            should be the same
        :param ip_protocol: string; one of tcp|udp|icmp|58|-1. Use -1 to specify all protocols
        """
        super(SecurityGroupRule, self).__init__(name, *args, **kwargs)
        if kind not in ('ingress', 'egress'):
            raise ProvisionerException("kind must be one of 'ingress' or 'egress'")
        self.kind = kind
        self.cidrip = None
        self._cidrip = cidrip
        self.from_port = None
        self._from_port = from_port
        self.to_port = None
        self._to_port = to_port
        self.ip_protocol = None
        self._ip_protocol = ip_protocol
        self.security_group = None
        self._security_group = security_group

    def get_init_args(self):
        args, kwargs = super(SecurityGroupRule, self).get_init_args()
        args += (self._security_group, self.kind, self._cidrip, self._from_port, self._to_port, self._ip_protocol)
        return args, kwargs

    def _fix_arguments(self):
        super(SecurityGroupRule, self)._fix_arguments()
        self.security_group = self._get_arg_value(self._security_group)
        self.cidrip = self._get_arg_value(self._cidrip)
        self.from_port = self._get_arg_value(self._from_port)
        self.to_port = self._get_arg_value(self._to_port)
        self.ip_protocol = self._get_arg_value(self._ip_protocol)

    def _get_attrs_dict(self):
        d = super(SecurityGroupRule, self)._get_attrs_dict()
        d["security_group"] = self.security_group
        d["kind"] = self.kind
        d["cidrip"] = self.cidrip
        d["from_port"] = self.from_port
        d["to_port"] = self.to_port
        d["ip_protocol"] = self.ip_protocol
        return d


class Subnet(AWSProvisionableInfraResource):
    def __init__(self, name, cidr_block, vpc, *args, availability_zone=None, ipv6_cidr_block=None, **kwargs):
        """
        Create a new subnet on a vpc.

        :param name: model name for the subnet resource
        :param cidr_block: string; a IPv4 CIDR block. This can be the same size as the VPC CIDR block, or a
            subset of the CIDR block for the VPC. If there are multiple subnets for the VPC they must not
            overlap
        :param vpc: either a VPC instance, a model reference to a VPC, or a context expression that leads to
            a VPC.
        :param availability_zone: string, optional. If not specified, AWS will assign an availability zone,
            ottherwise it will use the specified availability zone
        :param ipv6_cidr_block: string, optional. Can be supplied if the VPC was set up as IPv6.
        """
        super(Subnet, self).__init__(name, *args, **kwargs)
        self.cidr_block = None
        self._cidr_block = cidr_block
        self.vpc = None
        self._vpc = vpc
        self.availability_zone = None
        self._availability_zone = availability_zone
        self.ipv6_cidr_block = None
        self._ipv6_cidr_block = ipv6_cidr_block

    def get_init_args(self):
        args, kwargs = super(Subnet, self).get_init_args()
        args += (self._cidr_block, self._vpc)
        kwargs["availability_zone"] = self._availability_zone
        kwargs["ipv6_cidr_block"] = self._ipv6_cidr_block
        return args, kwargs

    def _fix_arguments(self):
        super(Subnet, self)._fix_arguments()
        self.cidr_block = self._get_arg_value(self._cidr_block)
        self.vpc = self._get_arg_value(self._vpc)
        self.availability_zone = self._get_arg_value(self._availability_zone)
        self.ipv6_cidr_block = self._get_arg_value(self._ipv6_cidr_block)

    def _get_attrs_dict(self):
        d = super(Subnet, self)._get_attrs_dict()
        d["cidr_block"] = self.cidr_block
        d["vpc"] = self.vpc
        d["availability_zone"] = self.availability_zone
        d["ipv6_cidr_block"] = self.ipv6_cidr_block
        return d


class InternetGateway(AWSProvisionableInfraResource):
    def __init__(self, name, vpc, *args, **kwargs):
        """
        Create a new internet gateway to be used for a particular VPC
        :param name: model name of the gateway
        :param vpc: the VPC to attach the gatweway to
        """
        super(InternetGateway, self).__init__(name, *args, **kwargs)
        self.vpc = None
        self._vpc = vpc

    def get_init_args(self):
        args, kwargs = super(InternetGateway, self).get_init_args()
        args += (self._vpc,)
        return args, kwargs

    def _fix_arguments(self):
        super(InternetGateway, self)._fix_arguments()
        self.vpc = self._get_arg_value(self._vpc)

    def _get_attrs_dict(self):
        d = super(InternetGateway, self)._get_attrs_dict()
        d["vpc"] = self.vpc
        return d


class Route(AWSProvisionableInfraResource):
    def __init__(self, name, *args, dest_cidr_block=None, dest_ipv6_cidr_block=None, gateway=None,
                 egress_only_gateway=None, nat_instance=None, nat_gateway=None, network_interface=None,
                 peering_connection=None, **kwargs):
        """
        create a route that can be used in multiple routing tables

        :param name: model name for the route
        :param dest_cidr_block: string, optional. IPv4 destination CIDR
        :param dest_ipv6_cidr_block: string, optional. IPv6 destination CIDR
        :param gateway: optional InternetGateway. Can be an actual instance, a model reference, or a context
            expression that leads to an InternetGateway
        :param egress_only_gateway: optional egress-only L{InternetGateway}; IPv6 traffic only. Can be an actual instance,
            a model reference, or a context expression that leads to an L{InternetGateway}
        :param nat_instance: optional; a NAT instance in the VPC
        :param nat_gateway: a NAT gateway
        :param network_interface: optional; a NetworkInterface. Can be an actual instance, model reference, or
            context expression that leads to a L{NetworkInterface}
        :param peering_connection: unused
        """
        super(Route, self).__init__(name, *args, **kwargs)
        self.dest_cidr_block = None
        self._dest_cidr_block = dest_cidr_block
        self.dest_ipv6_cidr_block = None
        self._dest_ipv6_cidr_block = dest_ipv6_cidr_block
        self.gateway = None
        self._gateway = gateway
        self.egress_only_gateway = None
        self._egress_only_gateway = egress_only_gateway
        self.nat_instance = None
        self._nat_instance = nat_instance
        self.nat_gateway = None
        self._nat_gateway = nat_gateway
        self.network_interface = None
        self._network_interface = network_interface
        self.peering_connection = None
        self._peering_connection = peering_connection

    def get_init_args(self):
        args, kwargs = super(Route, self).get_init_args()
        kwargs.update({"dest_cidr_block": self._dest_cidr_block,
                       "dest_ipv6_cidr_block": self._dest_ipv6_cidr_block,
                       "gateway": self._gateway,
                       "egress_only_gateway": self._egress_only_gateway,
                       "nat_instance": self._nat_instance,
                       "nat_gateway": self._nat_gateway,
                       "network_interface": self._network_interface,
                       "peering_connection": self._peering_connection})
        return args, kwargs

    def _fix_arguments(self):
        super(Route, self)._fix_arguments()
        self.dest_cidr_block = self._get_arg_value(self._dest_cidr_block)
        self.dest_ipv6_cidr_block = self._get_arg_value(self._dest_ipv6_cidr_block)
        self.gateway = self._get_arg_value(self._gateway)
        self.egress_only_gateway = self._get_arg_value(self._egress_only_gateway)
        self.nat_instance = self._get_arg_value(self._nat_instance)
        self.nat_gateway = self._get_arg_value(self._nat_gateway)
        self.network_interface = self._get_arg_value(self._network_interface)
        self.peering_connection = self._get_arg_value(self._peering_connection)

    def _get_attrs_dict(self):
        d = super(Route, self)._get_attrs_dict()
        d.update({"dest_cidr_block": self.dest_cidr_block,
                  "dest_ipv6_cidr_block": self.dest_ipv6_cidr_block,
                  "gateway": self.gateway,
                  "egress_only_gateway": self.egress_only_gateway,
                  "nat_instance": self.nat_instance,
                  "nat_gateway": self.nat_gateway,
                  "network_interface": self.network_interface,
                  "peering_connection": self.peering_connection})
        return d


class RouteTable(AWSProvisionableInfraResource):
    def __init__(self, name, vpc, subnet, routes, *args, **kwargs):
        """
        Create a routing table with the identified routes
        :param name: model name for the table
        :param vpc: the VPC the table is to be associated with
        :param subnet: the subnet the table is to be associated with
        :param routes: a sequence of L{Route} s; the sequence can contain actual L{Route} instances,
            model references, or context expressions for L{Route} instances
        """
        super(RouteTable, self).__init__(name, *args, **kwargs)
        self.vpc = None
        self._vpc = vpc
        self.subnet = None
        self._subnet = subnet
        self.routes = None
        self._routes = routes

    def get_init_args(self):
        args, kwargs = super(RouteTable, self).get_init_args()
        args += (self._vpc, self._subnet, self._routes)
        return args, kwargs

    def _fix_arguments(self):
        super(RouteTable, self)._fix_arguments()
        self.vpc = self._get_arg_value(self._vpc)
        self.subnet = self._get_arg_value(self._subnet)
        if isinstance(self._routes, Iterable):
            self.routes = [self._get_arg_value(r) for r in self._routes]
        else:
            self.routes = self._get_arg_value(self._routes)

    def _get_attrs_dict(self):
        d = super(RouteTable, self)._get_attrs_dict()
        d["vpc"] = self.vpc
        d["subnet"] = self.subnet
        d["routes"] = self.routes
        return d


class NetworkInterface(AWSProvisionableInfraResource):
    def __init__(self, name, subnet, *args, description="", sec_groups=None, private_ip_address=None,
                 private_ip_addresses=None, **kwargs):
        super(NetworkInterface, self).__init__(name, *args, **kwargs)
        self.subnet = None
        self._subnet = subnet
        self.description = None
        self._description = description
        self.sec_groups = None
        self._sec_groups = sec_groups
        self.private_ip_address = None
        self._private_ip_address = private_ip_address
        self.private_ip_addresses = private_ip_addresses
        self._private_ip_addresses = private_ip_addresses

    def get_init_args(self):
        args, kwargs = super(NetworkInterface, self).get_init_args()
        args += (self._subnet,)
        kwargs.update({"description": self._description,
                       "sec_groups": self._sec_groups,
                       "private_ip_address": self._private_ip_address,
                       "private_ip_addresses": self._private_ip_addresses})
        return args, kwargs

    def _fix_arguments(self):
        super(NetworkInterface, self)._fix_arguments()
        self.subnet = self._get_arg_value(self._subnet)
        self.description = self._get_arg_value(self._description)
        if isinstance(self._sec_groups, Iterable):
            self.sec_groups = [self._get_arg_value(sg) for sg in self._sec_groups]
        else:
            self.sec_groups = self._get_arg_value(self._sec_groups)
        self.private_ip_address = self._get_arg_value(self._private_ip_address)
        self.private_ip_addresses = self._get_arg_value(self._private_ip_addresses)

    def _get_attrs_dict(self):
        d = super(NetworkInterface, self)._get_attrs_dict()
        d.update({"subnet": self.subnet,
                  "description": self.description,
                  "sec_groups": self.sec_groups,
                  "private_ip_address": self.private_ip_address,
                  "private_ip_addresses": self.private_ip_addresses})
        return d


class AWSServer(AWSProvisionableInfraResource):
    def __init__(self, name, image_id, *args, instance_type=None, key_pair=None,
                 sec_groups=None, subnet=None, network_interfaces=None, **kwargs):
        """
        create a new server instance
        :param name: model name of the server; may wind up in the machine too
        :param image_id: string; AMI id of a machine image to start
        :param instance_type: string, optional. defines the type of instance on wihch to run
            the image. The default is 'm1.small'
        :param key_pair: string, optional. the name of a keypair to use to allow access. If not supplied,
            some other remote access arrangements must be available in the image
        :param sec_groups: list; optional. List of SecurityGroups; list elements must either be instances,
            model references, or context expressions that lead to a SecurityGroup
        :param subnet: optional; a L{Subnet} instance, model reference, or context expression for a Subnet
        :param network_interfaces: list, optional. List of NetworkInterfaces to connect to the machine. List
            elements can be NetworkInterface instances, model references, or context expressions that refer
            to a NetworkInterface
        """
        super(AWSServer, self).__init__(name, *args, **kwargs)
        self.image_id = None
        self._image_id = image_id
        self.instance_type = None
        self._instance_type = instance_type
        self.key_pair = None
        self._key_pair = key_pair
        self.sec_groups = None
        self._sec_groups = sec_groups
        self.subnet = None
        self._subnet = subnet
        self.network_interfaces = None
        self._network_interfaces = network_interfaces

    def get_init_args(self):
        args, kwargs = super(AWSServer, self).get_init_args()
        args += (self._image_id,)
        kwargs.update({"instance_type": self._instance_type,
                       "key_pair": self._key_pair,
                       "sec_groups": self._sec_groups,
                       "subnet": self._subnet,
                       "network_interfaces": self._network_interfaces})
        return args, kwargs

    def _fix_arguments(self):
        super(AWSServer, self)._fix_arguments()
        self.image_id = self._get_arg_value(self._image_id)
        self.instance_type = self._get_arg_value(self._instance_type)
        self.key_pair = self._get_arg_value(self._key_pair)
        if isinstance(self._sec_groups, Iterable):
            self.sec_groups = [self._get_arg_value(sg) for sg in self._sec_groups]
        else:
            self.sec_groups = self._get_arg_value(self._sec_groups)
        self.subnet = self._get_arg_value(self._subnet)
        if isinstance(self._network_interfaces, Iterable):
            self.network_interfaces = [self._get_arg_value(ni) for ni in self._network_interfaces]
        else:
            self.network_interfaces = self._get_arg_value(self._network_interfaces)

    def _get_attrs_dict(self):
        d = super(AWSServer, self)._get_attrs_dict()
        d.update({"image_id": self.image_id,
                  "instance_type": self.instance_type,
                  "key_pair": self.key_pair,
                  "sec_groups": self.sec_groups,
                  "subnet": self.subnet,
                  "network_interfaces": self.network_interfaces})
        return d
