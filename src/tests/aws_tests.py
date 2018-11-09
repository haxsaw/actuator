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

import json
import threading
from actuator.provisioners.aws import aws_class_factory
from actuator.provisioners.aws import get_resource, EC2, S3, get_client
from actuator import ctxt
from actuator.infra import InfraModel
from actuator.provisioners.core import ProvisionerException
from actuator.provisioners.aws.resources import (SecurityGroupRule, SecurityGroup, Subnet, VPC,
                                                 KeyPair, InternetGateway, RouteTable, Route,
                                                 NetworkInterface, AWSInstance, PublicIP)
from actuator.utils import persist_to_dict, reanimate_from_dict


real_factory = aws_class_factory.get_aws_factory


class MockSession(object):
    def resource(self, _, **kw):
        return object()

    def client(self, _, **kw):
        return object()


def return_mock_session():
    return MockSession()


def setup_module():
    aws_class_factory.get_aws_factory = return_mock_session


def teardown_module():
    aws_class_factory.get_aws_factory = real_factory


def test001():
    """
    test001: test that we can get a resource
    :return:
    """
    resource = get_resource(EC2)
    assert resource


def test001a():
    """
    test001a: test that we can get a client
    """
    client = get_client(EC2)
    assert client


def test002():
    """
    test002: test that a default resource with the same name is returned on multiple calls
    """
    r1 = get_resource(EC2)
    r2 = get_resource(EC2)
    assert r1 is r2


def test002a():
    """
    test002a: test that a default clients is returned with the same default params
    """
    c1 = get_client(EC2)
    c2 = get_client(EC2)
    assert c1 is c2


def test003():
    """
    test003: check that multiple calls with different params yield different resources
    """
    r1 = get_resource(EC2, region_name="east-1")
    r2 = get_resource(EC2, region_name="west-1")
    assert r1 is not r2


def test003a():
    """
    test003a: ccheck that multiple calls with different params yield different clients
    """
    c1 = get_client(EC2, region_name="eu-west-2")
    c2 = get_client(EC2, region_name="eu-east-2")
    assert c1 is not c2


def test004():
    """
    test004: Check that we acquire different resource instances across different threads
    """
    r1 = get_resource(S3)

    class C(object):
        def __init__(self):
            self.val = None

        def capture(self, val):
            self.val = val
    c = C()

    def acquire():
        resource = get_resource(S3)
        c.capture(resource)

    t = threading.Thread(target=acquire)
    t.start()
    t.join()
    assert r1 is not c.val


def test004a():
    """
    test004a: Check that we acquire different client instances across different threads
    """
    c1 = get_client(S3)

    class C(object):
        def __init__(self):
            self.val = None

        def capture(self, val):
            self.val = val
    c = C()

    def acquire():
        resource = get_client(S3)
        c.capture(resource)

    t = threading.Thread(target=acquire)
    t.start()
    t.join()
    assert c1 is not c.val


