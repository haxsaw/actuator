'''
NOTE: this module relies on ost_support for the mocks it needs, which in turn relies on Faker
for generating test data. The faker is put into known initial state so that it generates the 
same series of test data with each run, allowing us to test returned values properly. That means
that the order of calls into the mocks must not change from run to run or else the expected data
won't be generated. The lesson here is that as tests are added, they should always be added to the
end of the list of tests, and never inserted in between existing tests.
Created on 25 Aug 2014

@author: tom
'''

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
ocf.set_neutron_client_class(ost_support.MockNeutronClient)
ocf.set_nova_client_class(ost_support.MockNovaClient)

from actuator import InfraSpec, ProvisionerException, MultiComponentGroup, MultiComponent, ctxt
from actuator.provisioners.openstack.openstack import OpenstackProvisioner
from actuator.provisioners.openstack.components import (Server, Network,
                                                           Router, FloatingIP, Subnet)


def get_provisioner():
    return OpenstackProvisioner("it", "just", "doesn't", "matter")


def test001():
    provisioner = get_provisioner()
    class Test1(InfraSpec):
        net = Network("test1Net")
    spec = Test1("test1")
    assert spec.net.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.net.osid.value()
    
def test002():
    provisioner = get_provisioner()
    class Test2(InfraSpec):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
        fip = FloatingIP("fip1", ctxt.infra.server,
                         ctxt.infra.server.iface0.addr0, pool="external")
    spec = Test2("test2")
    assert spec.fip.ip.value() is None and spec.fip.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.fip.ip.value() and spec.fip.osid.value()
    
def test003():
    provisioner = get_provisioner()
    class Test3(InfraSpec):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.infra.net, u"192.168.23.0/24")
    spec = Test3("test3")
    assert spec.subnet.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert spec.subnet.osid.value()

def test004():
    provisioner = get_provisioner()
    class Test4(InfraSpec):
        net = Network("wibbleNet")
        subnet = Subnet("wibbleSub", ctxt.infra.net, u"192.168.23.0/24")
    spec = Test4("test4")
    assert spec.net.osid.value() is None
    provisioner.provision_infra_spec(spec)
    assert (spec.net.osid.value() == spec.subnet.network.value() and
            spec.net.osid.value() is not None)

def test005():
    provisioner = get_provisioner()
    class Test5(InfraSpec):
        router = Router("wibbleRouter")
    spec = Test5("test5")
    provisioner.provision_infra_spec(spec)
    assert spec.router.osid.value()
    
