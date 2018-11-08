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

from actuator.provisioners.core import ProvisioningTask
from actuator.provisioners.aws.resources import *
# from actuator.provisioners.aws import AWSRunContext
from actuator.utils import capture_mapping

_aws_domain = "AWS_DOMAIN"


@capture_mapping(_aws_domain, VPC)
class VPCTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, VPC)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        vpc = ec2.create_vpc(CidrBlock=rsrc.cidr_block,
                             AmazonProvidedIpv6CidrBlock=rsrc.amazon_provided_ipv6_cidr_block,
                             InstanceTenancy=rsrc.instance_tenancy)
        vpc.wait_until_exists()
        rsrc.aws_id = vpc.vpc_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, VPC)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        vpc = ec2.Vpc(rsrc.aws_id)
        vpc.delete()


@capture_mapping(_aws_domain, KeyPair)
class KeyPairTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, KeyPair)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        kp = ec2.create_key_pair(KeyName=rsrc.name)

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, KeyPair)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        kp = ec2.KeyPair(rsrc.name)
        kp.delete()


@capture_mapping(_aws_domain, SecurityGroup)
class SecurityGroupTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, SecurityGroup)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        sg = ec2.create_security_group(Description=rsrc.description,
                                       GroupName=rsrc.name,
                                       VpcId=rsrc.vpc.aws_id)
        rsrc.aws_id = sg.group_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, SecurityGroup)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        sg = ec2.SecurityGroup(rsrc.aws_id)
        sg.delete()


@capture_mapping(_aws_domain, SecurityGroupRule)
class SecurityGroupRuleTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, SecurityGroupRule)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        sg = ec2.SecurityGroup(rsrc.security_group.aws_id)
        if rsrc.kind == "ingress":
            sg.authorize_ingress(CidrIp=rsrc.cidrip,
                                 FromPort=rsrc.from_port,
                                 ToPort=rsrc.to_port,
                                 IpProtocol=rsrc.ip_protocol)
        elif rsrc.kind == "egress":
            sg.authorize_egress(CidrIp=rsrc.cidrip,
                                FromPort=rsrc.from_port,
                                ToPort=rsrc.to_port,
                                IpProtocol=rsrc.ip_protocol)

    def _reverse(self, proxy):
        pass


@capture_mapping(_aws_domain, Subnet)
class SubnetTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, Subnet)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        args = dict(AvailabilityZone=rsrc.availability_zone,
                    CidrBlock=rsrc.cidr_block,
                    VpcId=rsrc.vpc.aws_id)
        if rsrc.ipv6_cidr_block:
            args["Ipv6CidrBlock"] = rsrc.ipv6_cidr_block
        sn = ec2.create_subnet(**args)
        rsrc.aws_id = sn.subnet_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, Subnet)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        sn = ec2.Subnet(rsrc.aws_id)
        sn.delete()


@capture_mapping(_aws_domain, InternetGateway)
class InternetGatewayTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, InternetGateway)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.aws_id is None:
            gw = ec2.create_internet_gateway()
            rsrc.aws_id = gw.internet_gateway_id
        vpc = ec2.Vpc(rsrc.vpc.aws_id)
        vpc.attach_internet_gateway(InternetGatewayId=rsrc.aws_id )

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, InternetGateway)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        gw = ec2.InternetGateway(rsrc.aws_id)
        vpc = ec2.Vpc(rsrc.vpc.aws_id)
        vpc.detach_internet_gateway(InternetGatewayId=rsrc.aws_id)
        gw.delete()


@capture_mapping(_aws_domain, RouteTable)
class RouteTableTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, RouteTable)
        if rsrc.aws_id is None:
            ec2 = run_context.ec2(region_name=rsrc.cloud)
            rt = ec2.create_route_table(VpcId=rsrc.vpc.aws_id)
            rsrc.aws_id = rt.route_table_id
        rta = rt.associate_with_subnet(SubnetId=rsrc.subnet.aws_id)
        rsrc.association_id = rta.route_table_association_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, RouteTable)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.association_id is not None:
            ec2.disassociate_route_table(AssociationId=rsrc.association_id)
            rsrc.association_id = None
        rt = ec2.RouteTable(rsrc.aws_id)
        rt.delete()
