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

"""
Created on 7 Jun 2014
"""

from errator import reset_all_narrations, set_default_options

from actuator import (Var, NamespaceModel, with_variables, NamespaceException,
                          Role, with_roles, MultiResource, 
                          MultiResourceGroup, ctxt, ActuatorException,
                          StaticServer)
from actuator.namespace import RoleGroup, MultiRole, MultiRoleGroup
from actuator.infra import InfraModel
from actuator.modeling import AbstractModelReference
from actuator.provisioners.example_resources import Server


MyNS = None


def setup_module():
    global MyNS
    
    class FakeLogicalRef(AbstractModelReference):
        def __init__(self, v=None):
            self.v = v
            self._name = "v"
            self._obj = self
            
        def value(self):
            return object.__getattribute__(self, "v")
        
    class FakeInfra(object):
        def get_inst_ref(self, fakeref):
            return fakeref
    
    class MyNamespaceLocal(NamespaceModel):
        with_variables(Var("HOST", "wibble"),
                       Var("PORT", "1234"),
                       Var("REGION", "NY"),
                       Var("SIMPLE", "!{REGION}"),
                       Var("HOST-REGION", "!{REGION}-!{HOST}"),
                       Var("ONE", "!{TWO}"),
                       Var("TWO", "!{THREE}"),
                       Var("THREE", "!{ONE}"),
                       Var("EMBEDDED", "some text with !{REGION} in it"),
                       Var("REPEATED", "!{HOST} is !{HOST}"),
                       Var("INCOMPLETE", "this won't expand; !{SORRY}"),
                       Var("NONE", None),
                       Var("REF_TEST_NONE", FakeLogicalRef(None)),
                       Var("REF_TEST_VALUE", FakeLogicalRef("gabagabahey")))
        
        def __init__(self, name):
            super(MyNamespaceLocal, self).__init__(name)
            self.infra = FakeInfra()
    MyNS = MyNamespaceLocal

    reset_all_narrations()
    set_default_options(check=True)
    

def test001():
    inst = MyNS("ns1")
    v, p = inst.find_variable("HOST")
    assert v and p == inst, "failed to find the global HOST variable"


def test002():
    inst = MyNS("ns2")
    v, p = inst.find_variable("SIMPLE")
    assert v.get_value(p) == "NY", "variable replacement failed"


def test003():
    inst = MyNS("ns3")
    v, p = inst.find_variable("HOST-REGION")
    assert v.get_value(p) == "NY-wibble", "multiple variable replacement failed"


def test004():
    inst = MyNS("ns4")
    v, p = inst.find_variable("ONE")
    try:
        _ = v.get_value(p)
        assert False, "Replacement cycle was not detected"
    except NamespaceException, _:
        pass


def test005():
    inst = MyNS("ns5")
    v, p = inst.find_variable("EMBEDDED")
    assert v.get_value(p) == "some text with NY in it", "replacement didn't preserve text"


def test006():
    inst = MyNS("test")
    v, p = inst.find_variable("REPEATED")
    try:
        assert v.get_value(p) == "wibble is wibble"
    except NamespaceException, _:
        assert False, "This doesn't contain a cycle, just a repeated variable"
        
def test007():
    inst = MyNS("test")
    v, p = inst.find_variable("INCOMPLETE")
    assert v.get_value(p) is None, "an incomplete expansion returned a value when it shouldn't"


def test008():
    inst = MyNS("test")
    v, p = inst.find_variable("INCOMPLETE")
    assert v.get_value(p, allow_unexpanded=True) == "this won't expand; !{SORRY}", \
        "allowing unexpanded returns didn't yield the expected value"


def test009():
    inst = MyNS("test")
    try:
        inst.add_variable(("YEP", "NOPE"))
        assert False, "Was allowed to add something that isn't a Var"
    except NamespaceException, _:
        pass


def test010():
    try:
        class MyNamespaceLocal(NamespaceModel):
            with_variables(("YEP", "NOPE"))
        _ = MyNamespaceLocal("nslocal")
        assert False, "Was allowed to use with_variables with something not a Var"
    except NamespaceException, _:
        pass


