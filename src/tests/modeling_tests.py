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
Created on 7 Jun 2014
'''
from actuator import (MultiComponent, 
                          MultiComponentGroup, ComponentGroup, ctxt)
from actuator.infra import InfraModel, StaticServer, MultiResource
from actuator.provisioners.example_resources import Server
from actuator.modeling import CallContext
from actuator.namespace import Var, NamespaceModel, with_variables, Role,\
    MultiRole


def setup():
    pass


def test01():
    from actuator.modeling import _ComputeModelComponents
    class NoCompSource(_ComputeModelComponents):
        pass
    cs = NoCompSource()
    try:
        _ = cs._comp_source()
        assert False, "Non-overridden _comp_source() should have raised"
    except TypeError, e:
        assert "Derived class must implement" in e.message
        
def test02():
    try:
        _ = ComponentGroup("oopsGroup", server=Server("server", mem="8GB"), oops="not me")
        assert False, "Bad arg to ComponentGroup not caught"
    except TypeError, e:
        assert "isn't a kind of AbstractModelingEntity".lower() in e.message.lower()

def test03():
    ce = ctxt.one.two.three
    assert list(ce._path) == ["three", "two", "one"]
    
def test04():
    ce = ctxt.model.infra.grid[0]
    path = list(ce._path[1:])
    ki = ce._path[0]
    assert [ki.key] + path == ["0", "grid", "infra", "model"]
    
def test05():
    class Infra(InfraModel):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    for i in range(3):
        _ = inst.grid[i]
    assert set(inst.grid) == set(["0", "1", "2"])

def test06():
    class Infra(InfraModel):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    for i in range(3):
        _ = inst.grid[i]
    nada = "nada"
    assert inst.grid.get("10", default=nada) == nada
    
def test07():
    class Infra(InfraModel):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    assert not inst.grid
    
    
class FakeReference(object):
    """
    This class is used to act like a component in a model simply to satisfy the
    interface contract of AbstractModelReference in order to construct
    CallContext objects in tests below
    """
    def __init__(self, name):
        self._name = name
        

def test08():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    qexp = Infra.q.clusters.all().workers
    for i in range(2):
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 20
    
def test09():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    qexp = Infra.q.clusters.all().workers.keyin([0, 1, 2, 3, 4])
    for i in range(2):
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 10

def test10():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    qexp = Infra.q.clusters.match("(NY|LN)").workers
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 20

def test11():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    qexp = Infra.q.clusters.no_match("(NY|LN)").workers
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 30

def test12():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    
    def evens_only(key):
        return int(key) % 2 == 0
    
    qexp = Infra.q.clusters.workers.pred(evens_only)
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 25

def test13():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    
    def evens_only(key):
        return int(key) % 2 == 0
    
    qexp = Infra.q.clusters.match("(LN|NY)").workers.pred(evens_only)
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 10

def test14():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       cell=ComponentGroup("cell",
                                                           foreman=Server("foreman", mem="8"),
                                                           workers=MultiComponent(Server("worker", mem="8GB"))
                                                           )
                                       )
    infra = Infra("infra")
    
    def evens_only(key):
        return int(key) % 2 == 0
    
    qexp = Infra.q.clusters.match("(LN|NY)").cell.workers.pred(evens_only)
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.cell.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 10

def test15():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    qexp = Infra.q.union(Infra.q.clusters.match("(NY|LN)").workers,
                         Infra.q.clusters.key("SG").leader)
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 21

def test16():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    
    def evens_only(key):
        return int(key) % 2 == 0
    
    def lt_seven(key):
        return int(key) < 7
    
    qexp = Infra.q.clusters.workers.pred(evens_only).pred(lt_seven)
    
    for i in ["NY", "LN", "SG", "TK", "ZU"]:
        cluster = infra.clusters[i]
        for j in range(10):
            _ = cluster.workers[j]
    ctxt = CallContext(infra, FakeReference("wibble"))
    result = qexp(ctxt)
    assert len(result) == 20

def test17():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    try:
        _ = Infra.q.cluster.workers
        assert False, "This should have complained about 'cluster' not being an attribute"
    except AttributeError, e:
        assert "cluster" in e.message.lower()
        
def test18():
    class Infra(InfraModel):
        clusters = MultiComponentGroup("cluster",
                                       leader=Server("leader", mem="8GB"),
                                       workers=MultiComponent(Server("worker", mem="8GB")))
    infra = Infra("infra")
    assert infra.nexus
    
def test19():
    class InfraIPTest(InfraModel):
        s = StaticServer("sommat", "127.0.0.1")
        
    infra = InfraIPTest("test")
    infra.s.fix_arguments()
    
    class IPTest(NamespaceModel):
        with_variables(Var("ADDY", ctxt.model.infra.s.get_ip))
        r = Role("bogus")
        
    ns = IPTest()
    ns.set_infra_model(infra)
    
    v, o = ns.find_variable("ADDY")
    assert v.get_value(ns.r) == "127.0.0.1"
    
def host_list(ctx_exp, sep_char=" "):
    def host_list_inner(ctx):
        hlist = list(ctx_exp(ctx))
        #this next line is needed as the framework isn't doing the
        #arg fixing for us
        _ = [h.host_ref.fix_arguments() for h in hlist]
        ip_list = [h.host_ref.get_ip() for h in hlist]
        return sep_char.join(ip_list)
    return host_list_inner

def test20():
    class IPFactory(object):
        def __init__(self):
            self.host = 0
        def __call__(self, ctx=None):
            self.host += 1
            return "192.168.1.%d" % self.host
    ipfactory = IPFactory()
    
    class Infra20(InfraModel):
        slaves = MultiResource(StaticServer("slave", ipfactory))
    infra = Infra20("i20")
        
    class Namespace20(NamespaceModel):
        with_variables(Var("EXPR", host_list(ctxt.model.q.s)))
        s = MultiRole(Role("dude", host_ref=Infra20.slaves[ctxt.name]))
    ns = Namespace20()
    for i in range(5):
        ns.s[i].fix_arguments()
    
    v, o = ns.s[0].find_variable("EXPR")
    assert len(v.get_value(ns.s[0]).split(" ")) == 5
    

def do_all():
    setup()
    test19()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()
    
