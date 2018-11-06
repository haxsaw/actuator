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
from actuator.provisioners.aws import get_resource, EC2, S3
from actuator import ctxt
from actuator.infra import InfraModel
from actuator.provisioners.aws.resources import (SecurityGroupRule, SecurityGroup, Subnet, VPC,
                                                 KeyPair, InternetGateway)
from actuator.utils import persist_to_dict, reanimate_from_dict


real_factory = aws_class_factory.get_aws_factory


class MockSession(object):
    def resource(self, _, **kw):
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


def test002():
    """
    test002: test that a default resource with the same name is returned on multiple calls
    """
    r1 = get_resource(EC2)
    r2 = get_resource(EC2)
    assert r1 is r2


def test003():
    """
    test003: check that multiple calls with the same params yield the same resource
    """
    r1 = get_resource(EC2, region_name="east-1")
    r2 = get_resource(EC2, region_name="west-1")
    assert r1 is not r2


def test004():
    """
    test004: Check that the same we acquire different resource instances across different threads
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
    test014a: put a persist/reanimate a subnet
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


def do_all():
    for k, v in sorted(globals().items()):
        if k.startswith("test") and callable(v):
            try:
                v()
            except Exception as e:
                print(">>>>> {} failed with {}".format(k, str(e)))


if __name__ == "__main__":
    do_all()