def test005():
    """
    test004a: test making an instance of a vpc
    """
    vpc = VPC("t5", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    assert vpc


def test006():
    """
    test006: test putting a vpc into an infra model
    """
    class I006(InfraModel):
        vpc = VPC("t6", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    i = I006("i6")
    i.fix_arguments()
    assert i
    assert i.vpc.cidr_block.value() == '192.168.1.0/24'
    assert i.vpc.amazon_provided_ipv6_cidr_block.value() == True
    assert i.vpc.instance_tenancy.value() == 'dedicated'


class I006a(InfraModel):
    vpc = VPC("t6a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')


def test006a():
    """
    test006a: test persisting/reanimating a model with a vpc
    """
    i = I006a("i6a")
    i.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.vpc.cidr_block.value() == '192.168.1.0/24'
    assert iprime.vpc.amazon_provided_ipv6_cidr_block.value() == True
    assert iprime.vpc.instance_tenancy.value() == 'dedicated'


def test007():
    """
    test007: test making a security group
    """
    vpc = VPC("t7", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sg = SecurityGroup("t8", "test7 group", vpc)
    assert sg


def test008():
    """
    test008: test putting a security group in an infra model
    """
    class I008(InfraModel):
        vpc = VPC("t8", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sg = SecurityGroup("t8", "test8 group", ctxt.model.vpc)
    i = I008("i8")
    i.fix_arguments()
    assert i
    assert i.sg.description.value() == "test8 group"
    assert i.sg.vpc.value() is i.vpc.value()


class I008a(InfraModel):
    vpc = VPC("t8a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sg = SecurityGroup("t8a", "test8a group", ctxt.model.vpc)


def test008a():
    """
    test008a: check persisting/reanimating a security group in a model
    """
    i = I008a("i8a")
    i.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.sg.description.value() == "test8a group"
    assert iprime.sg.vpc.value() is iprime.vpc.value()


def test009():
    """
    test009: test making a security group rule
    """
    vpc = VPC("t9", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sg = SecurityGroup("t9", "test9 group", vpc)
    sgr = SecurityGroupRule("t9", sg, "ingress", "192.168.1.1/32", 1024, 1024, "tcp")
    assert sgr


def test010():
    """
    test010: test putting a security group in an infra model
    """
    class I010(InfraModel):
        vpc = VPC("t10", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sg = SecurityGroup("t10", "test10 group", ctxt.model.vpc)
        sgr = SecurityGroupRule("t10", ctxt.model.sg, "ingress", "192.168.1.1/32", 1024, 1024, "tcp")
    i10 = I010("i10")
    i10.fix_arguments()
    assert i10
    assert i10.sgr.security_group.value() is i10.sg.value()
    assert i10.sgr.kind.value() == "ingress"
    assert i10.sgr.cidrip.value() == "192.168.1.1/32"
    assert i10.sgr.from_port.value() == 1024
    assert i10.sgr.ip_protocol.value() == "tcp"
    assert i10.sg.vpc.value() is i10.vpc.value()


class I010a(InfraModel):
    vpc = VPC("t10a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sg = SecurityGroup("t10a", "test10a group", ctxt.model.vpc)
    sgr = SecurityGroupRule("t10a", ctxt.model.sg, "ingress", "192.168.1.1/32", 1024, 1024, "tcp")


def test10a():
    """
    test010a: test persisting/reanimating security a security group rule
    """
    i10 = I010a("i10a")
    i10.fix_arguments()
    d = persist_to_dict(i10)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.sgr.security_group.value() is iprime.sg.value()
    assert iprime.sgr.kind.value() == "ingress"
    assert iprime.sgr.cidrip.value() == "192.168.1.1/32"
    assert iprime.sgr.from_port.value() == 1024
    assert iprime.sgr.ip_protocol.value() == "tcp"
    assert iprime.sg.vpc.value() is iprime.vpc.value()


def test011():
    """
    test011: create a key pair
    """
    kp = KeyPair("test11", ensure_unique=True)
    assert kp


def test012():
    """
    test012: put a keypair in a model
    """
    class I012(InfraModel):
        kp = KeyPair("test12", ensure_unique=True)
    i = I012("test12")
    i.fix_arguments()
    assert i
    assert i.kp.ensure_unique.value(), "ensure unique is {}".format(i.kp.ensure_unique.value())
    assert i.kp.name.value() == "test12"


class I012a(InfraModel):
    kp = KeyPair("test12a", ensure_unique=True)


def test012a():
    """
    test012a: try prersisting/reanimating a KeyPair
    :return:
    """
    i = I012a("test12a")
    i.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.kp.ensure_unique.value(), "ensure unique is {}".format(iprime.kp.ensure_unique.value())
    assert iprime.kp.name.value() == "test12a"


def test013():
    """
    test013: create a subnet
    """
    vpc = VPC("t13", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sn = Subnet("sn13", "192.168.1.0/22", vpc, availability_zone="wibble", ipv6_cidr_block="")
    assert sn


def test014():
    """
    test014: put a subnet into a model
    """
    class I014(InfraModel):
        vpc = VPC("t14", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sn = Subnet("sn14", ctxt.model.vpc.cidr_block, ctxt.model.vpc,
                    availability_zone="wibble", ipv6_cidr_block="whatever")
    i = I014("infra14")
    i.fix_arguments()
    i.sn.value().fixed = False  # need to re-fix as fixing order isn't guarenteed during tests
    i.sn.fix_arguments()
    assert i
    assert i.sn.vpc.value() is i.vpc.value()
    assert i.sn.cidr_block.value() == i.vpc.cidr_block.value(), "sn cidr: {}, vpc cidr {}".format(i.sn.cidr_block.value(),
                                                                                                  i.vpc.cidr_block.value())
    assert i.sn.availability_zone.value() == "wibble", "zone was {}".format(i.sn.availability_zone.value())
    assert i.sn.ipv6_cidr_block.value() == "whatever"


class I014a(InfraModel):
    vpc = VPC("t14a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sn = Subnet("sn14a", ctxt.model.vpc.cidr_block, ctxt.model.vpc,
                availability_zone="wibble", ipv6_cidr_block="whatever")


def test014a():
    """
    test014a: persist/reanimate a subnet
    """
    i = I014a("infra14a")
    i.fix_arguments()
    i.sn.value().fixed = False  # need to re-fix as fixing order isn't guarenteed during tests
    i.sn.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.sn.vpc.value() is iprime.vpc.value()
    assert iprime.sn.cidr_block.value() == iprime.vpc.cidr_block.value(), "sn cidr: {}, vpc cidr {}".format(iprime.sn.cidr_block.value(),
                                                                                                  iprime.vpc.cidr_block.value())
    assert iprime.sn.availability_zone.value() == "wibble", "zone was {}".format(iprime.sn.availability_zone.value())
    assert iprime.sn.ipv6_cidr_block.value() == "whatever"


def test015():
    """
    test015: create an internet gateway
    """
    ig = InternetGateway("ig15", ctxt.model.vpc)
    assert ig


def test016():
    """
    test016: put an internet gateway into a model
    """
    class I016(InfraModel):
        ig = InternetGateway("ig16", ctxt.model.vpc)
        vpc = VPC("t16", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    i = I016("t16")
    i.fix_arguments()
    assert i
    assert i.ig.vpc.value() is i.vpc.value()


class I016a(InfraModel):
    ig = InternetGateway("ig16a", ctxt.model.vpc)
    vpc = VPC("t16a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')


def test016a():
    """
    test016a: test persisting/reanimating an internet gateway
    """
    i = I016a("i16a")
    i.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.ig.vpc.value() is iprime.vpc.value()


def test017():
    """
    test017: test making a RouteTable
    """
    rt = RouteTable("rt17", ctxt.model.vpc, ctxt.model.sn)
    assert rt


def test018():
    """
    test018: put a route table in a model
    """
    class I018(InfraModel):
        vpc = VPC("t18", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sn = Subnet("sn118", "192.168.1.0/24", ctxt.model.vpc,
                    availability_zone="wibble", ipv6_cidr_block="whatever")
        rt = RouteTable("t18", ctxt.model.vpc, ctxt.model.sn)
    i = I018("t18")
    i.fix_arguments()
    assert i
    assert i.rt.vpc.value() is i.vpc.value()
    assert i.rt.subnet.value() is i.sn.value()


class I018a(InfraModel):
    vpc = VPC("t18a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sn = Subnet("sn118a", "192.168.1.0/24", ctxt.model.vpc,
                availability_zone="wibble", ipv6_cidr_block="whatever")
    rt = RouteTable("t18", ctxt.model.vpc, ctxt.model.sn)


def test018a():
    """
    test018a: try persisting/reanimating a route table
    """
    i = I018a("t18a")
    i.fix_arguments()
    d = persist_to_dict(i)
    dp = json.loads(json.dumps(d))
    iprime = reanimate_from_dict(dp)
    assert iprime.rt.vpc.value() is iprime.vpc.value()
    assert iprime.rt.subnet.value() is iprime.sn.value()


def test019():
    """
    test019: try creating a route
    """
    r = Route("r19", ctxt.model.rt, dest_cidr_block="0.0.0.0/0", gateway=ctxt.model.ig)
    assert r


def test020():
    """
    test020: add a route to a model
    """
    class I020(InfraModel):
        ig = InternetGateway("ig20", ctxt.model.vpc)
        vpc = VPC("vpc20", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        r = Route("r20", ctxt.model.rt, dest_cidr_block="0.0.0.0/0", gateway=ctxt.model.ig)
        sn = Subnet("sn20", "192.168.1.0/24", ctxt.model.vpc,
                    availability_zone="wibble", ipv6_cidr_block="whatever")
        rt = RouteTable("t20", ctxt.model.vpc, ctxt.model.sn)
    i = I020("i20")
    i.fix_arguments()
    assert i.r.gateway.value() is i.ig.value()
    assert i.r.dest_cidr_block.value() == "0.0.0.0/0"
    assert i.r.route_table.value() is i.rt.value()


class I020a(InfraModel):
    ig = InternetGateway("ig20a", ctxt.model.vpc)
    vpc = VPC("vpc20a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    r = Route("r20a", ctxt.model.rt, dest_cidr_block="0.0.0.0/0", gateway=ctxt.model.ig)
    sn = Subnet("sn20a", "192.168.1.0/24", ctxt.model.vpc,
                availability_zone="wibble", ipv6_cidr_block="whatever")
    rt = RouteTable("t20a", ctxt.model.vpc, ctxt.model.sn)


def test020a():
    """
    test020a: persist/reanimate a model with a route
    """
    j = I020a("i20a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.r.gateway.value() is i.ig.value()
    assert i.r.dest_cidr_block.value() == "0.0.0.0/0"
    assert i.r.route_table.value() is i.rt.value()


def test022():
    """
    test022: create a network interface
    """
    ni = NetworkInterface("ni22", ctxt.model.sn, description="wibble",
                          sec_groups=[ctxt.model.sg1,
                                      ctxt.model.sg2])
    assert ni


def test023():
    """
    test023: put a network interface into a model
    """
    class I023(InfraModel):
        vpc = VPC("vpc23", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        ni = NetworkInterface("ni23", ctxt.model.sn, description="wibble",
                              sec_groups=[ctxt.model.sg1,
                                          ctxt.model.sg2])
        sn = Subnet("sn23", "192.168.1.0/24", ctxt.model.vpc)
        sg1 = SecurityGroup("i23-sg1", "sg1", ctxt.model.vpc)
        sg2 = SecurityGroup("i23-sg2", "sg2", ctxt.model.vpc)
    i = I023("i23")
    i.fix_arguments()
    assert i.ni.subnet.value() is i.sn.value()
    assert i.ni.value().sec_groups[0] is i.sg1.value()
    assert i.ni.value().sec_groups[1] is i.sg2.value()
    assert i.ni.description.value() == "wibble"


class I023a(InfraModel):
    vpc = VPC("vpc23a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    ni = NetworkInterface("ni23a", ctxt.model.sn, description="wibble",
                          sec_groups=[ctxt.model.sg1, ctxt.model.sg2])
    sn = Subnet("sn23a", "192.168.1.0/24", ctxt.model.vpc)
    sg1 = SecurityGroup("i23a-sg1", "sg1", ctxt.model.vpc)
    sg2 = SecurityGroup("i23a-sg2", "sg2", ctxt.model.vpc)


def test023a():
    """
    test023a: try persisting/reanimating a model with a network interface
    """
    j = I023a("i23a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.ni.subnet.value() is i.sn.value()
    assert i.ni.value().sec_groups[0] is i.sg1.value()
    assert i.ni.value().sec_groups[1] is i.sg2.value()
    assert i.ni.description.value() == "wibble"


ami_id = "ami-0f27df5f159bccfba"
instance_type = 't2.nano'


def test024():
    """
    test024: create a server
    """
    s = AWSInstance("s24", ami_id, instance_type=instance_type, key_pair=ctxt.model.kp,
                    sec_groups=[ctxt.model.sg], subnet=ctxt.model.sn, network_interfaces=[ctxt.model.ni])
    assert s


def test025():
    """
    test025: put a server into a model
    """
    class I025(InfraModel):
        s = AWSInstance("s25", ami_id, instance_type=instance_type, key_pair=ctxt.model.kp,
                        sec_groups=[ctxt.model.sg], subnet=ctxt.model.sn, network_interfaces=[ctxt.model.ni])
        kp = KeyPair("kp25")
        sg = SecurityGroup("sg25", "sg25 desc", ctxt.model.vpc)
        vpc = VPC("vpc25", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sn = Subnet("sn25", "192.168.1.0/24", ctxt.model.vpc)
        ni = NetworkInterface("ni25", ctxt.model.sn, description="wibble", sec_groups=[ctxt.model.sg])
    i = I025("i25")
    i.fix_arguments()
    assert i.s.key_pair.value() is i.kp.value()
    assert i.s.sec_groups.value()[0] is i.sg.value()
    assert i.s.network_interfaces.value()[0] is i.ni.value()
    assert i.s.subnet.value() is i.sn.value()
    assert i.s.image_id.value() == ami_id
    assert i.s.instance_type.value() == instance_type


class I025a(InfraModel):
    s = AWSInstance("s25a", ami_id, instance_type=instance_type, key_pair=ctxt.model.kp,
                    sec_groups=[ctxt.model.sg], subnet=ctxt.model.sn, network_interfaces=[ctxt.model.ni])
    kp = KeyPair("kp25a")
    sg = SecurityGroup("sg2a5", "sg25a desc", ctxt.model.vpc)
    vpc = VPC("vpc25a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sn = Subnet("sn25a", "192.168.1.0/24", ctxt.model.vpc)
    ni = NetworkInterface("ni25a", ctxt.model.sn, description="wibble", sec_groups=[ctxt.model.sg])


def test025a():
    """
    test025a: persist/reanimate a model with a server
    """
    j = I025a("i25a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.s.key_pair.value() is i.kp.value()
    assert i.s.sec_groups.value()[0] is i.sg.value()
    assert i.s.network_interfaces.value()[0] is i.ni.value()
    assert i.s.subnet.value() is i.sn.value()
    assert i.s.image_id.value() == ami_id
    assert i.s.instance_type.value() == instance_type


def test26():
    """
    test026: create a PublicIP
    """
    ip = PublicIP("ip26", domain="vpc", network_interface=ctxt.model.ni)
    assert ip


def test27():
    """
    test027: check that we raise when none of the required args are supplied
    """
    try:
        ip = PublicIP("ip27", domain="vpc")
        assert False, "this should have raised"
    except ProvisionerException:
        pass


def test28():
    """
    test028: check that we raise when too many required args are supplied
    """
    try:
        ip = PublicIP("ip28", network_interface=ctxt.model.ni, private_ip_address="192.168.1.1")
        assert False, "this should have raised"
    except ProvisionerException:
        pass

    try:
        ip = PublicIP("ip28", instance=ctxt.model.srvr, network_interface=ctxt.model.ni)
        assert False, "this should have raised"
    except ProvisionerException:
        pass


def test029():
    """
    test029: check that we get an exception with both and address and pub ip pool
    """
    try:
        _ = PublicIP("ip29", public_ipv4_pool="pool-id", address="8.8.8.8",
                     instance=ctxt.model.srvr)
        assert False, "this should have raised"
    except ProvisionerException:
        pass


def test030():
    """
    test030: put a public ip associated with a private ip into a model
    """
    class I030(InfraModel):
        ip = PublicIP("ip30", domain="standard", public_ipv4_pool="pool_id",
                      private_ip_address="192.168.1.1")
    i = I030("i30")
    i.fix_arguments()
    assert i.ip.domain.value() == "standard"
    assert i.ip.public_ipv4_pool.value() == "pool_id"
    assert i.ip.private_ip_address.value() == "192.168.1.1"


class I030a(InfraModel):
    ip = PublicIP("ip30a", domain="standard", public_ipv4_pool="pool_id",
                  private_ip_address="192.168.1.1")


def test030a():
    """
    test030a: persist/reanimate a pub ip using a private ip
    """
    j = I030a("i30a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.ip.domain.value() == "standard"
    assert i.ip.public_ipv4_pool.value() == "pool_id"
    assert i.ip.private_ip_address.value() == "192.168.1.1"


def test031():
    """
    test031: public ip with a network interface
    """
    class I031(InfraModel):
        ni = NetworkInterface("ni31", ctxt.model.sn)
        sn = Subnet("sn31", "192.168.1.0/24", ctxt.model.vpc)
        vpc = VPC("vpc31", "192.168.1.0/24")
        ip = PublicIP("ip31", domain="vpc", network_interface=ctxt.model.ni)
    i = I031("i31")
    i.fix_arguments()
    assert i.ip.network_interface.value() is i.ni.value()


class I031a(InfraModel):
    ni = NetworkInterface("ni31a", ctxt.model.sn)
    sn = Subnet("sn31a", "192.168.1.0/24", ctxt.model.vpc)
    vpc = VPC("vpc31a", "192.168.1.0/24")
    ip = PublicIP("ip31a", domain="vpc", network_interface=ctxt.model.ni)


def test031a():
    """
    test031a: persist/reanimate an ip that uses a network interface
    """
    j = I031a("i31a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.ip.network_interface.value() is i.ni.value()


def test032():
    """
    test032: test an ip that uses an instance
    """
    class I032(InfraModel):
        s = AWSInstance("s32", ami_id, instance_type=instance_type, key_pair=ctxt.model.kp,
                        sec_groups=[ctxt.model.sg], subnet=ctxt.model.sn, network_interfaces=[ctxt.model.ni])
        kp = KeyPair("kp32")
        sg = SecurityGroup("sg32", "sg32 desc", ctxt.model.vpc)
        vpc = VPC("vpc32", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
        sn = Subnet("sn32", "192.168.1.0/24", ctxt.model.vpc)
        ni = NetworkInterface("ni32", ctxt.model.sn, description="wibble", sec_groups=[ctxt.model.sg])
        ip = PublicIP("ip32", domain="vpc", instance=ctxt.model.s)
    i = I032("i32")
    i.fix_arguments()
    assert i.ip.instance.value() is i.s.value()


class I032a(InfraModel):
    s = AWSInstance("s32a", ami_id, instance_type=instance_type, key_pair=ctxt.model.kp,
                    sec_groups=[ctxt.model.sg], subnet=ctxt.model.sn, network_interfaces=[ctxt.model.ni])
    kp = KeyPair("kp32a")
    sg = SecurityGroup("sg32a", "sg32a desc", ctxt.model.vpc)
    vpc = VPC("vpc32a", "192.168.1.0/24", amazon_provided_ipv6_cidr_block=True, instance_tenancy='dedicated')
    sn = Subnet("sn32a", "192.168.1.0/24", ctxt.model.vpc)
    ni = NetworkInterface("ni32a", ctxt.model.sn, description="wibble", sec_groups=[ctxt.model.sg])
    ip = PublicIP("ip32a", domain="vpc", instance=ctxt.model.s)


def test032a():
    """
    test032a: persist/reanimate model with ip that uses an instance
    """
    j = I032a("i32a")
    j.fix_arguments()
    d = persist_to_dict(j)
    dp = json.loads(json.dumps(d))
    i = reanimate_from_dict(dp)
    assert i.ip.instance.value() is i.s.value()


def do_all():
    for k, v in sorted(globals().items()):
        if k.startswith("test") and callable(v):
            try:
                v()
            except Exception as e:
                print(">>>>> {} failed with {}".format(k, str(e)))


if __name__ == "__main__":
    do_all()