def test011():
    inst = MyNS("test")
    inst.add_override(Var("THREE", "BROKENLOOP"))
    try:
        v, p = inst.find_variable("ONE")
        _ = v.get_value(p)
    except NamespaceException, _:
        assert False, "Override should have broken the cycle"


def test012():
    inst = MyNS("test")
    inst.add_variable(Var("TWO", "and a half"))
    try:
        v, p = inst.find_variable("ONE")
        _ = v.get_value(p)
    except NamespaceException, _:
        assert False, "New Var should have replaced the old one"


def test013():
    inst = MyNS("test")
    v, p = inst.find_variable("NONE")
    assert v.get_value(p) is None, "Did not return None for an unset variable"


def test014():
    inst = MyNS("test")
    v, _ = inst.find_variable("NONE")
    assert not v.value_is_external(), "None value is being identified as external"


def test015():
    inst = MyNS("test")
    v, p = inst.find_variable("REF_TEST_NONE")
    assert v.get_value(p) is None


def test016():
    inst = MyNS("test")
    v, _ = inst.find_variable("REF_TEST_NONE")
    assert v.value_is_external()


def test017():
    inst = MyNS("test")
    v, p = inst.find_variable("REF_TEST_VALUE")
    assert v.get_value(p) is "gabagabahey"


def test018():
    inst = MyNS("test")
    v, _ = inst.find_variable("REF_TEST_VALUE")
    assert v.value_is_external()


