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

import json
from actuator import (ActuatorOrchestration, ctxt, MultiResource, ResourceGroup,
                      MultiResourceGroup)
from actuator import InfraModel
from actuator.provisioners.example_resources import Server, Network, Queue
from actuator.utils import persist_to_dict, reanimate_from_dict, adb
from actuator.namespace import NamespaceModel, Role, Var


def ns_persistence_helper(ns_model=None, infra_model=None):
    orch = ActuatorOrchestration(infra_model_inst=infra_model,
                                 namespace_model_inst=ns_model)
    if infra_model is not None:
        for c in infra_model.components():
            c.fix_arguments()
    if ns_model is not None:
        if infra_model is not None:
            ns_model.set_infra_model(infra_model)
        for c in ns_model.components():
            c.fix_arguments()
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    o2 = reanimate_from_dict(d)
    return o2

def test01():
    """
    test01: Check that orchestrators persist and reanimate themselves
    """
    op = ns_persistence_helper(None, None)
    assert op
     
     
class Infra1(InfraModel):
    pass
     
     
def test02():
    """
    test02: Check that the orchestrator persists and reanimates with an empty infra model
    """
    orch = ActuatorOrchestration(infra_model_inst=Infra1("t2"))
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    assert (hasattr(op, "infra_model_inst") and
            orch.infra_model_inst.name == op.infra_model_inst.name and
            orch.infra_model_inst.nexus is not op.infra_model_inst.nexus and 
            op.infra_model_inst.nexus is not None and
            op.infra_model_inst.nexus.find_instance(Infra1) is op.infra_model_inst)
     
class Infra2(InfraModel):
    s = Server("s1", mem="8GB")
     
def test03():
    """
    test03: save orchestrator with an infra with a single server
    """
    i0 = Infra2("test3")
    op = ns_persistence_helper(None, i0)
    assert (hasattr(op.infra_model_inst, "s") and
            op.infra_model_inst.s.name.value() == i0.s.name.value() and
            op.infra_model_inst.s.mem.value() == i0.s.mem.value())
     
 
class Infra3(InfraModel):
    n = Network("net", cidr="192.168.6.0/24")
     
     
def test04():
    """
    test04: save orch with an infra with a single network
    """
    i0 = Infra3("i3")
    op = ns_persistence_helper(None, i0)
    assert (hasattr(op.infra_model_inst, "n") and
            op.infra_model_inst.n.name.value() == i0.n.name.value() and
            op.infra_model_inst.n.cidr.value() == i0.n.cidr.value())
     
     
class Infra4(InfraModel):
    n = Network("net", cidr="192.168.6.0/24")
    s = Server("server", network=ctxt.model.n)
     
 
def test05():
    """
    test05: save infra with a network an server, with the server using ctxt to ref the network
    """
    i0 = Infra4("test05")
    op = ns_persistence_helper(None, i0)
    assert (op.infra_model_inst.n.value() is op.infra_model_inst.s.network.value())
     
 
class Infra5(InfraModel):
    cluster = MultiResource(Server("node", mem="8GB"))
     
def test06():
    """
    test06: save an infra with servers in a MultiResource container
    """
    i0 = Infra5("test06")
    for i in range(5):
        _ = i0.cluster[i]
    op = ns_persistence_helper(None, i0)
    assert (len(op.infra_model_inst.cluster) == 5 and
            op.infra_model_inst.cluster[0].mem.value() == "8GB" and
            op.infra_model_inst.cluster[0].name.value() == "node_0")
     
     
class Infra6(InfraModel):
    group = ResourceGroup("group",
                          server=Server("server", mem="8GB", net=ctxt.model.group.network),
                          network=Network("net", cidr="192.168.6.0/24"),
                          queue=Queue("q", host=ctxt.model.group.server, port=8000))
     
def test07():
    """
    test07: check persistence with a ResourceGroup
    """
    i0 = Infra6("i6")
    op = ns_persistence_helper(None, i0)
    i1 = op.infra_model_inst
    assert (i1.group.server.net.value() is i1.group.network.value() and
            i1.group.queue.host.value() is i1.group.server.value() and
            i1.group.server.mem.value() == "8GB" and
            i1.group.queue.name.value() == "q")
     
     
class Infra7(InfraModel):
    num_slaves = 20
    master = Server("master", mem="8GB", net=ctxt.model.network)
    network = Network("net", cidr="192.168.6.0/24")
    clusters = MultiResourceGroup("cell",
                                  foreman=Server("foreman", mem="8GB",
                                                net=ctxt.model.network),
                                  queue=Queue("q", host=ctxt.comp.container.foreman),
                                  slaves=MultiResource(Server("slave",
                                                              mem="8GB",
                                                              net=ctxt.model.network)))
    def size(self, size):
        for i in range(size):
            c = self.clusters[i]
            for j in range(self.num_slaves):
                _ = c.slaves[j]
     
def test08():
    """
    Check that we can save/reanimate a MultiResourceGroup
    """
    i0 = Infra7("i8")
    i0.size(5)
    _ = i0.refs_for_components()
    op = ns_persistence_helper(None, i0)
    i1 = op.infra_model_inst
    assert (len(i1.clusters[2].slaves) == Infra7.num_slaves and
            i1.clusters[2].value() is not i1.clusters[1].value() and
            i1.clusters[0].slaves[0] is not i1.clusters[1].slaves[0] and
            i1.clusters[1].name.value() == "cell_1")
     
class NS9(NamespaceModel):
    pass
 
def test09():
    """
    test09: check basic namespace persist/reanimate as part of a orchestrator
    """
    i9 = Infra7("i9")
    ns9 = NS9()
    ns9p = ns_persistence_helper(ns9, i9).namespace_model_inst
    assert ns9p
     
def test10():
    """
    test10: check that nexus is consistent across models (infra and namespace)
    """
    i10 = Infra7("i10")
    ns10 = NS9()
    op = ns_persistence_helper(ns10, i10)
    assert op.namespace_model_inst.nexus is op.infra_model_inst.nexus

class NS11(NamespaceModel):
    r = Role("ro1e1")

def test11():
    """
    test11: check if a simple Role can be reanimated
    """
    ns11 = NS11()
    op = ns_persistence_helper(ns11, None)
    nsm = op.namespace_model_inst
    assert (nsm.r and
            nsm.r.name.value() == "ro1e1" and
            nsm.r.host_ref.value() is None and
            not nsm.r.variables.value() and
            not nsm.r.overrides.value())
    
class NS12(NamespaceModel):
    r = Role("role", variables=[Var("v1", "summat")])
    
def test12():
    ns12 = NS12()
    op = ns_persistence_helper(ns12, None)
    nsm = op.namespace_model_inst
    assert (nsm.r.get_visible_vars() and
            nsm.r.var_value("v1") == "summat")
    
class Infra13(InfraModel):
    s = Server("wibble")    
     
class NS13(NamespaceModel):
    r = Role("role", host_ref=Infra13.s)
     
def test13():
    infra = Infra13("13")
    ns = NS13()
    op = ns_persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    im = op.infra_model_inst
    assert (nsm.r.host_ref.value() is im.s.value())
    
    
#need a test that puts a model ref into the value of a Var
    
#modeling.KeyAsAttr is going to not come back properly unless
#something is done to flag that these are objects and not just
#numeric strings.
    
    
def do_all():
    test13()
    g = globals()
    keys = list(g.keys())
    keys.sort()
    for k in keys:
        v = g[k]
        if k.startswith("test") and callable(v):
            print "Running ", k
            v()
    
if __name__ == "__main__":
    do_all()

