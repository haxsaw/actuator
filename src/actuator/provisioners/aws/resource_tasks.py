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

import time
from collections import Iterable
from actuator.provisioners.core import ProvisioningTask, ProvisionerException
from actuator.provisioners.aws.resources import *
from actuator.utils import capture_mapping
from botocore.exceptions import ClientError

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
        kp = ec2.KeyPair(rsrc.aws_name)   # set up lookup to see if key already exists
        try:
            _ = kp.key_fingerprint   # this will raise an exception if the key doesn't exist
            if rsrc.public_key_file:
                raise ProvisionerException("KeyPair {} cannot specify a public_key_file for an existing key")
            rsrc.retain_on_reverse = True
        except ClientError as e:
            if "NotFound" not in str(e):
                raise
            if rsrc.public_key_file:
                key_material = open(rsrc.public_key_file, "r").read().encode()
                _ = ec2.import_key_pair(KeyName=rsrc.aws_name, PublicKeyMaterial=key_material)
            else:
                kp = ec2.create_key_pair(KeyName=rsrc.aws_name)
                rsrc.key_material = kp.key_material

    def _reverse(self, proxy):
        rsrc = self.rsrc
        assert isinstance(rsrc, KeyPair)
        if not rsrc.retain_on_reverse:
            run_context = proxy.get_context()
            ec2 = run_context.ec2(region_name=rsrc.cloud)
            kp = ec2.KeyPair(rsrc.aws_name)
            try:
                kp.delete()
            except ClientError as e:
                if "NotFound" not in str(e):
                    raise


@capture_mapping(_aws_domain, SecurityGroup)
class SecurityGroupTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(SecurityGroupTask, self).depends_on_list()
        if isinstance(self.rsrc.vpc, VPC):
            depson.append(self.rsrc.vpc)
        return depson

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
    def depends_on_list(self):
        depson = super(SecurityGroupRuleTask, self).depends_on_list()
        if isinstance(self.rsrc.security_group, SecurityGroup):
            depson.append(self.rsrc.security_group)
        return depson

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
    def depends_on_list(self):
        depson = super(SubnetTask, self).depends_on_list()
        if isinstance(self.rsrc.vpc, VPC):
            depson.append(self.rsrc.vpc)
        return depson

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
    def depends_on_list(self):
        depson = super(InternetGatewayTask, self).depends_on_list()
        if isinstance(self.rsrc.vpc, VPC):
            depson.append(self.rsrc.vpc)
        return depson

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, InternetGateway)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.aws_id is None:
            gw = ec2.create_internet_gateway()
            rsrc.aws_id = gw.internet_gateway_id
        vpc = ec2.Vpc(rsrc.vpc.aws_id)
        vpc.attach_internet_gateway(InternetGatewayId=rsrc.aws_id)

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
    def depends_on_list(self):
        depson = super(RouteTableTask, self).depends_on_list()
        if isinstance(self.rsrc.vpc, VPC):
            depson.append(self.rsrc.vpc)
        if isinstance(self.rsrc.subnet, Subnet):
            depson.append(self.rsrc.subnet)
        return depson

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, RouteTable)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.aws_id is None:
            rt = ec2.create_route_table(VpcId=rsrc.vpc.aws_id)
            rsrc.aws_id = rt.route_table_id
        else:
            rt = ec2.RouteTable(rsrc.aws_id)
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


