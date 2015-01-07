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
NOTE: this module relies on ost_support for the mocks it needs, which in turn relies on Faker
for generating test data. The faker is put into known initial state so that it generates the 
same series of test data with each run, allowing us to test returned values properly. That means
that the order of calls into the mocks must not change from run to run or else the expected data
won't be generated. The lesson here is that as tests are added, they should always be added to the
end of the list of tests, and never inserted in between existing tests.
Created on 25 Aug 2014
'''

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.namespace import NamespaceModel, with_variables
ocf.set_neutron_client_class(ost_support.MockNeutronClient)
ocf.set_nova_client_class(ost_support.MockNovaClient)

from actuator import (InfraModel, ProvisionerException, MultiResourceGroup,
                      MultiResource, ctxt, Var, ResourceGroup)
# from actuator.provisioners.openstack.openstack import OpenstackProvisioner
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from actuator.provisioners.openstack.resources import (Server, Network,
                                                        Router, FloatingIP,
                                                        Subnet, SecGroup,
                                                        SecGroupRule)


def get_provisioner():
    return OpenstackProvisioner("it", "just", "doesn't", "matter")


def test001():
    provisioner = get_provisioner()
    class Test1(InfraModel):
        net = Network("test1Net")
    spec = Test1("test1")
    assert spec.net.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.net.osid.value()
    
def test002():
    provisioner = get_provisioner()
    class Test2(InfraModel):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
        fip = FloatingIP("fip1", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    spec = Test2("test2")
    assert spec.fip.ip.value() is None and spec.fip.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.fip.ip.value() and spec.fip.osid.value()
    
def test003():
    provisioner = get_provisioner()
    class Test3(InfraModel):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.model.net, u"192.168.23.0/24")
    spec = Test3("test3")
    assert spec.subnet.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.subnet.osid.value()

def test004():
    provisioner = get_provisioner()
    class Test4(InfraModel):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.model.net, u"192.168.23.0/24")
    spec = Test4("test4")
    assert spec.net.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert (spec.net.osid.value() == spec.subnet.network.osid.value() and
            spec.net.osid.value() is not None)

def test005():
    provisioner = get_provisioner()
    class Test5(InfraModel):
        router = Router("wibbleRouter")
    spec = Test5("test5")
    provisioner.provision_infra_spec(spec)
    assert spec.router.osid.value()
    
def test006():
    provisioner = get_provisioner()
    class Test6(InfraModel):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
    spec = Test6("test6")
    provisioner.provision_infra_spec(spec)
    assert spec.server.osid.value() and spec.server.addresses.value()
    
def test007():
    try:
        class Test7(InfraModel):
            net = Network("wibbleNet")
            subnet = Subnet("wibbleSub", "net", u'300.168.23.0/24')
            #CIDR string checking has been disabled
#         assert False, "There should have been an exception regarding the cidr string"
    except ProvisionerException, _:
        assert True
        
def test008():
    """
    NOTE: this test is obsolete, but must remain as it impacts the operation
    of the tests that follow (the mocks and the values they generate depend on
    this test running). It will always return success, but PLEASE DON'T DELETE IT!!
    """
    provisioner = get_provisioner()
    class Test8(InfraModel):
        net = Network("wibbleNet")
        subnet = Subnet("WibbleSub", ctxt.model.net, u'192.168.22.0/24')
        router = Router("wibbleRouter")
        srvr1 = Server("simple1", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
        srvr2 = Server("simple2", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
    spec = Test8("test8")
    provisioner.provision_infra_spec(spec)
#     provisioner.workflow_sorter.reset()
#     assert len(provisioner.workflow_sorter.servers) == 0
    assert True
    
def test009():
    provisioner = get_provisioner()
    class Test9(InfraModel):
        server = Server("simple", u'bogus image', "m1.small", key_name="perseverance_dev_key")
    spec = Test9("test9")
    try:
        provisioner.provision_infra_spec(spec)
        assert False, "failed to raise an exception on a bogus image name"
    except ProvisionerException, e:
        evalues = " ".join([t[2].message.lower() for t in provisioner.agent.aborted_tasks])
#         assert "image" in e.message.lower()
        assert "image" in evalues

def test010():
    provisioner = get_provisioner()
    class Test10(InfraModel):
        server = Server("simple", u'Ubuntu 13.10', "m1.wibble", key_name="perseverance_dev_key")
    spec = Test10("test10")
    try:
        provisioner.provision_infra_spec(spec)
        assert False, "failed to raise an exception on a bogus flavor name"
    except ProvisionerException, e:
        assert "flavor" in e.message.lower()
        
def test011():
    provisioner = get_provisioner()
    class Test11(InfraModel):
        net = Network("wibble")
        server = Server("simple", u'Ubuntu 13.10', "m1.small", nics=[ctxt.model.net.name],
                        key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    spec = Test11("t11")
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test012():
    provisioner = get_provisioner()
    class Test12(InfraModel):
        net = Network("wibble")
        routable_group = MultiResourceGroup("routables",
                                             server=Server("simple", u'Ubuntu 13.10', "m1.small",
                                                           nics=[ctxt.model.net.name],
                                                           key_name="perseverance_dev_key"),
                                             fip=FloatingIP("fip",
                                                            ctxt.comp.container.server,
                                                            ctxt.comp.container.server.iface0.addr0,
                                                            pool="external"))
    spec = Test12("t12")
    _ = [spec.routable_group[i] for i in ["a", "b"]]
    rec = provisioner.provision_infra_spec(spec)
    assert rec

def test013():
    provisioner = get_provisioner()
    class Test13(InfraModel):
        subnet = Subnet("WibbleSub", ctxt.model.net, u'192.168.22.0/24')
        net = Network("wibble")
        grid = MultiResource(Server("simple", u'Ubuntu 13.10', "m1.small",
                                     nics=[ctxt.model.net.name],
                                     key_name="perseverance_dev_key"))
        gateway = Server("gateway", u'Ubuntu 13.10', "m1.small",
                         nics=[ctxt.model.net.name], key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.model.gateway,
                         ctxt.model.gateway.iface0.addr0, pool="external")
    spec = Test13("test13")
    _ = [spec.grid[i] for i in ["LN", "NY", "TK"]]
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test014():
    provisioner = get_provisioner()
    class Test14(InfraModel):
        subnet = Subnet("WibbleSub", ctxt.model.net, u'192.168.22.0/24')
        net = Network("wibble")
        collective = MultiResourceGroup("collective",
                                         foreman = Server("gateway", u'Ubuntu 13.10', "m1.small",
                                                          nics=[ctxt.model.net.name],
                                                          key_name="perseverance_dev_key"),
                                         workers = MultiResource(Server("simple", u'Ubuntu 13.10', "m1.small",
                                                                         nics=[ctxt.model.net.name],
                                                                         key_name="perseverance_dev_key")))
        gateway = Server("gateway", u'Ubuntu 13.10', "m1.small",
                         nics=[ctxt.model.net.name], key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.model.gateway,
                         ctxt.model.gateway.iface0.addr0, pool="external")
    spec = Test14("t14")
    for i in range(3):
        for j in range(5):
            _ = spec.collective[i].workers[j]
    rec = provisioner.provision_infra_spec(spec)
    assert len(spec.resources()) == 22
    
def test015():
    provisioner = get_provisioner()
    class Test15(InfraModel):
        g = MultiResourceGroup("testGroup",
                                net=Network("wibble"),
                                subnet=Subnet("WibbleSub", ctxt.comp.container.net, u'192.168.23.0/24'),
                                workers=MultiResource(Server("worker", u'Ubuntu 13.10', "m1.small",
                                                              nics=[ctxt.comp.container.container.net.name])))
    spec = Test15("t15")
    _ = spec.g[1].workers[1]
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test016():
    provisioner = get_provisioner()
    class Test16(InfraModel):
        net = Network("wibble")
        subnet = Subnet("WibbleSub", lambda _: [], u"192.168.23.0/24",
                        dns_nameservers=[u'8.8.8.8'])
    spec = Test16("t16")
    try:
        provisioner.provision_infra_spec(spec)
        assert False, "We should have gotten an error about the network arg"
    except ProvisionerException, e:
        assert "network" in e.message
        
def test017():
    provisioner = get_provisioner()
    class Test17(InfraModel):
        net = Network("wibble")
        subnet = Subnet("WibbleSub", ctxt.model.net, u"192.168.23.0/24",
                        dns_nameservers=[u'8.8.8.8'])
        s1 = Server("perseverance1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net.name])
        clusters = MultiResourceGroup("clusters",
                                       cluster_net=Network("wibbleNet"),
                                       cluster_sub=Subnet("cluster_sub", ctxt.comp.container.cluster_net,
                                                          u'192.168.%d.0/30'),
                                       cluster_foreman = Server("cluster_foreman", "Ubuntu 13.10", "m1.small",
                                                                nics=[ctxt.comp.container.cluster_net.name]),
                                       cluster=MultiResource(Server("cluster_node", "Ubuntu 13.10", "m1.small",
                                                                     nics=[ctxt.comp.container.container.cluster_net.name])))
    spec = Test17("t17")
    _ = spec.clusters["ny"].cluster[1]
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
#@FIXME test018-test021 suspended as validation on the class object currently
#is deactivated
# def test018():
#     try:
#         class Test18(InfraModel):
#             net = Network("wibble")
#             subnet = Subnet("WibbleSub", ctxt.model.nett, u'192.168.23.0/24',
#                             dns_nameservers=[u'8,8,8,8'])
#         assert False, "Class Test18 should have raised an InfraException"
#     except InfraException, e:
#         assert "nett" in e.message
#         
# def test019():
#     try:
#         class Test19(InfraModel):
#             net = Network("wibble")
#             subnet = Subnet("WibbleSub", ctxt.model.net, u"192.168.23.0/24",
#                             dns_nameservers=[u'8.8.8.8'])
#             s1 = Server("perseverance1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.nett])
# #             cluster=MultiResource(Server("cluster_node", "Ubuntu 13.10", "m1.small",
# #                                                                      #the nics arg is the one that should fail
# #                                                                      nics=[ctxt.model.nett]))
#         assert False, "The creation of Test19 should have failed"
#     except InfraException, e:
#         assert "nics" in e.message
# 
# def test020():
#     try:
#         class Test120(InfraModel):
#             net = Network("wibble")
#             subnet = Subnet("WibbleSub", ctxt.model.net, u"192.168.23.0/24",
#                             dns_nameservers=[u'8.8.8.8'])
#             cluster=MultiResource(Server("cluster_node", "Ubuntu 13.10", "m1.small",
#                                                                      #the nics arg is the one that should fail
#                                                                      nics=[ctxt.model.nett]))
#         assert False, "The creation of Test20 should have failed"
#     except InfraException, e:
#         assert "nics" in e.message
# 
# def test021():
#     try:
#         class Test021(InfraModel):
#             #the next line contains the error; 'cluster_net' is spelled with 2 t's
#             cluster=MultiResourceGroup("cluster", cluster_sub=Subnet("csub",
#                                                                       ctxt.comp.container.cluster_nett,
#                                                                       u'192.168.24.0/24',
#                                                                       dns_nameservers=['8.8.8.8']),
#                                         cluster_net = Network("cnet"))
#         assert False, "The creation of Test21 should have failed"
#     except InfraException, e:
#         assert "nett" in e.message

def test022():
    _ = SecGroup("wibbleGroup", description="A group for testing")
    
def test023():
    class SGTest(InfraModel):
        secgroup = SecGroup("wibbleGroup", description="A group for testing")
    inst = SGTest("t1")
    assert inst.secgroup is not SGTest.secgroup

def test024():
    prov = get_provisioner()
    class SGTest(InfraModel):
        secgroup = SecGroup("wibbleGroup", description="A group for testing")
    inst = SGTest("t1")
    rec = prov.provision_infra_spec(inst)
    assert rec
    
def test025():
    prov = get_provisioner()
    class SGTest(InfraModel):
        secgroup = SecGroup("wibbleGroup", description="stuff")
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key",
                        security_groups=[ctxt.model.secgroup])
        fip = FloatingIP("fip1", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    inst = SGTest("t25")
    rec = prov.provision_infra_spec(inst)
    assert rec
    
def test026():
    _ = SecGroupRule("rule1", ctxt.model.secgroup, ip_protocol=None,
                     from_port=None, to_port=None, cidr=None)


def test027():
    prov = get_provisioner()
    class SGRTest(InfraModel):
        secgroup = SecGroup("wibbleGroup", description="stuff")
        ping = SecGroupRule("pingRule", ctxt.model.secgroup,
                            ip_protocol="icmp",
                            from_port=-1, to_port=-1)
    inst = SGRTest("ping")
    rec = prov.provision_infra_spec(inst)
    assert rec

def test028():
    prov = get_provisioner()
    seccomp = ResourceGroup("security_resource_group",
                             secgroup=SecGroup("wibbleGroup", description="stuff"),
                             ping=SecGroupRule("pingRule",
                                               ctxt.comp.container.secgroup,
                                               ip_protocol="icmp",
                                               from_port=-1, to_port=-1),
                             ssh_rule=SecGroupRule("ssh_rule",
                                                   ctxt.comp.container.secgroup,
                                                   ip_protocol="tcp", from_port=22,
                                                   to_port=22))
    class SGRTest(InfraModel):
        external_access = seccomp
    inst = SGRTest("seccomp")
    rec = prov.provision_infra_spec(inst)
    assert rec

def test029():
    prov = get_provisioner()
    seccomp = ResourceGroup("security_resource_group",
                             secgroup=SecGroup("wibbleGroup", description="stuff"),
                             ping=SecGroupRule("pingRule",
                                               ctxt.comp.container.secgroup,
                                               ip_protocol="icmp",
                                               from_port=-1, to_port=-1),
                             ssh_rule=SecGroupRule("ssh_rule",
                                                   ctxt.comp.container.secgroup,
                                                   ip_protocol="tcp", from_port=22,
                                                   to_port=22))
    class SGRTest(InfraModel):
        external_access = seccomp
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key",
                        security_groups=[ctxt.model.external_access.secgroup])
        fip = FloatingIP("fip1", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    inst = SGRTest("seccomp with server")
    rec = prov.provision_infra_spec(inst)
    assert rec
    
def test030():
    prov = get_provisioner()
    class IPTest(InfraModel):
        server = Server("simple", u"Ubuntu 13.10", "m1.small",
                        key_name="perseverance_dev_key")
        server_fip = FloatingIP("server_fip", ctxt.model.server,
                                ctxt.model.server.iface0.addr0, pool="external")
    inst = IPTest("iptest")
    class IPNamespace(NamespaceModel):
        with_variables(Var("SERVER_IP", IPTest.server_fip.ip))
    ns = IPNamespace()
    ns.compute_provisioning_for_environ(inst)
    prov.provision_infra_spec(inst)
    assert ns.future("SERVER_IP").value()

def do_all():
    test006()
#     for k, v in globals().items():
#         if k.startswith("test") and callable(v):
#             v()
            
if __name__ == "__main__":
    do_all()
