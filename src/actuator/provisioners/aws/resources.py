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


from actuator.modeling import ContextExpr
from actuator.infra import Provisionable, IPAddressable
from actuator.provisioners.core import Provisionable, ProvisionerException
from actuator.utils import _Persistable


class _AWSProvisionableInfraResource(Provisionable):
    def __init__(self, name, *args, **kwargs):
        super(_AWSProvisionableInfraResource, self).__init__(name, *args, **kwargs)
        self.aws_id = None

    def _get_attrs_dict(self):
        d = super(_AWSProvisionableInfraResource, self)._get_attrs_dict()
        d["aws_id"] = self.aws_id
        return d


class VPC(_AWSProvisionableInfraResource):
    def __init__(self, name, cidr_block, *args, amazon_provided_ipv6_cidr_block=False,
                 instance_tenancy=None, **kwargs):
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


class SecurityGroup(_AWSProvisionableInfraResource):
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


class KeyPair(_AWSProvisionableInfraResource):
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


class SecurityGroupRule(_AWSProvisionableInfraResource):
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


class Subnet(_AWSProvisionableInfraResource):
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


class InternetGateway(_AWSProvisionableInfraResource):
    def __init__(self, name, *args, **kwargs):
        super(InternetGateway, self).__init__(name, *args, **kwargs)