@capture_mapping(_aws_domain, Route)
class RouteTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(RouteTask, self).depends_on_list()
        if isinstance(self.rsrc.route_table, RouteTable):
            depson.append(self.rsrc.route_table)
        if isinstance(self.rsrc.gateway, InternetGateway):
            depson.append(self.rsrc.gateway)
        if isinstance(self.rsrc.network_interface, NetworkInterface):
            depson.append(self.rsrc.network_interface)
        # FIXME: need to add egress_only_gateway, nat_instance, nat_gateway, peering_connection
        # once we know what they are
        return depson

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, Route)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        rt = ec2.RouteTable(rsrc.route_table.aws_id)
        args = {}
        if rsrc.dest_cidr_block:
            args["DestinationCidrBlock"] = rsrc.dest_cidr_block
        if rsrc.dest_ipv6_cidr_block:
            args["DestinationIpv6CidrBlock"] = rsrc.dest_ipv6_cidr_block
        if rsrc.egress_only_gateway:
            args["EgressOnlyInternetGatewayId"] = rsrc.egress_only_gateway.aws_id
        if rsrc.gateway:
            args["GatewayId"] = rsrc.gateway.aws_id
        # FIXME: not cover InstanceId param
        if rsrc.nat_gateway:
            args["NatGatewayId"] = rsrc.nat_gateway.aws_id
        if rsrc.network_interface:
            args["NetworkInterfaceId"] = rsrc.network_interface.aws_id
        # FIXME: not covering VpCPeeringConnectionId
        _ = rt.create_route(**args)
        rsrc.aws_id = rsrc.route_table.aws_id, (rsrc.dest_cidr_block or
                                                rsrc.dest_ipv6_cidr_block)

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, Route)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        r = ec2.Route(*rsrc.aws_id)
        r.delete()


@capture_mapping(_aws_domain, NetworkInterface)
class NetworkInterfaceTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(NetworkInterfaceTask, self).depends_on_list()
        if isinstance(self.rsrc.subnet, Subnet):
            depson.append(self.rsrc.subnet)
        if isinstance(self.rsrc.sec_groups, Iterable):
            for sg in self.rsrc.sec_groups:
                if isinstance(sg, SecurityGroup):
                    depson.append(sg)
        # FIXME may need to check private_ip_address and private_ip_addresses
        return depson

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, NetworkInterface)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.sec_groups:
            gids = [sg.aws_id for sg in rsrc.sec_groups]
        else:
            gids = []
        args = dict(SubnetId=rsrc.subnet.aws_id,
                    Groups=gids)
        if rsrc.private_ip_address:
            args["PrivateIpAddress"] = rsrc.private_ip_address
        # FIXME: skipping private_ip_addresses for now
        if rsrc.description:
            args["Description"] = rsrc.description
        ni = ec2.create_network_interface(**args)
        rsrc.aws_id = ni.network_interface_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, NetworkInterface)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        ni = ec2.NetworkInterface(rsrc.aws_id)
        ni.delete()


