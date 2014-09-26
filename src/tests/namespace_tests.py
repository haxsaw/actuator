'''
Created on 7 Jun 2014

@author: tom
'''
from actuator import (Var, NamespaceSpec, with_variables, NamespaceException,
                          Component, with_components)
from actuator.infra import (InfraSpec, MultiComponent, MultiComponentGroup)
from actuator.provisioners.example_components import Server


MyNS = None

def setup():
    global MyNS
    
    class FakeLogicalRef(object):
        def __init__(self, v=None):
            self.v = v
            
        def value(self):
            return self.v
        
    class FakeInfra(object):
        def get_inst_ref(self, fakeref):
            return fakeref
    
    class MyNamespaceLocal(NamespaceSpec):
        with_variables(Var("HOST", "wibble"),
                       Var("PORT", "1234"),
                       Var("REGION", "NY"),
                       Var("SIMPLE", "!REGION!"),
                       Var("HOST-REGION", "!REGION!-!HOST!"),
                       Var("ONE", "!TWO!"),
                       Var("TWO", "!THREE!"),
                       Var("THREE", "!ONE!"),
                       Var("EMBEDDED", "some text with !REGION! in it"),
                       Var("REPEATED", "!HOST! is !HOST!"),
                       Var("INCOMPLETE", "this won't expand; !SORRY!"),
                       Var("NONE", None),
                       Var("REF_TEST_NONE", FakeLogicalRef()),
                       Var("REF_TEST_VALUE", FakeLogicalRef("gabagabahey")))
        
        def __init__(self):
            super(MyNamespaceLocal, self).__init__()
            self.infra_instance = FakeInfra()
    MyNS = MyNamespaceLocal
    

def test001():
    inst = MyNS()
    v, p = inst.find_variable("HOST")
    assert v and p == inst, "failed to find the global HOST variable"
    
def test002():
    inst = MyNS()
    v, p = inst.find_variable("SIMPLE")
    assert v.get_value(p) == "NY", "variable replacement failed"
    
def test003():
    inst = MyNS()
    v, p = inst.find_variable("HOST-REGION")
    assert v.get_value(p) == "NY-wibble", "multiple variable replacement failed"
    
def test004():
    inst = MyNS()
    v, p = inst.find_variable("ONE")
    try:
        _ = v.get_value(p)
        assert False, "Replacement cycle was not detected"
    except NamespaceException, _:
        pass
    
def test005():
    inst = MyNS()
    v, p = inst.find_variable("EMBEDDED")
    assert v.get_value(p) == "some text with NY in it", "replacement didn't preserve text"
    
def test006():
    inst = MyNS()
    v, p = inst.find_variable("REPEATED")
    try:
        assert v.get_value(p) == "wibble is wibble"
    except NamespaceException, _:
        assert False, "This doesn't contain a cycle, just a repeated variable"
        
def test007():
    inst = MyNS()
    v, p = inst.find_variable("INCOMPLETE")
    assert v.get_value(p) is None, "an incomplete expansion returned a value when it shouldn't"

def test008():
    inst = MyNS()
    v, p = inst.find_variable("INCOMPLETE")
    assert v.get_value(p, allow_unexpanded=True) == "this won't expand; !SORRY!", \
        "allowing unexpanded returns didn't yield the expected value"
        
def test009():
    inst = MyNS()
    try:
        inst.add_variable(("YEP", "NOPE"))
        assert False, "Was allowed to add something that isn't a Var"
    except NamespaceException, _:
        pass
    
def test010():
    try:
        class MyNamespaceLocal(NamespaceSpec):
            with_variables(("YEP", "NOPE"))
        _ = MyNamespaceLocal()
        assert False, "Was allowed to use with_variables with something not a Var"
    except NamespaceException, _:
        pass
    
def test011():
    inst = MyNS()
    inst.add_override(Var("THREE", "BROKENLOOP"))
    try:
        v, p = inst.find_variable("ONE")
        _ = v.get_value(p)
    except NamespaceException, _:
        assert False, "Override should have broken the cycle"
        
def test012():
    inst = MyNS()
    inst.add_variable(Var("TWO", "and a half"))
    try:
        v, p = inst.find_variable("ONE")
        _ = v.get_value(p)
    except NamespaceException, _:
        assert False, "New Var should have replaced the old one"
        
def test013():
    inst = MyNS()
    v, p = inst.find_variable("NONE")
    assert v.get_value(p) is None, "Did not return None for an unset variable"
    
def test014():
    inst = MyNS()
    v, _ = inst.find_variable("NONE")
    assert not v.value_is_external(), "None value is being identified as external"
    
