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
'''

import json

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.namespace import NamespaceModel, with_variables
ocf.set_neutron_client_class(ost_support.MockNeutronClient)
ocf.set_nova_client_class(ost_support.MockNovaClient)

from actuator import (InfraModel, ProvisionerException, MultiResourceGroup,
                      MultiResource, ctxt, Var, ResourceGroup, with_infra_options,
    ActuatorOrchestration)
from actuator.provisioners.openstack.resource_tasks import (OpenstackProvisioner,
                                                            ResourceTaskSequencerAgent)
ResourceTaskSequencerAgent.repeat_count = 1
from actuator.provisioners.openstack.resources import (Server, Network,
                                                        Router, FloatingIP,
                                                        Subnet, SecGroup,
                                                        SecGroupRule, KeyPair,
                                                        RouterInterface,
                                                        RouterGateway)
from actuator.utils import (LOG_INFO, find_file, persist_to_dict,
                            reanimate_from_dict)


def get_provisioner():
    return OpenstackProvisioner("it", "just", "doesn't", "matter",
                                log_level=LOG_INFO)


def test001():
    provisioner = get_provisioner()
    class Test1(InfraModel):
        net = Network("test1Net")
    model = Test1("test1")
    assert model.net.osid.value() is None
    provisioner.provision_infra_model(model)
    assert model.net.osid.value()
    
def test002():
    provisioner = get_provisioner()
    class Test2(InfraModel):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
        fip = FloatingIP("fip1", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    model = Test2("test2")
    assert model.fip.get_ip() is None and model.fip.osid.value() is None
    try:
        provisioner.provision_infra_model(model)
    except Exception, _:
        print "provision failed; here are the exceptions"
        import traceback
        for t, et, ev, tb in provisioner.agent.get_aborted_tasks():
            print "Task %s" % t.name
            traceback.print_exception(et, ev, tb)
            print
        assert False, "Test provisioning failed"
    assert model.fip.get_ip() and model.fip.osid.value()
    
def test003():
    provisioner = get_provisioner()
    class Test3(InfraModel):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.model.net, u"192.168.23.0/24")
    model = Test3("test3")
    assert model.subnet.osid.value() is None
    provisioner.provision_infra_model(model)
    assert model.subnet.osid.value()

def test004():
    provisioner = get_provisioner()
    class Test4(InfraModel):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.model.net, u"192.168.23.0/24")
    model = Test4("test4")
    assert model.net.osid.value() is None
    provisioner.provision_infra_model(model)
    assert (model.net.osid.value() == model.subnet.network.osid.value() and
            model.net.osid.value() is not None)

def test005():
    provisioner = get_provisioner()
    class Test5(InfraModel):
        router = Router("wibbleRouter")
    model = Test5("test5")
    provisioner.provision_infra_model(model)
    assert model.router.osid.value()
    
def test006():
    provisioner = get_provisioner()
    class Test6(InfraModel):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
    model = Test6("test6")
    provisioner.provision_infra_model(model)
    assert model.server.osid.value() and model.server.addresses.value()
    
def test007():
    "this test is currently disabled"
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
    model = Test8("test8")
    provisioner.provision_infra_model(model)
#     provisioner.workflow_sorter.reset()
#     assert len(provisioner.workflow_sorter.servers) == 0
    assert True
    
def test009():
    provisioner = get_provisioner()
    class Test9(InfraModel):
        server = Server("simple", u'bogus image', "m1.small", key_name="perseverance_dev_key")
    model = Test9("test9")
    try:
        provisioner.provision_infra_model(model)
        assert False, "failed to raise an exception on a bogus image name"
    except ProvisionerException, _:
        evalues = " ".join([t[2].message.lower() for t in provisioner.agent.aborted_tasks])
        assert "image" in evalues

def test010():
    provisioner = get_provisioner()
    class Test10(InfraModel):
        server = Server("simple", u'Ubuntu 13.10', "m1.wibble", key_name="perseverance_dev_key")
    model = Test10("test10")
    try:
        provisioner.provision_infra_model(model)
        assert False, "failed to raise an exception on a bogus flavor name"
    except ProvisionerException, _:
        evalues = " ".join([t[2].message.lower() for t in provisioner.agent.aborted_tasks])
        assert "flavor" in evalues
        
def test011():
    provisioner = get_provisioner()
    class Test11(InfraModel):
        net = Network("wibble")
        server = Server("simple", u'Ubuntu 13.10', "m1.small", nics=[ctxt.model.net.name],
                        key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.model.server,
                         ctxt.model.server.iface0.addr0, pool="external")
    model = Test11("t11")
    rec = provisioner.provision_infra_model(model)
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
    model = Test12("t12")
    _ = [model.routable_group[i] for i in ["a", "b"]]
    rec = provisioner.provision_infra_model(model)
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
    model = Test13("test13")
    _ = [model.grid[i] for i in ["LN", "NY", "TK"]]
    rec = provisioner.provision_infra_model(model)
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
    model = Test14("t14")
    for i in range(3):
        for j in range(5):
            _ = model.collective[i].workers[j]
    _ = provisioner.provision_infra_model(model)
    assert len(model.components()) == 22
    
def test015():
    provisioner = get_provisioner()
    class Test15(InfraModel):
        g = MultiResourceGroup("testGroup",
                                net=Network("wibble"),
                                subnet=Subnet("WibbleSub", ctxt.comp.container.net, u'192.168.23.0/24'),
                                workers=MultiResource(Server("worker", u'Ubuntu 13.10', "m1.small",
                                                              nics=[ctxt.comp.container.container.net.name])))
    model = Test15("t15")
    _ = model.g[1].workers[1]
    rec = provisioner.provision_infra_model(model)
    assert rec
    
def test016():
    provisioner = get_provisioner()
    class Test16(InfraModel):
        net = Network("wibble")
        subnet = Subnet("WibbleSub", lambda _: [], u"192.168.23.0/24",
                        dns_nameservers=[u'8.8.8.8'])
    model = Test16("t16")
    try:
        provisioner.provision_infra_model(model)
        assert False, "We should have gotten an error about the network arg"
    except ProvisionerException, _:
        evalues = " ".join([t[2].message.lower() for t in provisioner.agent.aborted_tasks])
        assert "network" in evalues
        
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
    model = Test17("t17")
    _ = model.clusters["ny"].cluster[1]
    rec = provisioner.provision_infra_model(model)
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
    rec = prov.provision_infra_model(inst)
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
    rec = prov.provision_infra_model(inst)
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
    rec = prov.provision_infra_model(inst)
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
    rec = prov.provision_infra_model(inst)
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
    rec = prov.provision_infra_model(inst)
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
    prov.provision_infra_model(inst)
    assert ns.future("SERVER_IP").value()
    
def test031():
    "test basic KeyPair modeling capabilities"
    class KPTest(InfraModel):
        kp = KeyPair("kp_test", "pkn", os_name="kp_test",
                     pub_key_file=None, pub_key="wibble", force=False)
    inst = KPTest("thing")
    inst.kp.fix_arguments()
    assert (inst and inst.kp and inst.kp is not KPTest.kp
            and inst.kp.priv_key_name.value() == "pkn")
    
def test032():
    "test arg testing"
    try:
        class KPTest(InfraModel):
            kp = KeyPair("kp_test", "pkn", os_name="kp_test", force=False)
        assert False, "The class creation should have failed"
    except ProvisionerException, _:
        assert True
    
def test033():
    "test033 test getting a resource task for the KeyPair"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("kp_test", "pkn", os_name="kp_test",
                     pub_key_file=None, pub_key="wibble", force=False)
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
    
def test034():
    "test034 test provisioning an existing key"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn", pub_key_file=None, pub_key="wibble")
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert ost_support.MockNovaClient._keypairs_dict["test-key"].public_key == "startingkey"
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
        
def test035():
    "test035 test provisioning an existing key with overwrite"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn", pub_key_file=None, pub_key="wibble",
                     force=True)
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert ost_support.MockNovaClient._keypairs_dict["test-key"].public_key == "wibble"
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
        
def test036():
    "test036 test using a os_name instead of the KeyPair name"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn", pub_key_file=None, pub_key="wibble",
                     os_name="alt-key-name")
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert ost_support.MockNovaClient._keypairs_dict["alt-key-name"].public_key == "wibble"
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
        
def test037():
    "test037 making sure force doesn't mess with use os_name"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn", pub_key_file=None, pub_key="wibble2",
                     os_name="alt-key-name", force=True)
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert ost_support.MockNovaClient._keypairs_dict["alt-key-name"].public_key == "wibble2"
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
        
def test038():
    "test038: check if the key is properly pulled from a file"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn",
                     pub_key_file=find_file("actuator-dev-key.pub"),
                     os_name="alt-key-name", force=True)
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert (ost_support.MockNovaClient._keypairs_dict["alt-key-name"].public_key ==
                open(find_file("actuator-dev-key.pub"), "r").read())
    except ProvisionerException, _:
        assert False, "provisioning the public key failed"
        
def test039():
    "test039: ensure that we get an error if we can't find the key file"
    prov = get_provisioner()
    class KPTest(InfraModel):
        kp = KeyPair("test-key", "pkn", pub_key_file="no-such-file.pub")
    inst = KPTest("thing")
    try:
        prov.provision_infra_model(inst)
        assert False, "should have complained about finding the key file"
    except ProvisionerException, _:
        assert True
        
def test040():
    "test040: ensure that we require either a key file or a public key"
    try:
        class KPTest(InfraModel):
            kp = KeyPair("test-key", "pkn")
        assert False, "should have complained missing key arg"
    except ProvisionerException, _:
        assert True

def test041():
    "test041: ensure that we barf if both key file and pub key are supplied"
    try:
        class KPTest(InfraModel):
            kp = KeyPair("test-key", "pkn", pub_key="not me",
                         pub_key_file=find_file("actuator-dev-key.pub"))
        assert False, "should have complained missing key arg"
    except ProvisionerException, _:
        assert True
        
class FauxEngine(object):
    def get_context(self):
        from actuator.provisioners.openstack.support import OpenstackProvisioningRecord
        from actuator.provisioners.openstack.resource_tasks import RunContext
        return RunContext(OpenstackProvisioningRecord(1), "it", "just", "doesn't", "matter")
    
    
def test042():
    "test042: Check for basic operation of deprovision proto"
    from actuator.provisioners.openstack.resource_tasks import ProvisioningTask
 
    engine = FauxEngine()
    
    class NetTest(InfraModel):
        net = Network("deprov_net", admin_state_up=True)
    inst = NetTest("net")
    net = inst.net.value()
    pvt = ProvisioningTask(net)
    result = pvt.reverse(engine)
    assert result is None
    
    
def test043():
    "test043: provision/deprovision a network"
    from actuator.provisioners.openstack.resource_tasks import ProvisionNetworkTask
    
    engine = FauxEngine()
    
    class NetTest(InfraModel):
        net = Network("deprov_net", admin_state_up=True)
    inst = NetTest("net")
    net = inst.net.value()
    pvt = ProvisionNetworkTask(net)
    pvt.perform(engine)
    result = pvt.reverse(engine)
    assert result is None

def test044():
    "test044: provision/deprovision a subnet"
    from actuator.provisioners.openstack.resource_tasks import (ProvisionNetworkTask,
                                                                ProvisionSubnetTask)
    
    engine = FauxEngine()
    
    class NetTest(InfraModel):
        net = Network("deprov_net", admin_state_up=True)
        subnet = Subnet("deprov_subnet", ctxt.model.net, "192.168.20.0/24")
    inst = NetTest("sub")
    net = inst.net.value()
    sub = inst.subnet.value()
    pvt = ProvisionNetworkTask(net)
    inst.subnet.fix_arguments()
    psnt = ProvisionSubnetTask(sub)
    pvt.perform(engine)
    psnt.perform(engine)
    result = psnt.reverse(engine)
    assert result is None

def test045():
    "test045: provision/deprovision a security group"
    from actuator.provisioners.openstack.resource_tasks import ProvisionSecGroupTask
    
    engine = FauxEngine()
    
    class SGTest(InfraModel):
        sg = SecGroup("deprov_sg", description="test secgroup")
    inst = SGTest("net")
    net = inst.sg.value()
    psgt = ProvisionSecGroupTask(net)
    psgt.perform(engine)
    result = psgt.reverse(engine)
    assert result is None
    
def test046():
    "test046: provision/deprovision a server"
    from actuator.provisioners.openstack.resource_tasks import ProvisionServerTask
    
    engine = FauxEngine()
    
    class ServerTest(InfraModel):
        srvr = Server("deprov_server", u"Ubuntu 13.10", "m1.small",
                      key_name="perseverance_dev_key")
    inst = ServerTest("server")
    inst.srvr.fix_arguments()
    srvr = inst.srvr.value()
    pst = ProvisionServerTask(srvr)
    pst.perform(engine)
    result = pst.reverse(engine)
    assert result is None
    
def test047():
    "test047: provision/deprovision a router"
    from actuator.provisioners.openstack.resource_tasks import ProvisionRouterTask
    
    engine = FauxEngine()
    
    class RouterTest(InfraModel):
        router = Router("deprov_router")
    inst = RouterTest("router")
    router = inst.router.value()
    prt = ProvisionRouterTask(router)
    prt.perform(engine)
    result = prt.reverse(engine)
    assert result is None
    
def test048():
    "test048: provision/deprovision a router interface"
    from actuator.provisioners.openstack.resource_tasks import (ProvisionNetworkTask,
                                                                ProvisionSubnetTask,
                                                                ProvisionRouterTask,
                                                                ProvisionRouterInterfaceTask)

    engine = FauxEngine()
    
    class RITest(InfraModel):
        router = Router("deprov_ri")
        subnet = Subnet("deprov_ri", ctxt.model.network, u"192.168.23.0/24",
                        dns_nameservers=[u"8.8.8.8"])
        network = Network("deprov_ri")
        ri = RouterInterface("deprov_ri", ctxt.model.router, ctxt.model.subnet)
    
    inst = RITest(InfraModel)
    router = inst.router.value()
    subnet = inst.subnet.value()
    network = inst.network.value()
    ri = inst.ri.value()
    
    prt = ProvisionRouterTask(router)
    psnt = ProvisionSubnetTask(subnet)
    pnt = ProvisionNetworkTask(network)
    prit = ProvisionRouterInterfaceTask(ri)
    prt.perform(engine)
    pnt.perform(engine)
    psnt.perform(engine)
    inst.ri.fix_arguments()
    prit.perform(engine)
    result = prit.reverse(engine)
    assert result is None
    
def test049():
    "test049: provision/deprovision a floating ip"
    from actuator.provisioners.openstack.resource_tasks import (ProvisionFloatingIPTask,
                                                                ProvisionServerTask)
    engine = FauxEngine()
    
    class FIPTest(InfraModel):
        srvr = Server("deprov_server", u"Ubuntu 13.10", "m1.small",
                      key_name="perseverance_dev_key")
        fip = FloatingIP("deprov_fip", ctxt.model.srvr,
                         ctxt.model.srvr.iface0.addr0, pool="external")
    inst = FIPTest("fip")
    srvr = inst.srvr.value()
    fip = inst.fip.value()
    
    pst = ProvisionServerTask(srvr)
    pfipt = ProvisionFloatingIPTask(fip)
    inst.srvr.fix_arguments()
    pst.perform(engine)
    inst.fip.fix_arguments()
    pfipt.perform(engine)
    result = pfipt.reverse(engine)
    assert result is None

from actuator.provisioners.openstack.resource_tasks import ProvisionNetworkTask

class BreakableNetworkTask(ProvisionNetworkTask):
    """
    Used in a bunch of tests below
    """
    prov_cb = None
    deprov_cb = None
    def __init__(self, *args, **kwargs):
        super(BreakableNetworkTask, self).__init__(*args, **kwargs)
        self.prov_tries = 0
        self.do_prov_fail = False
        self.deprov_tries = 0
        self.do_deprov_fail = False
        
    def _perform(self, engine):
        if self.do_prov_fail:
            raise ProvisionerException("Nope!")
        super(BreakableNetworkTask, self)._perform(engine)
        self.prov_tries += 1
        if self.prov_cb is not None:
            self.prov_cb(self)
        
    def _reverse(self, engine):
        if self.do_deprov_fail:
            raise ProvisionerException("Nope!")
        super(BreakableNetworkTask, self)._reverse(engine)
        self.deprov_tries += 1
        if self.deprov_cb is not None:
            self.deprov_cb(self)
        
def prov_deprov_setup():
    engine = FauxEngine()

    class Test(InfraModel):
        net = Network("wibble")
    inst = Test("wibble")
    return engine, inst
            
def test050():
    'test050: test no multiple provisioning'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.perform(engine)
    pnt.perform(engine)
    assert pnt.prov_tries == 1
    
def test051():
    'test051: test provision after fail'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.do_prov_fail = True
    try: pnt.perform(engine)
    except: pass
    pnt.do_prov_fail = False
    pnt.perform(engine)
    assert pnt.prov_tries == 1
    
def test052():
    'test052: test no deprov before prov'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.reverse(engine)
    assert pnt.prov_tries == 0 and pnt.deprov_tries == 0
    
def test053():
    'test053: test deprov after prov'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.perform(engine)
    pnt.reverse(engine)
    assert pnt.prov_tries == 1 and pnt.deprov_tries == 1
    
def test054():
    'test054: test no prov after deprov'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.perform(engine)
    pnt.reverse(engine)
    pnt.perform(engine)
    assert pnt.prov_tries == 1 and pnt.deprov_tries == 1
    
def test055():
    'test055: test deprov after one failed deprov'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.perform(engine)
    pnt.do_deprov_fail = True
    try: pnt.reverse(engine)
    except: pass
    pnt.do_deprov_fail = False
    pnt.reverse(engine)
    assert pnt.deprov_tries == 1
    
def test056():
    'test056: no multiple deprov after prov'
    engine, inst = prov_deprov_setup()
    net = inst.net.value()
    pnt = BreakableNetworkTask(net)
    pnt.perform(engine)
    pnt.reverse(engine)
    pnt.reverse(engine)
    assert pnt.prov_tries == 1 and pnt.deprov_tries == 1
    
class ResumeNetwork(Network):
    def __init__(self, *args, **kwargs):
        self.do_raise = False
        super(ResumeNetwork, self).__init__(*args, **kwargs)
        self.__admin_state_up = None
        
    def set_raise(self, do_raise):
        self.do_raise = do_raise
    
    def get_as(self):
        if self.do_raise:
            self.do_raise = False
            raise Exception("SUMMAT BAD DONE HAPPENED")
        return self.__admin_state_up
    
    def set_as(self, asu):
        self.__admin_state_up = asu
    admin_state_up = property(get_as, set_as)
    
class CaptureTries(object):
    def __init__(self):
        self.prov_count = 0
        self.tasks_seen = set()
    def cb(self, t):
        self.prov_count = t.prov_tries
        self.tasks_seen.add(t)

def test057():
    'test057: resume provisioning an infra'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
    
    ct = CaptureTries()
                    
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    inst.net.set_raise(True)
    BreakableNetworkTask.prov_cb = ct.cb
    try:
        prov.provision_infra_model(inst)
        raise False, "the first provision didn't raise an exception; ERROR IN TEST"
    except Exception, _:
        pass
    
    inst.net.set_raise(False)
    
    try:
        prov.provision_infra_model(inst)
    except Exception, _:
        import traceback, sys
        et, ev, tb = sys.exc_info()
        print "UNEXEPECTED abort:"
        traceback.print_exception(et, ev, tb)
        for t, et, ev, tb in  prov.agent.get_aborted_tasks():
            print "Aborted task %s" % t.name
            traceback.print_exception(et, ev, tb)
        raise
    assert ct.prov_count == 1
    
def test058():
    'test058: resume provisioning an infra; complete just once'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
     
    ct = CaptureTries()
                     
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    inst.net.set_raise(True)
    BreakableNetworkTask.prov_cb = ct.cb
    try:
        prov.provision_infra_model(inst)
        raise False, "the first provision didn't raise an exception"
    except Exception, _:
        pass
    inst.net.set_raise(False)
    prov.provision_infra_model(inst)
    prov.provision_infra_model(inst)
    assert ct.prov_count == 1 and len(ct.tasks_seen) == 1
    
def test059():
    'test059: multiple provisions, just one performance'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
     
    ct = CaptureTries()
                     
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    BreakableNetworkTask.prov_cb = ct.cb
    prov.provision_infra_model(inst)
    prov.provision_infra_model(inst)
    assert ct.prov_count == 1 and len(ct.tasks_seen) == 1
    
def test060():
    'test060: test fail orchestration'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
    from actuator import ActuatorOrchestration
    
    ct = CaptureTries()
                    
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    inst.net.set_raise(True)
    BreakableNetworkTask.prov_cb = ct.cb
    orch = ActuatorOrchestration(infra_model_inst=inst, provisioner=prov)
    result = orch.initiate_system()
    assert not result
    
def test061():
    'test061: test resume to success with orchestration'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
    from actuator import ActuatorOrchestration
    
    ct = CaptureTries()
                    
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    inst.net.set_raise(True)
    BreakableNetworkTask.prov_cb = ct.cb
    orch = ActuatorOrchestration(infra_model_inst=inst, provisioner=prov)
    result1 = orch.initiate_system()

    inst.net.set_raise(False)
    result2 = orch.initiate_system()
    assert not result1 and result2 and ct.prov_count == 1
    
def test062():
    'test062: two initiates only perform the tasks once'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
    from actuator import ActuatorOrchestration
    
    ct = CaptureTries()
                    
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    BreakableNetworkTask.prov_cb = ct.cb
    orch = ActuatorOrchestration(infra_model_inst=inst, provisioner=prov)
    result1 = orch.initiate_system()
    result2 = orch.initiate_system()
    assert result1 and result2 and ct.prov_count == 1
    
def test063():
    "test063: deprovision infra"
    class DecoInfra(InfraModel):
        net = Network("deco")
    deco = DecoInfra("deco")
    prov = get_provisioner()
    prov.provision_infra_model(deco)
    prov.deprovision_infra_model(deco)
    assert True
    
def test064():
    'test064: run the teardown after initiation'
    from actuator.provisioners.openstack.resource_tasks import _rt_domain
    from actuator.utils import capture_mapping
    from actuator import ActuatorOrchestration
    
    ct = CaptureTries()
                    
    capture_mapping(_rt_domain, ResumeNetwork)(BreakableNetworkTask)
    class ResumeInfra(InfraModel):
        net = ResumeNetwork("resume")
    inst = ResumeInfra('resume')
    assert inst.net.name.value() is 'resume'
    prov = get_provisioner()
    BreakableNetworkTask.prov_cb = ct.cb
    orch = ActuatorOrchestration(infra_model_inst=inst, provisioner=prov)
    result1 = orch.initiate_system()
    result2 = orch.teardown_system()
    assert result1 and result2 and ct.prov_count == 1
    
#these next tests are looking at integration with persistence, so the classes
#need to be at the global module level

def persistence_helper(inst):
    prov = get_provisioner()
    orch = ActuatorOrchestration(infra_model_inst=inst, provisioner=prov)
    _ = orch.initiate_system()
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    return op.infra_model_inst

class Infra65(InfraModel):
    s = Server("s", u"Ubuntu 13.10", "m1.small")
    
def test065():
    """
    test065: check persistence of a model with a single server
    """
    i65 = Infra65("65")
    i65p = persistence_helper(i65)
    assert (i65p.s.imageName.value() == u"Ubuntu 13.10" and
            i65p.s.flavorName.value() == "m1.small")
    
class Infra66(InfraModel):
    s = Server("s", u"Ubuntu 13.10", "m1.small", userdata={"k1":1, "k2":2})
    
def test066():
    """
    test066: another single server persistence test, check more args
    """
    i66 = Infra66("66")
    i66p = persistence_helper(i66)
    assert i66p.s.userdata.value()["k1"] == 1

def udfunc(context):
    return {"compname":ctxt.name(context)}

class Infra67(InfraModel):
    grid = MultiResource(Server("node", u"Ubuntu 13.10", "m1.small",
                         userdata=udfunc))
    
def test067():
    """
    test067: persistence test: infra model with a MultiResource wrapping a server
    """
    i67 = Infra67("67")
    for i in range(5):
        _ = i67.grid[i]    
    i67p = persistence_helper(i67)
    assert (len(i67p.grid) == 5 and
            i67p.grid[1].userdata["compname"] == "1")

class Infra68(InfraModel):
    net = Network("net")

def test068():
    """
    test068: persistence test for Network
    """
    i68 = Infra68("68")
    i68p = persistence_helper(i68)
    assert (i68p.net.name.value() == "net")
    
class Infra69(InfraModel):
    net = Network("net")
    srvr = Server("node", u"Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
    
def test069():
    """
    test069: check if a Server referencing a Network reanimates properly
    """
    i69 = Infra69("69")
    i69p = persistence_helper(i69)
    assert (i69p.srvr.nics.value()[0] is i69p.net.value())
    
class Infra70(InfraModel):
    g = ResourceGroup("g",
                      net=Network("net"),
                      srvr = Server("node", u"Ubuntu 13.10", "m1.small",
                                    nics=[ctxt.comp.container.net]))
    
def test070():
    """
    test070: Persist/reanimate a ResourceGroup with inter-relating resources
    """
    i70 = Infra70("70")
    i70p = persistence_helper(i70)
    assert (i70p.g.net.value() is i70p.g.srvr.nics.value()[0])
    
class Infra71(InfraModel):
    g = ResourceGroup("g",
                      net=Network("net"),
                      grid=MultiResource(Server("node", u"Ubuntu 13.10",
                                                "m1.small",
                                                nics=[ctxt.comp.container.container.net])))
    
def test071():
    """
    test071: Persist/reanimate a ResourceGroup with embedded, interrelated resources in a MultiResource
    """
    i71 = Infra71("71")
    for i in range(5):
        _ = i71.g.grid[i]
    i71p = persistence_helper(i71)
    assert (len(i71p.g.grid) == 5 and
            i71p.g.net.value() is i71p.g.grid[4].nics.value()[0])
    
class Infra72(InfraModel):
    net = Network("main")
    cells = MultiResourceGroup("cell",
                               slaves=MultiResource(Server("slave",
                                                           u"Ubuntu 13.10",
                                                           "m1.small",
                                                           nics=[ctxt.comp.container.container.subnet])),
                               subnet=Network("sn"),
                               boss=Server("boss", u"Ubuntu 13.10",
                                           "m1.small",
                                           nics=[ctxt.model.net,
                                                 ctxt.comp.container.subnet]))
    
def test072():
    """
    test072: Persist/reanimate MultiResouce inside a MultiResourceGroup with related resources
    """
    i72 = Infra72("72")
    for i in range(5):
        cell = i72.cells[i]
        for j in range(20):
            _ = cell.slaves[j]
    i72p = persistence_helper(i72)
    assert (len(i72p.cells) == 5 and
            len(i72p.cells[0].slaves) == 20 and
            i72p.cells[0].subnet.value() is i72p.cells[0].slaves[10].nics.value()[0] and
            i72p.net.value() is i72p.cells[1].boss.nics.value()[0] and
            i72p.cells[1].subnet.value() is i72p.cells[1].boss.nics.value()[1])
    
class Infra73(InfraModel):
    router = Router("r", admin_state_up=False)
    
def test073():
    """
    test073: persist/reanimate Router
    """
    i73 = Infra73("73")
    i73p = persistence_helper(i73)
    assert i73.router.admin_state_up.value() == i73p.router.admin_state_up.value()
    
class Infra74(InfraModel):
    net = Network("net")
    sn = Subnet("sn", ctxt.model.net, "192.168.6.0/24",
                dns_nameservers=["8.8.8.8"])
    
def test074():
    """
    test074: persist/reanimate Subnet related to a network
    """
    i74 = Infra74("74")
    i74p = persistence_helper(i74)
    assert (i74p.net.value() is i74p.sn.network.value() and
            i74p.sn.cidr.value() == "192.168.6.0/24" and
            u"8.8.8.8" in i74p.sn.dns_nameservers.value())
    
class Infra75(InfraModel):
    rg = RouterGateway("argee", ctxt.model.router, "external")
    router = Router("rotter")
    
def test075():
    """
    test075: persist/reanimate a RouterGateway related to a Router
    """
    i75 = Infra75("75")
    i75p = persistence_helper(i75)
    assert (i75p.rg.name.value() == "argee" and
            i75p.rg.router.value() is i75p.router.value())
    
class Infra76(InfraModel):
    router = Router("rotter")
    net = Network("knitwork")
    sn = Subnet("subknit", ctxt.model.net, "192.168.6.0/24",
                dns_nameservers=["8.8.8.8"])
    ri = RouterInterface("rhodie", ctxt.model.router, ctxt.model.sn)
    
def test076():
    """
    test076: persist/reanimate Router/RouterInterface/Network/Subnet
    """
    i76 = Infra76("76")
    i76p = persistence_helper(i76)
    assert (i76p.ri.router.value() is i76p.router.value() and
            i76p.ri.subnet.value() is i76p.sn.value() and
            i76p.sn.network.value() is i76p.net.value())
    
class Infra77(InfraModel):
    s = Server("wibble", u"Ubuntu 13.10", "m1.small")
    fip = FloatingIP("wibble_fip", ctxt.model.s,
                     ctxt.model.s.iface0.addr0)
    
def test077():
    """
    test077: persist/reanimate FloatingIP related to a Server
    """
    i77 = Infra77("77")
    i77p = persistence_helper(i77)
    assert i77p.fip.server.value() is i77p.s.value()
    
class Infra78(InfraModel):
    sg = SecGroup("essgee", "The king of groups")
    s = Server("s", u"Ubuntu 13.10", "m1.small",
               security_groups=[ctxt.model.sg])
    
def test078():
    """
    test078: persist/reanimate a SecGroup related to a Server
    """
    i78 = Infra78("78")
    i78p = persistence_helper(i78)
    assert (i78p.sg.value() in i78p.s.security_groups.value() and
            "king" in i78p.sg.description.value())
    
    
def do_all():
    globs = globals()
    tests = []
    for k, v in globs.items():
        if k.startswith("test") and callable(v):
            tests.append(k)
    tests.sort()
    for k in tests:
        print "Doing ", k
        globs[k]()
            
if __name__ == "__main__":
    do_all()