@capture_mapping(_aws_domain, AWSInstance)
class AWSInstanceTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(AWSInstanceTask, self).depends_on_list()
        if isinstance(self.rsrc.key_pair, KeyPair):
            depson.append(self.rsrc.key_pair)
        if isinstance(self.rsrc.sec_groups, Iterable):
            for sg in self.rsrc.sec_groups:
                if isinstance(sg, SecurityGroup):
                    depson.append(sg)
        if isinstance(self.rsrc.subnet, Subnet):
            depson.append(self.rsrc.subnet)
        if isinstance(self.rsrc.network_interfaces, Iterable):
            for ni in self.rsrc.network_interfaces:
                if isinstance(ni, NetworkInterface):
                    depson.append(ni)
        return depson

    def await_status(self, cli, rsrc, expected_status, extract_func, max_ticks=300):
        """
        checks for the required status on the supplied resource
        :param cli: a boto3 EC2 client
        :param rsrc: an AWSInstance resource
        :param expected_status: string status value that we are waiting for
        :param extract_func: a callable that returns the appropriate status (or state or whatever) value
            for the instance from the return of the cli.describe_instance_status() boto3 call. this will
            be compared to the expected_status value and return when they match
        :param max_ticks: int, optional. number of ticks (secs) that we'll wait in here for this status
        :return:
        """
        assert isinstance(rsrc, AWSInstance)
        ticks = 0
        while ticks < max_ticks:
            time.sleep(1)
            if not (ticks % 15):
                status = cli.describe_instance_status(InstanceIds=[rsrc.aws_id])
                if len(status["InstanceStatuses"]) == 0:
                    break  # there's nothing to check!
                status_value = extract_func(status)
                if status_value == expected_status:
                    break
                elif status_value in ("impaired", "insufficient-data"):
                    details = status["InstanceStatuses"][0]["InstanceStatus"]["Details"]["Status"]
                    raise ProvisionerException("Instance {} startup failed; status:{}, details:{}".format(
                        rsrc.name, status_value, details
                    ))
            ticks += 1
        else:
            raise ProvisionerException("Timed out waiting for instance {} to reach status {}".format(rsrc.name,
                                                                                                     expected_status))

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, AWSInstance)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        if rsrc.aws_id is None:
            if rsrc.network_interfaces:
                nids = [{"NetworkInterfaceId": ni.aws_id,
                         "DeviceIndex": i}
                        for i, ni in enumerate(rsrc.network_interfaces)]
            else:
                nids = []
            if rsrc.sec_groups:
                sgids = [sg.aws_id for sg in rsrc.sec_groups]
            else:
                sgids = []
            args = dict(ImageId=rsrc.image_id,
                        InstanceType=rsrc.instance_type,
                        NetworkInterfaces=nids,
                        SecurityGroupIds=sgids,
                        MaxCount=1,
                        MinCount=1)
            if rsrc.subnet:
                args["SubnetId"] = rsrc.subnet.aws_id
            if rsrc.key_pair:
                args["KeyName"] = rsrc.key_pair.name
            instances = ec2.create_instances(**args)
            inst = instances[0]
            inst.wait_until_running()
            rsrc.aws_id = inst.instance_id
        # now delay finishing until the instance's status is 'ok'
        cli = run_context.ec2_client(region_name=rsrc.cloud)
        self.await_status(cli, rsrc, "ok", lambda status: status["InstanceStatuses"][0]["InstanceStatus"]["Status"])

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, AWSInstance)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        inst = ec2.Instance(rsrc.aws_id)
        inst.terminate()
        cli = run_context.ec2_client(region_name=rsrc.cloud)
        self.await_status(cli, rsrc, "terminated",
                          lambda status: status["InstanceStatuses"][0]["InstanceState"]["Name"])


@capture_mapping(_aws_domain, PublicIP)
class PublicIPTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(PublicIPTask, self).depends_on_list()
        if isinstance(self.rsrc.instance, AWSInstance):
            depson.append(self.rsrc.instance)
        if isinstance(self.rsrc.network_interface, NetworkInterface):
            depson.append(self.rsrc.network_interface)
        return depson

    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, PublicIP)
        cli = run_context.ec2_client(region_name=rsrc.cloud)
        # first allocate the address
        if rsrc.aws_id is None:
            args = {"Domain": rsrc.domain}
            if rsrc.address:
                args["Address"] = rsrc.address
            if rsrc.public_ipv4_pool:
                args["PublicIpv4Pool"] = rsrc.public_ipv4_pool
            response = cli.allocate_address(**args)
            rsrc.aws_id = response["AllocationId"]
            rsrc.ip_address = response["PublicIp"]
        # now do the association
        args = {"AllocationId": rsrc.aws_id}
        if rsrc.domain == "standard":
            args["Public"] = rsrc.ip_address
        if rsrc.network_interface:
            args["NetworkInterfaceId"] = rsrc.network_interface.aws_id
        if rsrc.instance:
            args["InstanceId"] = rsrc.instance.aws_id
        if rsrc.private_ip_address:
            args["PrivateIpAddress"] = rsrc.private_ip_address
        response = cli.associate_address(**args)
        rsrc.association_id = response["AssociationId"]

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, PublicIP)
        cli = run_context.ec2_client(region_name=rsrc.cloud)
        # first disassociate
        args = {"AssociationId": rsrc.aws_id}
        if rsrc.domain == "standard":
            args["PublicIp"] = rsrc.ip_address
        if rsrc.association_id is not None:
            args = {"AssociationId": rsrc.association_id}
            if rsrc.domain == "standard":
                args["PublicIp"] = rsrc.ip_address
            cli.disassociate_address(**args)
            rsrc.association_id = None
        # now release the address
        args = {"AllocationId": rsrc.aws_id}
        if rsrc.domain == "standard":
            args["PublicIp"] = rsrc.ip_address
        cli.release_address(**args)