def test015():
    inst = MyNS()
    v, p = inst.find_variable("REF_TEST_NONE")
    assert v.get_value(p) is None
    
def test016():
    inst = MyNS()
    v, _ = inst.find_variable("REF_TEST_NONE")
    assert v.value_is_external()
    
def test017():
    inst = MyNS()
    v, p = inst.find_variable("REF_TEST_VALUE")
    assert v.get_value(p) is "gabagabahey"
    
def test018():
    inst = MyNS()
    v, _ = inst.find_variable("REF_TEST_VALUE")
    assert v.value_is_external()
    
def test019():
    class NS19(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Component("app_server")
    
    inst = NS19()
    assert inst.components["app_server"] == inst.app_server
    
def test020():
    class NS20(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Component("app_server")
    
    inst = NS20()
    assert inst.app_server is not NS20.app_server

def test021():
    class NS21(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Component("query_%d" % i)
        with_components(**queries)
        del queries
        
    assert NS21.query_1
    
def test022():
    class NS22(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        with_variables(Var("THIS", "TOO"))
    inst = NS22()
    v1, p1 = inst.find_variable("QUERY_PORT")
    v2, p2 = inst.find_variable("THIS")
    assert v1.get_value(p1) and v2.get_value(p2)

def test023():
    class Infra23(InfraSpec):
        app = Server("app")
        query = MultiComponent(Server("query", mem="8GB"))
        grid = MultiComponentGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))
    class NS23(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Component("app_server", host_ref=Infra23.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Component("query_%d" % i, host_ref=Infra23.query[i])
        with_components(**queries)
        del i, queries
        
    assert NS23.query_0
    
def test24():
    class Infra24(InfraSpec):
        app = Server("app")
        query = MultiComponent(Server("query", mem="8GB"))
        grid = MultiComponentGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))

    class NS24(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Component("app_server", host_ref=Infra24.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Component("query_%d" % i, host_ref=Infra24.query[i])
        with_components(**queries)
        del i, queries

    infra = Infra24("infra24")
    env = NS24()
#     import pdb
#     pdb.set_trace()
    env.compute_provisioning_for_environ(infra)
    assert len(infra.provisionables()) == 6

def test25():
    class Infra25(InfraSpec):
        app = Server("app")
        query = MultiComponent(Server("query", mem="8GB"))
        grid = MultiComponentGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))

    class NS25(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra25.query[10].provisionedName))
        app_server = Component("app_server", host_ref=Infra25.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Component("query_%d" % i, host_ref=Infra25.query[i])
        with_components(**queries)
        del i, queries

    infra = Infra25("infra25")
    env = NS25()
    env.compute_provisioning_for_environ(infra)
    assert len(infra.provisionables()) == 7

def test26():
    class Infra26(InfraSpec):
        app = Server("app")
        query = MultiComponent(Server("query", mem="8GB"))
        grid = MultiComponentGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))

    class NS26(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra26.app.provisionedName),
                       Var("QUERY_HOST", Infra26.query[0]))
        app_server = Component("app_server", host_ref=Infra26.app)

    infra = Infra26("infra26")
    env = NS26()
    env.add_override(Var("QUERY_HOST", "staticHostName"))
    env.compute_provisioning_for_environ(infra)
    assert len(infra.provisionables()) == 1, "override didn't wipe out ref to a new query server"

def test27():
    class Infra27(InfraSpec):
        app = Server("app")
        query = MultiComponent(Server("query", mem="8GB"))
        grid = MultiComponentGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))
    
    class NS27(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra27.app.provisionedName),
                       Var("QUERY_HOST", Infra27.query[0]))
        app_server = Component("app_server", host_ref=Infra27.app)
    
    infra = Infra27("infra26")
    env = NS27()
    env.add_override(Var("QUERY_HOST", "staticHostName"))
    provs = env.compute_provisioning_for_environ(infra, exclude_refs=[Infra27.query[0], Infra27.app])
    assert len(provs) == 0, "exclusions didn't wipe out the provisioning"

def test28():
    class Infra28(InfraSpec):
        regional_server = MultiComponent(Server("regional_server", mem="16GB"))
    
    nf = lambda x: "reg_srvr_%d" % x
    class NS28(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("SERVER_ID", "server_!ID!")
                       )
        
        servers = {nf(i):Component(nf(i),
                                   host_ref=Infra28.regional_server[nf(i)])
                         .add_variable(Var("ID", str(i)))
                   for i in range(5)}
        with_components(**servers)
        del servers
        
    ns = NS28()
    assert ns.reg_srvr_0 is not None

