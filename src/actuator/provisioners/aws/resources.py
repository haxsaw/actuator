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

from collections import Iterable
from uuid import uuid4

from actuator.infra import IPAddressable
from actuator.provisioners.core import Provisionable, ProvisionerException


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
    def __init__(self, name, *args, ensure_unique=False, public_key_file=None,
                 retain_on_reverse=False, **kwargs):
        """
        makes a KeyPair resource that can either refer to an existing key pair or define a new one

        A KeyPair can:
        - name an existing key pair on AWS for which the private key is already held
        - name a new key pair to be created on AWS for which the private key will be created and downloaded
        - use an existing public/private key pair, uploading the public key to AWS and using the private
          key already held

        Additionally, a key pair on AWS can be created such that it won't be deleted upon reversal, so that
        the pair can be left while the other resources are deleted/released

        If ensure_unique is False (the default), the named key pair is looked up on AWS first to see if it exists.
        If it does, then that key pair is used and it is assumed the the client has access to the private
        key. Key pairs that are found are not deleted during system teardown.

        If ensure_unique is True or if the named key doesn't exist on AWS, then the AWS key pair is created
        and the private key is acquired from AWS. This private key can be used in configuration models
        to remotely run commands on hosts that use this key.

        :param name: both model name for the key pair and the AWS name
        :param ensure_unique: bool, optional. If True, append a random suffix to the name to ensure
            uniqueness at AWS, and hence force the creation of a key pair there.
        :param public_key_file: string, optional. Path to a file containing the public key for the
            AWS key with the name 'name'. You can't supply a public_key_file if the key already exists;
            this will raise an error during provisioning (standup).
        :param retain_on_reverse: bool, optional. Default False. If True, the key pair is left behind
            on AWS when the resource is deprovisioned. NOTE: this will be set to True internally in
            the case that the key already exists on AWS-- pre-existing keys will not be be deleted on
            system teardown.
        """
        super(KeyPair, self).__init__(name, *args, **kwargs)
        self.ensure_unique = None
        self._ensure_unique = ensure_unique
        self.public_key_file = None
        self._public_key_file = public_key_file
        self.retain_on_reverse = None
        self._retain_on_reverse = retain_on_reverse
        self.key_material = None
        self.aws_name = None

    def get_init_args(self):
        args, kwargs = super(KeyPair, self).get_init_args()
        kwargs.update({"ensure_unique": self._ensure_unique,
                       "public_key_file": self._public_key_file,
                       "retain_on_reverse": self._retain_on_reverse})
        return args, kwargs

    def _fix_arguments(self):
        super(KeyPair, self)._fix_arguments()
        self.ensure_unique = bool(self._get_arg_value(self._ensure_unique))
        self.public_key_file = self._get_arg_value(self._public_key_file)
        self.retain_on_reverse = self._get_arg_value(self._retain_on_reverse)
        if self.ensure_unique:
            self.aws_name = "{}-{}".format(self.name, str(uuid4()))
        else:
            self.aws_name = self.name

    def _get_attrs_dict(self):
        d = super(KeyPair, self)._get_attrs_dict()
        d["ensure_unique"] = self.ensure_unique
        d.update({"ensure_unique": self.ensure_unique,
                  "public_key_file": self.public_key_file,
                  "retain_on_reverse": self.retain_on_reverse,
                  "key_material": self.key_material,
                  "aws_name": self.aws_name})
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
    def __init__(self, name, cidr_block, vpc, *args, availability_zone="", ipv6_cidr_block="", **kwargs):
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
    def __init__(self, name, route_table, *args, dest_cidr_block=None, dest_ipv6_cidr_block=None, gateway=None,
                 egress_only_gateway=None, nat_instance=None, nat_gateway=None, network_interface=None,
                 peering_connection=None, **kwargs):
        """
        create a route that can be used in multiple routing tables

        :param name: model name for the route
        :param route_table: the L{RouteTable} the rule is to be applied to. This can be an actual instance
            of a L{RouteTable}, or a model reference or context expression that leads to a L{RouteTable}
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
        self.route_table = None
        self._route_table = route_table
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
        args += (self._route_table,)
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
        self.route_table = self._get_arg_value(self._route_table)
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
        d.update({"route_table": self.route_table,
                  "dest_cidr_block": self.dest_cidr_block,
                  "dest_ipv6_cidr_block": self.dest_ipv6_cidr_block,
                  "gateway": self.gateway,
                  "egress_only_gateway": self.egress_only_gateway,
                  "nat_instance": self.nat_instance,
                  "nat_gateway": self.nat_gateway,
                  "network_interface": self.network_interface,
                  "peering_connection": self.peering_connection})
        return d


class RouteTable(AWSProvisionableInfraResource):
    def __init__(self, name, vpc, subnet, *args, **kwargs):
        """
        Create a routing table with the identified routes
        :param name: model name for the table
        :param vpc: the VPC the table is to be associated with
        :param subnet: the subnet the table is to be associated with
        """
        super(RouteTable, self).__init__(name, *args, **kwargs)
        self.vpc = None
        self._vpc = vpc
        self.subnet = None
        self._subnet = subnet
        self.association_id = None

    def get_init_args(self):
        args, kwargs = super(RouteTable, self).get_init_args()
        args += (self._vpc, self._subnet)
        return args, kwargs

    def _fix_arguments(self):
        super(RouteTable, self)._fix_arguments()
        self.vpc = self._get_arg_value(self._vpc)
        self.subnet = self._get_arg_value(self._subnet)

    def _get_attrs_dict(self):
        d = super(RouteTable, self)._get_attrs_dict()
        d["vpc"] = self.vpc
        d["subnet"] = self.subnet
        d["association_id"] = self.association_id
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
        self.private_ip_addresses = None
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


class PublicIP(AWSProvisionableInfraResource, IPAddressable):
    def __init__(self, name, *args, domain="vpc", public_ipv4_pool=None, address=None,
                 instance=None, network_interface=None, private_ip_address=None, **kwargs):
        """
        create a new publicly available elastic IP that can be associated with a private IP

        :param name: model name of the elastic ip
        :param domain: string, optional. One of 'standard' or 'vpc'. Default is 'vpc'
        :param public_ipv4_pool: string, optional id of an address pool owned by the caller.
            EC2 will select an address from the pool.
        :param address: string, optional. allows the caller to specify a particular public ip.
            can't be used with public_ipv4_pool
        :param instance: L{AWSInstance}, optional. Either an actual L{AWSInstance}, or a model
            reference or context expression that leads to an AWSInstance. One of instance,
            network_interface, or private_ip_address must be provided.
        :param network_interface: L{NetworkInterface}, optional. Either an L{NetworkInterface},
            or a model reference or context expression that leads to a NetworkInterface. One of
            instance, network_interface, or private_ip_address must be provided.
        :param private_ip_address: string, optional. private IP to associate the public ip with.
            One of instance, network_interface, or private_ip_address must be provided.
        """
        super(PublicIP, self).__init__(name, *args, **kwargs)
        if sum([instance is not None and 1,
               network_interface is not None and 1,
               private_ip_address is not None and 1]) != 1:
            raise ProvisionerException("You must specify exactly one of instance, network_interface "
                                       "or private_ip_address")
        if public_ipv4_pool and address:
            raise ProvisionerException("You can only specify one of address or public_ipv4_pool")
        self.domain = None
        self._domain = domain
        self.public_ipv4_pool = None
        self._public_ipv4_pool = public_ipv4_pool
        self.address = None
        self._address = address
        self.instance = None
        self._instance = instance
        self.network_interface = None
        self._network_interface = network_interface
        self.private_ip_address = None
        self._private_ip_address = private_ip_address
        self.ip_address = None
        self.association_id = None

    def get_init_args(self):
        args, kwargs = super(PublicIP, self).get_init_args()
        kwargs.update({"domain": self._domain,
                       "public_ipv4_pool": self._public_ipv4_pool,
                       "address": self._address,
                       "instance": self._instance,
                       "network_interface": self._network_interface,
                       "private_ip_address": self._private_ip_address})
        return args, kwargs

    def _fix_arguments(self):
        super(PublicIP, self)._fix_arguments()
        self.domain = self._get_arg_value(self._domain)
        self.public_ipv4_pool = self._get_arg_value(self._public_ipv4_pool)
        self.address = self._get_arg_value(self._address)
        self.instance = self._get_arg_value(self._instance)
        self.network_interface = self._get_arg_value(self._network_interface)
        self.private_ip_address = self._get_arg_value(self._private_ip_address)

    def _get_attrs_dict(self):
        d = super(PublicIP, self)._get_attrs_dict()
        d.update({"domain": self.domain,
                  "public_ipv4_pool": self.public_ipv4_pool,
                  "address": self.address,
                  "instance": self.instance,
                  "network_interface": self.network_interface,
                  "private_ip_address": self.private_ip_address,
                  "ip_address": self.ip_address,
                  "association_id": self.association_id})
        return d

    def get_ip(self, context=None):
        return self.ip_address

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip_address)


class AWSInstance(AWSProvisionableInfraResource, IPAddressable):
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
        super(AWSInstance, self).__init__(name, *args, **kwargs)
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
        self.ip_address = None

    def get_init_args(self):
        args, kwargs = super(AWSInstance, self).get_init_args()
        args += (self._image_id,)
        kwargs.update({"instance_type": self._instance_type,
                       "key_pair": self._key_pair,
                       "sec_groups": self._sec_groups,
                       "subnet": self._subnet,
                       "network_interfaces": self._network_interfaces})
        return args, kwargs

    def _fix_arguments(self):
        super(AWSInstance, self)._fix_arguments()
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
        d = super(AWSInstance, self)._get_attrs_dict()
        d.update({"image_id": self.image_id,
                  "instance_type": self.instance_type,
                  "key_pair": self.key_pair,
                  "sec_groups": self.sec_groups,
                  "subnet": self.subnet,
                  "network_interfaces": self.network_interfaces,
                  "ip_address": self.ip_address})
        return d

    def get_ip(self, context=None):
        return self.ip_address

    def get_cidr4(self, *_):
        return "{}/32".format(self.ip_address)