def test019():
    class NS19(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Role("app_server")
    
    inst = NS19("ns19")
    assert inst._roles["app_server"] == inst.app_server.value()


def test020():
    class NS20(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Role("app_server")
    
    inst = NS20("ns20")
    assert inst.app_server is not NS20.app_server


def test021():
    class NS21(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Role("query_%d" % i)
        with_roles(**queries)
        del queries
        
    assert NS21.query_1


def test022():
    class NS22(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        with_variables(Var("THIS", "TOO"))
    inst = NS22("ns22")
    v1, p1 = inst.find_variable("QUERY_PORT")
    v2, p2 = inst.find_variable("THIS")
    assert v1.get_value(p1) and v2.get_value(p2)


def test023():
    class Infra23(InfraModel):
        app = Server("app")
        query = MultiResource(Server("query", mem="8GB"))
        grid = MultiResourceGroup("grid",
                                  handler=Server("handler", mem="8GB"),
                                  compute=Server("compute", mem="16GB"))

    class NS23(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Role("app_server", host_ref=Infra23.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Role("query_%d" % i, host_ref=Infra23.query[i])
        with_roles(**queries)
        del i, queries
        
    assert NS23.query_0


def test024():
    class Infra24(InfraModel):
        app = Server("app")
        query = MultiResource(Server("query", mem="8GB"))
        grid = MultiResourceGroup("grid",
                                   handler=Server("handler", mem="8GB"),
                                   compute=Server("compute", mem="16GB"))

    class NS24(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"))
        app_server = Role("app_server", host_ref=Infra24.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Role("query_%d" % i, host_ref=Infra24.query[i])
        with_roles(**queries)
        del i, queries

    infra = Infra24("infra24")
    env = NS24("ns24")
    env.compute_provisioning_for_environ(infra)
    assert len(infra.components()) == 6


def test025():
    class Infra25(InfraModel):
        app = Server("app")
        query = MultiResource(Server("query", mem="8GB"))
        grid = MultiResourceGroup("grid",
                                  handler=Server("handler", mem="8GB"),
                                  compute=Server("compute", mem="16GB"))

    class NS25(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra25.query[10].provisionedName))
        app_server = Role("app_server", host_ref=Infra25.app)
        queries = {}
        for i in range(5):
            queries["query_%d" % i] = Role("query_%d" % i, host_ref=Infra25.query[i])
        with_roles(**queries)
        del i, queries

    infra = Infra25("infra25")
    env = NS25("ns25")
    env.compute_provisioning_for_environ(infra)
    assert len(infra.components()) == 7


def test026():
    class Infra26(InfraModel):
        app = Server("app")
        query = MultiResource(Server("query", mem="8GB"))
        grid = MultiResourceGroup("grid",
                                  handler=Server("handler", mem="8GB"),
                                  compute=Server("compute", mem="16GB"))

    class NS26(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra26.app.provisionedName),
                       Var("QUERY_HOST", Infra26.query[0]))
        app_server = Role("app_server", host_ref=Infra26.app)

    infra = Infra26("infra26")
    env = NS26("ns26")
    env.add_override(Var("QUERY_HOST", "staticHostName"))
    env.compute_provisioning_for_environ(infra)
    assert len(infra.components()) == 1, "override didn't wipe out ref to a new query server"


def test027():
    class Infra27(InfraModel):
        app = Server("app")
        query = MultiResource(Server("query", mem="8GB"))
        grid = MultiResourceGroup("grid",
                                  handler=Server("handler", mem="8GB"),
                                  compute=Server("compute", mem="16GB"))
    
    class NS27(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("APP_HOST", Infra27.app.provisionedName),
                       Var("QUERY_HOST", Infra27.query[0]))
        app_server = Role("app_server", host_ref=Infra27.app)
    
    infra = Infra27("infra26")
    env = NS27("ns27")
    env.add_override(Var("QUERY_HOST", "staticHostName"))
    provs = env.compute_provisioning_for_environ(infra, exclude_refs=[Infra27.query[0], Infra27.app])
    assert len(provs) == 0, "exclusions didn't wipe out the provisioning"


def test028():
    class Infra28(InfraModel):
        regional_server = MultiResource(Server("regional_server", mem="16GB"))
    
    nf = lambda x: "reg_srvr_%d" % x

    class NS28(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("SERVER_ID", "server_!{ID}")
                       )

        servers = {nf(i): Role(nf(i),
                               host_ref=Infra28.regional_server[nf(i)])
                   .add_variable(Var("ID", str(i)))
                   for i in range(5)}
        with_roles(**servers)
        del servers
        
    ns = NS28("ns28")
    assert ns.reg_srvr_0 is not None


def test029():
    class Infra29(InfraModel):
        regional_server = MultiResource(Server("regional_server", mem="16GB"))
    
    nf = lambda x: "reg_srvr_%d" % x

    class NS29(NamespaceModel):
        with_variables(Var("APP_PORT", "8080"),
                       Var("QUERY_PORT", "8081"),
                       Var("GRID_PORT", "8082"),
                       Var("SERVER_ID", "server_!{ID}")
                       )
        
        servers = {nf(i): Role(nf(i),
                               host_ref=Infra29.regional_server[nf(i)])
                   .add_variable(Var("ID", str(i)))
                   for i in range(5)}
        with_roles(**servers)
        del servers
        
    ns = NS29("ns29")
    assert ns.reg_srvr_0.future("SERVER_ID").value() == "server_0"


def test030():
    class Infra30(InfraModel):
        regional_server = Server("regional_server", mem="16GB")
    
    nf = lambda x: "reg_srvr_%d" % x

    class NS30(NamespaceModel):
        with_variables(Var("TRICKY", "!{NAME} with id !{SERVER_ID}"),
                       Var("SERVER_ID", "server_!{ID}")
                       )
        server1 = (Role(nf(1), host_ref=Infra30.regional_server)
                   .add_variable(Var("ID", str(1)), Var("NAME", nf(1))))

        server2 = (Role(nf(2), host_ref=Infra30.regional_server)
                   .add_variable(Var("ID", str(2)), Var("NAME", nf(2))))

    ns = NS30("ns30")
    assert ns.server2.future("TRICKY").value() == "reg_srvr_2 with id server_2"


def test031():
    nf = lambda x: "reg_srvr_%d" % x

    class NS31(NamespaceModel):
        with_variables(Var("TRICKY", "!{NAME} with id !{SERVER_ID}"),
                       Var("SERVER_ID", "server_!{ID}"),
                       Var("NAME", "--WRONG!!")
                       )
        server1 = (Role(nf(1))
                   .add_variable(Var("ID", str(1)),
                                 Var("NAME", nf(1))))

        server2 = (Role(nf(2))
                   .add_variable(Var("ID", str(2)),
                                 Var("NAME", nf(2))))

    ns = NS31("ns31")
    expected = {("NAME", "reg_srvr_2"),
                ("ID", "2"),
                ("TRICKY", "reg_srvr_2 with id server_2"),
                ("SERVER_ID", "server_2")}
    results = set([(k, v.get_value(ns.server2))
                   for k, v in ns.server2.get_visible_vars().items()])
    assert expected == results


def test032():
    class Infra32(InfraModel):
        regional_server = Server("regional_server", mem="16GB")
    
    nf = lambda x: "reg_srvr_%d" % x

    class NS32(NamespaceModel):
        with_variables(Var("TRICKY", "!{NAME} with id !{SERVER_ID}"),
                       Var("SERVER_ID", "server_!{ID}")
                       )
        server1 = (Role(nf(1), host_ref=Infra32.regional_server)
                   .add_variable(Var("ID", str(1)), Var("NAME", nf(1))))
        
    ns = NS32("ns32")
    infra = Infra32("32")
    ns.compute_provisioning_for_environ(infra)
    assert ns.find_infra_model() is infra and ns.server1.find_infra_model() is infra


def test033():
    class NS33(NamespaceModel):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS33("ns33")
    ns.add_roles(server1=Role("server1").add_variable(Var("TEST", "YEP")))
    assert ns.server1.future("TEST").value() == "YEP"


def test034():
    class NS34(NamespaceModel):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS34("ns34")
    server1 = Role("server1").add_variable(Var("TEST", "YEP"))
    ns.add_roles(server1=server1)
    server1.add_variable(Var("TEST", "--REALLY NOPE--"))
    assert ns.server1.future("TEST").value() == "YEP"


def test035():
    class NS35(NamespaceModel):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS35("ns35")
    server1 = Role("server1").add_variable(Var("TEST", "YEP"))
    ns.add_roles(server1=server1)
    ns.server1.add_variable(Var("TEST", "YEP YEP"))
    assert ns.server1.future("TEST").value() == "YEP YEP"


def test036():
    class NS36(NamespaceModel):
        with_variables(Var("TEST", "NOPE"))
        
    ns = NS36("ns36")
    server1 = Role("server1").add_variable(Var("TEST", "YEP"))
    ns.add_roles(server1=server1, server2=Role("server2"))
    ns.server1.add_override(Var("TEST", "YEP YEP YEP"))
    assert ns.server1.future("TEST").value() == "YEP YEP YEP"


def test037():
    class NS37(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    ns = NS37("ns37")
    assert ns.daddy.future("MYSTERY").value() == "RIGHT!"


def test038():
    class NS38(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    assert not isinstance(NS38.daddy, Role)


def test039():
    class NS39(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    ns = NS39("ns39")
    assert NS39.daddy is not ns.daddy


def test040():
    class NS40(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    ns = NS40("ns40")
    assert ns.daddy is ns.get_inst_ref(NS40.daddy)


def test041():
    class NS41(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    ns = NS41("ns41")
    assert not isinstance(ns.daddy.name, basestring)


def test042():
    class NS42(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        daddy = Role("daddy").add_variable(Var("MYSTERY", "RIGHT!"))
        kid = Role("kid")
    ns = NS42("ns42")
    assert ns.daddy.name.value() == "daddy"
 
def test043():
    class NS43(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        family = RoleGroup("family", daddy=Role("daddy").add_variable(Var("MYSTERY", "RIGHT!")),
                                kid=Role("kid"))
    ns = NS43("ns43")
    assert ns.family.daddy.name.value() == "daddy"


def test044():
    class NS44(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        family = RoleGroup("family",
                                  daddy=Role("daddy"),
                                  kid=Role("kid")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS44("ns44")
    var, _ = ns.family.kid.find_variable("MYSTERY")
    assert var.get_value(ns.family.kid.value()) == "RIGHT!"


def test045():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        kids = MultiRole(Role("kid")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS("ns45")
    var, _ = ns.kids.find_variable("MYSTERY")
    assert var.get_value(ns.kids.value()) == "RIGHT!"


def test046():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        kids = MultiRole(Role("kid")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS("ns46")
    var, _ = ns.kids[0].find_variable("MYSTERY")
    assert var.get_value(ns.kids[0].value()) == "RIGHT!"


def test047():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        kids = MultiRole(Role("kid")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS("ns47")
    assert ns.kids[0] is ns.kids[0]


def test048():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        kids = MultiRole(Role("kid")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns1 = NS("ns48a")
    ns2 = NS("ns48b")
    assert ns1.kids[0] is not ns2.kids[0]


def test049():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        kids = MultiRole(Role("kid").add_variable(Var("MYSTERY", "maybe..."))).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS("ns49")
    var, _ = ns.kids[0].find_variable("MYSTERY")
    assert var.get_value(ns.kids[0].value()) == "maybe..." 


def test052():
    class Infra1(InfraModel):
        controller = Server("controller", mem="16GB")
        grid = MultiResourceGroup("pod", foreman=Server("foreman", mem="8GB"),
                                   worker=Server("grid-node", mem="8GB"))
          
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        grid = MultiRoleGroup("pod", foreman=Role("foreman",
                                                  host_ref=ctxt.nexus.inf.grid[ctxt.comp.container._name].foreman),
                                     worker=Role("grid-node",
                                                 host_ref=ctxt.nexus.inf.grid[ctxt.comp.container._name].worker)).add_variable(Var("MYSTERY", "RIGHT!"))
    infra = Infra1("mcg")
    ns = NS("ns52")
    for i in range(5):
        _ = ns.grid[i]
    ns.compute_provisioning_for_environ(infra)
    assert len(infra.grid) == 5 and len(infra.components()) == 11


def test053():
    class Infra1(InfraModel):
        grid = MultiResourceGroup("grid",
                                   foreman=Server("foreman", mem="8GB"),
                                   workers=MultiResource(Server("grid-node", mem="8GB")))
          
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        grid = MultiRoleGroup("pod",
                              foreman=Role("foreman",
                                           host_ref=ctxt.nexus.inf.grid[ctxt.comp.container._name].foreman),
                              workers=MultiRole(Role("grid-node",
                                                     host_ref=ctxt.nexus.inf.grid[ctxt.comp.container.container._name].workers[ctxt.name]))).add_variable(Var("MYSTERY", "RIGHT!"))
    infra = Infra1("mcg")
    ns = NS("ns53")
    for i in [2,4]:
        grid = ns.grid[i]
        for j in range(i):
            _ = grid.workers[j]
    ns.compute_provisioning_for_environ(infra)
    assert len(infra.grid) == 2 and len(infra.grid[2].workers) == 2 and len(infra.grid[4].workers) == 4 and len(infra.components()) == 8


def test054():
    class Infra1(InfraModel):
        grid = MultiResource(Server("foreman", mem="8GB"))
          
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        grid = MultiRole(Role("foreman",
                              host_ref=ctxt.nexus.inf.grid[0])).add_variable(Var("MYSTERY", "RIGHT!"))
    infra = Infra1("mcg")
    ns = NS("ns54")
    for i in [2,4]:
        _ = ns.grid[i]
    ns.compute_provisioning_for_environ(infra)
    assert len(infra.grid) == 1 and len(infra.components()) == 1


def test056():
    class Infra1(InfraModel):
        grid = MultiResource(Server("node", mem="8GB"))
        
    def bad_comp(ctxt):
        # generate an attribute error
        [].wibble
        
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        grid = MultiRole(Role("foreman", host_ref=bad_comp)).add_variable(Var("MYSTERY", "RIGHT!"))

    infra = Infra1("mcg")
    ns = NS("ns56")
    for i in [2,4]:
        _ = ns.grid[i]
    try:
        ns.compute_provisioning_for_environ(infra)
        assert False, "Should have complained about the back host_ref callable"
    except ActuatorException, e:
        assert "Callable arg failed" in e.message


def test057():
    from actuator.namespace import _ComputableValue
    try:
        _ = _ComputableValue(object())
        assert False, "_ComputableValue should have complained about the value supplied"
    except NamespaceException, e:
        assert "unrecognized" in e.message.lower()


def test058():
    from actuator.namespace import VariableContainer
    vc = VariableContainer(variables=[Var("ONE", "1"), Var("TWO", "2")])
    assert set(vc.variables.keys()) == set(["ONE", "TWO"])


def test059():
    from actuator.namespace import VariableContainer
    vc = VariableContainer(overrides=[Var("ONE", "1"), Var("TWO", "2")])
    assert set(vc.overrides.keys()) == set(["ONE", "TWO"])


def test060():
    from actuator.namespace import VariableContainer
    try:
        _ = VariableContainer(overrides=[{"ONE":"1"}])
        assert False, "Should have got an exception on a bad Var"
    except TypeError, e:
        assert "is not a var" in e.message.lower()


def test063():
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"))
        grid = MultiRole(Role("foreman")).add_variable(Var("MYSTERY", "RIGHT!"))
    ns = NS("ns63")
    for i in range(5):
        _ = ns.grid[i]
    clone = ns.grid.clone()
    assert len(clone) == 5


def test064():
    class NS(NamespaceModel):
        with_variables(Var("NODE_NAME", "!{BASE_NAME}-!{NODE_ID}"))
        grid = (MultiRole(Role("worker",
                               variables=[Var("NODE_ID", ctxt.name)]))
                .add_variable(Var("BASE_NAME", "Grid")))
    ns = NS("ns64")
    value = ns.grid[5].var_value("NODE_NAME")
    assert value and value == "Grid-5"


def test065():
    # why does this work just like test64()? Because of where we ask for the
    # var_value(); even though NODE_ID is defined on the model class itself,
    # it gets evaluated in the context of ns.grid[5]. Since the value is
    # a context expression, it gets evaluated relative to the context that
    # needs its value, and the name in this context is '5'
    class NS(NamespaceModel):
        with_variables(Var("NODE_NAME", "!{BASE_NAME}-!{NODE_ID}"),
                       Var("NODE_ID", ctxt.name))
        grid = (MultiRole(Role("worker"))
                .add_variable(Var("BASE_NAME", "Grid")))
    ns = NS("ns65")
    value = ns.grid[5].var_value("NODE_NAME")
    assert value and value == "Grid-5"


def test066():
    class Infra1(InfraModel):
        grid_i = MultiResource(StaticServer("node", "127.0.0.1"))
        
    class NS(NamespaceModel):
        with_variables(Var("NODE_NAME", "!{BASE_NAME}-!{NODE_ID}"))
        grid = (MultiRole(Role("worker",
                               variables=[Var("NODE_ID", ctxt.name)]))
                .add_variable(Var("BASE_NAME", "Grid")))
    infra = Infra1("66")
    ns = NS("ns66")
    ns.compute_provisioning_for_environ(infra)
    _ = infra.refs_for_components()
    value = ns.grid[5].var_value("NODE_NAME")
    assert value and value == "Grid-5"


def test067():
    """
    test67: check basic Var access
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "1"),
                       Var("TWO", "2"))
    ns = NS("ns67")
    assert ns.v.ONE() == "1"


def test068():
    """
    test68: check proper value access with Role overriding a Var
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "1"))
        r = Role("r", variables=(Var("ONE", "uno"),))
    ns = NS("ns68")
    assert ns.v.ONE() == "1" and ns.r.v.ONE() == "uno"


def test069():
    """
    test69: check that Namespace Var can be access via the nexus
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "1"))
    ns = NS("ns69")
    assert ns.nexus.ns.v.ONE() == "1"


def test070():
    """
    test70: check proper operation using value() instead of a call
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "1"))
        r = Role("r", variables=[Var("ONE", "uno")])
    ns = NS("ns70")
    assert ns.v.ONE.value() == "1" and ns.r.v.ONE.value() == "uno"


def test071():
    """
    test71: check access of Vars via the context object
    """
    class NS(NamespaceModel):
        r1 = Role("r1", variables=[Var("ONE", "eins")])
        r2 = Role("r2", variables=[Var("ONE", ctxt.model.r1.v.ONE)])
    ns = NS("ns71")
    assert ns.r2.v.ONE() == "eins"


def test072():
    """
    test72: check that we can get a value for a NS Var via the nexus
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "1"))
        r1 = Role("r1", variables=[Var("GLOBAL", ctxt.nexus.ns.v.ONE)])
        r2 = Role("r2", variables=[Var("INDIRECT", ctxt.nexus.ns.r1.v.GLOBAL)])
    ns = NS("ns72")
    assert ns.r2.v.INDIRECT() == "1"


def test073():
    """
    test73: check that we can get a value in a config model from a namespace
    """
    class Inf(InfraModel):
        s = Server("me", mem="8GB", ip=ctxt.nexus.ns.srvr.v.IP)
    inf = Inf("inf")
    
    class NS(NamespaceModel):
        with_variables(Var("IP", "127.0.0.1"))
        srvr = Role("srvr", variables=[Var("IP", "192.168.6.1")])
    ns = NS("test")
    ns.set_infra_model(inf)
    inf.s.fix_arguments()
    assert inf.s.ip.value() == "192.168.6.1"


def test074():
    """
    test74: check for good behavior on bad Var ref
    """
    class NS(NamespaceModel):
        with_variables(Var("ONE", "uno"))
    ns = NS("test")
    try:
        _ = ns.v.TWO()
        assert False, "The previous line should have raised an exception"
    except Exception, _:
        assert ns.v.ONE() == "uno"


def test075():
    """
    test75: check using a Var context expr as an index into another ctxt expr
    """
    class Inf(InfraModel):
        grid = MultiResource(Server("gnode", mem="8GB"))
    inf = Inf("grid")
    
    class NS(NamespaceModel):
        with_variables(Var("KEY", "nope"))
        gnode = MultiRole(Role("grid_node",
                               host_ref=ctxt.nexus.inf.grid[ctxt.comp.v.KEY],
                               variables=[Var("KEY", ctxt.comp.name)]))
    ns = NS("test")
    ns.set_infra_model(inf)
    for i in range(5):
        _ = ns.gnode[i]
    
    assert ns.gnode[0].name != "nope"


def test076():
    """
    test076: define a Var on a namespace model and get the value with 'v'
    """
    class NS(NamespaceModel):
        with_variables(Var("avar", ctxt.model.v.anothervar),
                       Var("anothervar", "hiya"))
    ns = NS("test")
    assert ns.v.avar() == "hiya"


def test077():
    class Infra1(InfraModel):
        grid = MultiResourceGroup("grid",
                                   foreman=Server("foreman", mem="8GB"),
                                   workers=MultiResource(Server("grid-node", mem="8GB")))
          
    class NS(NamespaceModel):
        with_variables(Var("MYSTERY", "WRONG!"),
                       Var("FROM", "ABOVE"))
        grid = MultiRoleGroup("pod",
                              foreman=Role("foreman",
                                           host_ref=ctxt.nexus.inf.grid[ctxt.comp.container._name].foreman),
                              workers=MultiRole(Role("grid-node",
                                                     host_ref=ctxt.nexus.inf.grid[ctxt.comp.container.container._name].workers[ctxt.name],
                                                     variables=[Var("MYSTERY", "RIGHT!")])))
    infra = Infra1("mcg")
    ns = NS("test")
    for i in [2, 4]:
        grid = ns.grid[i]
        for j in range(i):
            _ = grid.workers[j]
    ns.compute_provisioning_for_environ(infra)
    assert (len(infra.grid) == 2 and
            len(infra.grid[2].workers) == 2 and
            len(infra.grid[4].workers) == 4 and
            len(infra.components()) == 8 and
            ns.grid[2].workers[0].var_value("FROM") == "ABOVE")


def test078():
    class Infra78(InfraModel):
        s = Server("s78", mem=ctxt.nexus.ns.v.MEMSIZE)
        
    class NS78(NamespaceModel):
        with_variables(Var("MEMSIZE", "8GB"))
        
    inf = Infra78("78")
    ns = NS78("ns78")
    ns.set_infra_model(inf)
    for c in inf.components():
        c.fix_arguments()
    assert inf.s.mem.value() == "8GB"


def test079():
    class Infra79(InfraModel):
        s = Server("s78", mem=ctxt.nexus.ns.r.v.MEMSIZE)
        
    class NS79(NamespaceModel):
        r = Role("r", variables=[Var("MEMSIZE", "16GB")])
        
    inf = Infra79("79")
    ns = NS79("ns79")
    ns.set_infra_model(inf)
    for c in inf.components():
        c.fix_arguments()
    assert inf.s.mem.value() == "16GB"
     

def do_all():
    setup_module()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()
    