def test29():
    class Infra29(InfraSpec):
        regional_server = MultiComponent(Server("regional_server", mem="16GB"))
    
    nf = lambda x: "reg_srvr_%d" % x
    class NS29(NamespaceSpec):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("SERVER_ID", "server_!ID!")
                       )
        
        servers = {nf(i):Component(nf(i),
                                   host_ref=Infra29.regional_server[nf(i)])
                         .add_variable(Var("ID", str(i)))
                   for i in range(5)}
        with_components(**servers)
        del servers
        
    ns = NS29()
    assert ns.reg_srvr_0.get_var_future("SERVER_ID").value() == "server_0"

def test30():
    class Infra30(InfraSpec):
        regional_server = Server("regional_server", mem="16GB")
    
    nf = lambda x: "reg_srvr_%d" % x
    class NS30(NamespaceSpec):
        with_variables(Var("TRICKY", "!NAME! with id !SERVER_ID!"),
                       Var("SERVER_ID", "server_!ID!")
                       )
        server1 = (Component(nf(1), host_ref=Infra30.regional_server)
                   .add_variable(Var("ID", str(1)), Var("NAME", nf(1))))

        server2 = (Component(nf(2), host_ref=Infra30.regional_server)
                   .add_variable(Var("ID", str(2)), Var("NAME", nf(2))))

        
    ns = NS30()
    assert ns.server2.get_var_future("TRICKY").value() == "reg_srvr_2 with id server_2"

def test31():
    nf = lambda x: "reg_srvr_%d" % x
    class NS31(NamespaceSpec):
        with_variables(Var("TRICKY", "!NAME! with id !SERVER_ID!"),
                       Var("SERVER_ID", "server_!ID!"),
                       Var("NAME", "--WRONG!!")
                       )
        server1 = (Component(nf(1))
                   .add_variable(Var("ID", str(1)),
                                 Var("NAME", nf(1))))

        server2 = (Component(nf(2))
                   .add_variable(Var("ID", str(2)),
                                 Var("NAME", nf(2))))

        
    ns = NS31()
    expected = set([("NAME", "reg_srvr_2"),
                    ("ID", "2"),
                    ("TRICKY", "reg_srvr_2 with id server_2"),
                    ("SERVER_ID", "server_2")])
    results = set([(k, v.get_value(ns.server2))
                   for k, v in ns.server2.get_visible_vars().items()])
    assert expected == results

def test32():
    class Infra32(InfraSpec):
        regional_server = Server("regional_server", mem="16GB")
    
    nf = lambda x: "reg_srvr_%d" % x
    class NS32(NamespaceSpec):
        with_variables(Var("TRICKY", "!NAME! with id !SERVER_ID!"),
                       Var("SERVER_ID", "server_!ID!")
                       )
        server1 = (Component(nf(1), host_ref=Infra32.regional_server)
                   .add_variable(Var("ID", str(1)), Var("NAME", nf(1))))
        
    ns = NS32()
    infra = Infra32("32")
    ns.compute_provisioning_for_environ(infra)
    assert ns.find_infra() is infra and ns.server1.find_infra() is infra
    
def test33():
    class NS33(NamespaceSpec):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS33()
    ns.add_components(server1=Component("server1").add_variable(Var("TEST", "YEP")))
    assert ns.server1.get_var_future("TEST").value() == "YEP"

def test34():
    class NS34(NamespaceSpec):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS34()
    server1 = Component("server1").add_variable(Var("TEST", "YEP"))
    ns.add_components(server1=server1)
    server1.add_variable(Var("TEST", "--REALLY NOPE--"))
    assert ns.server1.get_var_future("TEST").value() == "YEP"

def test35():
    class NS35(NamespaceSpec):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS35()
    server1 = Component("server1").add_variable(Var("TEST", "YEP"))
    ns.add_components(server1=server1)
    ns.server1.add_variable(Var("TEST", "YEP YEP"))
    assert ns.server1.get_var_future("TEST").value() == "YEP YEP"

def test36():
    class NS36(NamespaceSpec):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS36()
    server1 = Component("server1").add_variable(Var("TEST", "YEP"))
    ns.add_components(server1=server1, server2=Component("server2"))
    ns.server1.add_override(Var("TEST", "YEP YEP YEP"))
    assert ns.server1.get_var_future("TEST").value() == "YEP YEP YEP"
    
def test37():
    class NS37(NamespaceSpec):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Component("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Component("kid", parent=daddy)
    ns = NS37()
    assert ns.kid.get_var_future("MYSTERY").value() == "RIGHT!"

        
def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()
    