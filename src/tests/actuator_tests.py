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


def test01():
    """
    test01: Check that orchestrators persist and reanimate themselves
    """
    orch = ActuatorOrchestration()
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch, "test04")
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    for c in i0.components():
        c.fix_arguments()
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch, "t5")
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch, "t6")
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    for c in i0.components():
        c.fix_arguments()
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
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
    for c in i0.components():
        c.fix_arguments()
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    i1 = op.infra_model_inst
    assert (len(i1.clusters[2].slaves) == Infra7.num_slaves and
            i1.clusters[2].value() is not i1.clusters[1].value() and
            i1.clusters[0].slaves[0] is not i1.clusters[1].slaves[0] and
            i1.clusters[1].name.value() == "cell_1")
    
    
#modeling.KeyAsAttr is going to not come back properly unless
#something is done to flag that these are objects and not just
#numeric strings.
    
    
def do_all():
    test08()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()