def test006():
    provisioner = get_provisioner()
    class Test6(InfraSpec):
        server = Server("simple", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
    spec = Test6("test6")
    provisioner.provision_infra_spec(spec)
    assert spec.server.osid.value() and spec.server.addresses.value()
    
def test007():
    try:
        class Test7(InfraSpec):
            net = Network("wibbleNet")
            subnet = Subnet("wibbleSub", "net", u'300.168.23.0/24')
            #CIDR string checking has been disabled
#         assert False, "There should have been an exception regarding the cidr string"
    except ProvisionerException, _:
        assert True
        
def test008():
    provisioner = get_provisioner()
    class Test8(InfraSpec):
        net = Network("wibbleNet")
        subnet = Subnet("WibbleSub", ctxt.infra.net, u'192.168.22.0/24')
        router = Router("wibbleRouter")
        srvr1 = Server("simple1", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
        srvr2 = Server("simple2", u"Ubuntu 13.10", "m1.small", key_name="perseverance_dev_key")
    spec = Test8("test8")
    provisioner.provision_infra_spec(spec)
    provisioner.workflow_sorter.reset()
    assert len(provisioner.workflow_sorter.servers) == 0
    
def test009():
    provisioner = get_provisioner()
    class Test9(InfraSpec):
        server = Server("simple", u'bogus image', "m1.small", key_name="perseverance_dev_key")
    spec = Test9("test9")
    try:
        provisioner.provision_infra_spec(spec)
        assert False, "failed to raise an exception on a bogus image name"
    except ProvisionerException, e:
        assert "image" in e.message.lower()

def test010():
    provisioner = get_provisioner()
    class Test10(InfraSpec):
        server = Server("simple", u'Ubuntu 13.10', "m1.wibble", key_name="perseverance_dev_key")
    spec = Test10("test10")
    try:
        provisioner.provision_infra_spec(spec)
        assert False, "failed to raise an exception on a bogus flavor name"
    except ProvisionerException, e:
        assert "flavor" in e.message.lower()
        
def test011():
    provisioner = get_provisioner()
    class Test11(InfraSpec):
        net = Network("wibble")
        server = Server("simple", u'Ubuntu 13.10', "m1.small", nics=[ctxt.infra.net.logicalName],
                        key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.infra.server,
                         ctxt.infra.server.iface0.addr0, pool="external")
    spec = Test11("t11")
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test012():
    provisioner = get_provisioner()
    class Test12(InfraSpec):
        net = Network("wibble")
        routable_group = MultiComponentGroup("routables",
                                             server=Server("simple", u'Ubuntu 13.10', "m1.small",
                                                           nics=[ctxt.infra.net.logicalName],
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
    class Test13(InfraSpec):
        subnet = Subnet("WibbleSub", ctxt.infra.net, u'192.168.22.0/24')
        net = Network("wibble")
        grid = MultiComponent(Server("simple", u'Ubuntu 13.10', "m1.small",
                                     nics=[ctxt.infra.net.logicalName],
                                     key_name="perseverance_dev_key"))
        gateway = Server("gateway", u'Ubuntu 13.10', "m1.small",
                         nics=[ctxt.infra.net.logicalName], key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.infra.gateway,
                         ctxt.infra.gateway.iface0.addr0, pool="external")
    spec = Test13("test13")
    _ = [spec.grid[i] for i in ["LN", "NY", "TK"]]
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test014():
    provisioner = get_provisioner()
    class Test14(InfraSpec):
        subnet = Subnet("WibbleSub", ctxt.infra.net, u'192.168.22.0/24')
        net = Network("wibble")
        collective = MultiComponentGroup("collective",
                                         foreman = Server("gateway", u'Ubuntu 13.10', "m1.small",
                                                          nics=[ctxt.infra.net.logicalName],
                                                          key_name="perseverance_dev_key"),
                                         workers = MultiComponent(Server("simple", u'Ubuntu 13.10', "m1.small",
                                                                         nics=[ctxt.infra.net.logicalName],
                                                                         key_name="perseverance_dev_key")))
        gateway = Server("gateway", u'Ubuntu 13.10', "m1.small",
                         nics=[ctxt.infra.net.logicalName], key_name="perseverance_dev_key")
        fip = FloatingIP("fip", ctxt.infra.gateway,
                         ctxt.infra.gateway.iface0.addr0, pool="external")
    spec = Test14("t14")
    for i in range(3):
        for j in range(5):
            _ = spec.collective[i].workers[j]
    rec = provisioner.provision_infra_spec(spec)
    assert len(spec.provisionables()) == 22
    
def test015():
    provisioner = get_provisioner()
    class Test15(InfraSpec):
        g = MultiComponentGroup("testGroup",
                                net=Network("wibble"),
                                subnet=Subnet("WibbleSub", ctxt.comp.container.net, u'192.168.23.0/24'),
                                workers=MultiComponent(Server("worker", u'Ubuntu 13.10', "m1.small",
                                                              nics=[ctxt.comp.container.container.net.logicalName])))
    spec = Test15("t15")
    _ = spec.g[1].workers[1]
    rec = provisioner.provision_infra_spec(spec)
    assert rec
    
def test016():
    provisioner = get_provisioner()
    class Test16(InfraSpec):
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
    class Test17(InfraSpec):
        net = Network("wibble")
        subnet = Subnet("WibbleSub", ctxt.infra.net, u"192.168.23.0/24",
                        dns_nameservers=[u'8.8.8.8'])
        s1 = Server("perseverance1", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.net.logicalName])
        clusters = MultiComponentGroup("clusters",
                                       cluster_net=Network("wibbleNet"),
                                       cluster_sub=Subnet("cluster_sub", ctxt.comp.container.cluster_net,
                                                          u'192.168.%d.0/30'),
                                       cluster_foreman = Server("cluster_foreman", "Ubuntu 13.10", "m1.small",
                                                                nics=[ctxt.comp.container.cluster_net.logicalName]),
                                       cluster=MultiComponent(Server("cluster_node", "Ubuntu 13.10", "m1.small",
                                                                     nics=[ctxt.comp.container.container.cluster_net.logicalName])))
    spec = Test17("t17")
    _ = spec.clusters["ny"].cluster[1]
    rec = provisioner.provision_infra_spec(spec)
    assert rec

def do_all():
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
