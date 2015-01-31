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
Created on 4 Jun 2014
'''
from actuator import (InfraModel, MultiResourceGroup, ComponentGroup, ctxt)
from actuator.modeling import (ModelReference, ModelInstanceReference, AbstractModelReference,
                               AbstractModelingEntity, MultiComponent)
from actuator.infra import (with_resources, InfraException, ResourceGroup,
                            MultiResource, MultiResourceGroup)
from actuator.provisioners.example_resources import Server, Database

MyInfra = None

def setup():
    global MyInfra
    class MyInfraLocal(InfraModel):
        other = "some data"
        server = Server("wibble", mem="16GB")
        grid = MultiResource(Server("grid-comp", mem="8GB"))
        database = Database("db")
        workers = MultiResourceGroup("workers",
                                      handler=Server("handler", mem="4GB"),
                                      query=Server("query", mem="8GB"),
                                      ncube=Server("ncube", mem="16GB"))
        composite = MultiResourceGroup("grid",
                                        grid=MultiResource(Server("grid-comp", mem="8GB")),
                                        workers=MultiResourceGroup("inner_workers",
                                                                    handler=Server("handler", mem="4GB"),
                                                                    query=Server("query", mem="8GB"),
                                                                    ncube=Server("ncube", mem="16GB")))
    MyInfra = MyInfraLocal

def test01():
    assert type({}) == type(MyInfra.__components), "the __components attr is missing or the wrong type"
    
def test02():
    assert type(MyInfra.server) != Server, "the type of a resource attribute isn't a ref"
    
def test03():
    assert MyInfra.server is MyInfra.server, "references aren't being reused"

def test04():
    assert type(MyInfra.server.name) is ModelReference, \
            "data member on a resource isn't being wrapped with a reference"
    
def test05():
    assert MyInfra.other == "some data", "plain class attrs aren't being passed thru"
    
def test06():
    try:
        _ = MyInfra.server.wibble
        assert False, "failed to raise AttributeError when accessing a bad attr"
    except AttributeError, _:
        pass
    
def test07():
    assert MyInfra.server.name is MyInfra.server.name, \
            "reference reuse not occurring on resource attribute"
    
def test08():
    assert MyInfra.server.mem, "failed to create ref for kw-created attr"
    
def test09():
    assert type(MyInfra.server.provisionedName) == ModelReference, \
            "data member on a resource isn't being wrapped with a reference"

def test10():
    assert MyInfra.server.value().__class__ is Server, \
            "value underlying a resource ref is the wrong class"
    
def test11():
    assert MyInfra.server.provisionedName.value() is None, \
            "expected empty value for this attr"
    
def test12():
    try:
        _ = MyInfra.server['wow']
        assert False, "Should not have been allowed to perform keyed access on the server"
    except TypeError, _:
        pass
    
def test13():
    assert MyInfra.grid[1].__class__ == ModelReference, \
        "did not get a ref for a keyed MultiResource"
    
def test14():
    assert MyInfra.grid.__class__ == ModelReference, \
        "did not get a ref for a MultiResource"
    
def test15():
    assert MyInfra.grid[1] is MyInfra.grid[1], \
        "refs not being reused for keyed MultiCcmponent"
    
def test16():
    assert MyInfra.grid[2].name.__class__ == ModelReference
    
def test17():
    assert (MyInfra.grid[3].name is MyInfra.grid[3].name)
    
def test18():
    assert MyInfra.grid[4].name is not MyInfra.grid[5].name
    
def test19():
    assert MyInfra.grid[6].mem
    
def test20():
    assert MyInfra.server.get_path() == ["server"]
    
def test21():
    assert MyInfra.server.mem.get_path() == ["server", "mem"]
    
def test22():
    assert MyInfra.server.provisionedName.get_path() == ["server", "provisionedName"]
    
def test23():
    assert MyInfra.grid.get_path() == ["grid"]
    
def test24():
    assert MyInfra.grid[1].get_path() == ["grid", "1"]
    
def test25():
    assert MyInfra.grid[2].mem.value() == "8GB"
    
def test26():
    assert MyInfra.grid[22].mem.get_path() == ["grid", "22", "mem"]
    
def test27():
    assert MyInfra.grid[5].name.get_path() == ["grid", "5", "name"]
    
def test28():
    inst = MyInfra("test28")
    assert inst
    
def test29():
    inst = MyInfra("test29")
    assert inst.other == "some data"
    
def test30():
    inst = MyInfra("test30")
    assert inst.server.__class__ is ModelInstanceReference
    
def test31():
    inst = MyInfra("test31")
    assert inst.grid.__class__ is ModelInstanceReference
    
def test32():
    inst = MyInfra("test32")
    assert inst.grid[1].__class__ is ModelInstanceReference
    
def test33():
    inst = MyInfra("test33")
    assert inst.server is inst.server
    
def test34():
    inst = MyInfra("test34")
    assert inst.grid is inst.grid
    
def test35():
    inst = MyInfra("test35")
    assert inst.grid[1] is inst.grid[1]
    
def test36():
    inst = MyInfra("test36")
    assert inst.server.provisionedName is inst.server.provisionedName
    
def test37():
    inst = MyInfra("test37")
    assert inst.grid[1].provisionedName is inst.grid[1].provisionedName
    
def test38():
    inst = MyInfra("test38")
    assert inst.grid[3] is not inst.grid[4]
    
def test39():
    inst1 = MyInfra("test39a")
    inst2 = MyInfra("test39b")
    assert inst1.server is not inst2.server
    
def test40():
    inst1 = MyInfra("test40a")
    inst2 = MyInfra("test40b")
    assert inst1.grid[5] is not inst2.grid[6]
    
def test41():
    inst = MyInfra("test41")
    assert inst.grid[1].name.value() == "grid-comp_1"
    
def test42():
    inst = MyInfra("test42")
    assert inst.grid[7].provisionedName.get_path() == ["grid", "7", "provisionedName"]
    
def test43():
    inst = MyInfra("test43")
    _ = inst.grid[8]
    _ = inst.grid[9]
    _ = inst.grid[10]
    _ = inst.grid[9]
    assert len(inst.grid.instances()) == 3
    
def test44():
    inst = MyInfra("test44")
    modref = MyInfra.grid[11].provisionedName
    assert (modref.get_path() == inst.get_inst_ref(modref).get_path())
    
def test45():
    inst = MyInfra("test45")
    for ref in (MyInfra.grid[12], MyInfra.grid[13], MyInfra.grid[14]):
        _ = inst.get_inst_ref(ref)
    assert len(inst.grid.instances()) == 3
    
def test46():
    assert MyInfra.workers
    
def test47():
    assert MyInfra.workers[1]
    
def test48():
    assert MyInfra.workers[1] is MyInfra.workers[1]
    
def test49():
    assert MyInfra.workers[2].query.__class__ is not Server
    
def test50():
    assert MyInfra.workers[3].query is not MyInfra.workers[4].query
    
def test51():
    assert MyInfra.workers[5].query.value() is MyInfra.workers[6].query.value()
    
def test52():
    assert MyInfra.workers[7].query.name.value() == "query"
    
def test53():
    assert (MyInfra.workers[8].query.name.get_path() ==
            ["workers", "8", "query", "name"])
    
def test54():
    inst = MyInfra("test54")
    assert inst.workers[1]
    
def test55():
    inst = MyInfra("test55")
    assert inst.workers[2] is inst.workers[2]
    
def test56():
    inst = MyInfra("test56")
    assert inst.workers[3] is not inst.workers[4]
    
def test57():
    inst = MyInfra("test57")
    _ = inst.workers[5]
    _ = inst.workers[6]
    _ = inst.workers[7]
    _ = inst.workers[6]
    assert len(inst.workers.instances()) == 3
    
def test58():
    inst = MyInfra("test58")
    assert inst.workers[8].query.value() is not inst.workers[9].query.value
    
def test59():
    inst = MyInfra("test59")
    assert inst.workers[10].query is not MyInfra.workers[10].query
    
def test60():
    inst = MyInfra("test60")
    assert (inst.workers[11].handler.name.get_path() ==
            ["workers", "11", "handler", "name"])
    
def test61():
    inst = MyInfra("test61")
    ref = MyInfra.workers[12].ncube.provisionedName
    assert inst.get_inst_ref(ref).get_path() == ["workers", "12", "ncube", "provisionedName"]
    
def test62():
    inst = MyInfra("test62")
    for ref in (MyInfra.workers[13].query,
                MyInfra.workers[14].handler,
                MyInfra.workers[15].ncube):
        _ = inst.get_inst_ref(ref)
    assert len(inst.workers.instances()) == 3
    
def test63():
    inst1 = MyInfra("test63-1")
    inst2 = MyInfra("test63-2")
    assert inst1.workers[1] is not inst2.workers[1]
    
def test64():
    inst1 = MyInfra("test64-1")
    inst2 = MyInfra("test64-2")
    assert inst1.workers[2].query.value() is not inst2.workers[2].query.value()
    
def test65():
    inst1 = MyInfra("test65-1")
    inst2 = MyInfra("test65-2")
    modref = MyInfra.workers[16].query
    assert inst1.get_inst_ref(modref) is not inst2.get_inst_ref(modref)
    
def test66():
    inst1 = MyInfra("test66-1")
    inst2 = MyInfra("test66-2")
    assert inst1.workers[2].query.value().__class__ is inst2.workers[2].query.value().__class__
    
def test67():
    assert MyInfra.composite[1].grid[2].name
    
def test68():
    assert MyInfra.composite[2].workers[1].handler.name
    
def test69():
    assert (MyInfra.composite[3].workers[2].query.mem.get_path() ==
            ["composite", "3", "workers", "2", "query", "mem"])
    
def test70():
    inst = MyInfra("test70")
    ref = MyInfra.composite[4].workers[3].ncube.mem
    assert (inst.get_inst_ref(ref).get_path() ==
            ["composite", "4", "workers", "3", "ncube", "mem"])
    
def test71():
    inst = MyInfra("test71")
    _ = MyInfra.composite[5].workers[4].ncube.provisionedName
    assert len(inst.composite[5].workers.instances()) == 0
    
def test72():
    assert MyInfra.composite[1].value().__class__.__name__ == "ResourceGroup"
    
def test73():
    assert MyInfra.grid[1].value().__class__ is Server
    
def test74():
    inst = MyInfra("test74")
    assert inst.composite[1].value().__class__.__name__ == "ResourceGroup"
    
def test75():
    inst = MyInfra("test75")
    assert inst.grid[1].value().__class__ is Server
    
def test76():
    assert MyInfra.composite.value().__class__ in (MultiResourceGroup, MultiResource)
    
def test77():
    inst = MyInfra("test77")
    assert inst.composite.value().__class__ in (MultiResourceGroup, MultiResource)
    
def test78():
    modrefs = [MyInfra.composite,
               MyInfra.composite[1],
               MyInfra.composite[2].grid,
               MyInfra.composite[3].grid[1],
               MyInfra.composite[3].grid[1].name]
    s = set([ref.get_containing_component()
             for ref in modrefs
             if ref.get_containing_component() is not None])
    assert len( s ) == 1, "There was more than one resource"
    
def test79():
    assert MyInfra.grid[1].get_containing_component() == MyInfra.grid[1].name.get_containing_component()
    
def test80():
    assert (MyInfra.composite[1].grid[1].get_containing_component() ==
            MyInfra.composite[1].grid[1].name.get_containing_component())
    
def test81():
    inst = MyInfra("test81")
    modrefs = [inst.grid[1].name,
               inst.grid[2].name,
               inst.grid[3].name,
               inst.grid[3],
               inst.grid]
    assert len(set([p for p in [r.get_containing_component() for r in modrefs] if p is not None])) == 3
    
def test82():
    inst = MyInfra("test82")
    assert len(inst.components()) == 2
    
def test83():
    class ProvTest(InfraModel):
        grid = MultiResource(Server("prov1", mem="8GB"))
    inst = ProvTest("prov1")
    _ = inst.grid[1]
    assert len(inst.components()) == 1
    
def test84():
    inst = MyInfra("test84")
    _ = inst.grid[1]
    assert len(inst.components()) == 3
    
def test85():
    inst = MyInfra("test85")
    for i in range(5):
        _ = inst.grid[i]
    assert len(inst.components()) == 7
    
def test86():
    inst = MyInfra("test86")
    _ = inst.workers[1]
    assert len(inst.components()) == 5
    
def test87():
    inst = MyInfra("test87")
    _ = inst.workers[1].handler
    assert len(inst.components()) == 5
    
def test88():
    inst = MyInfra("test88")
    for i in range(2):
        _ = inst.workers[i]
    assert len(inst.components()) == 8
    
def test89():
    inst = MyInfra("test89")
    _ = inst.composite[1]
    assert len(inst.components()) == 2
    
def test90():
    inst = MyInfra("test90")
    _ = inst.composite[1].grid[1]
    assert len(inst.components()) == 3

def test91():
    inst = MyInfra("test91")
    _ = inst.composite[1].workers
    assert len(inst.components()) == 2
    
def test92():
    inst = MyInfra("test92")
    _ = inst.composite[1].workers[1]
    assert len(inst.components()) == 5
    
def test93():
    inst = MyInfra("test93")
    _ = inst.composite[1].workers[1]
    for i in range(2):
        _ = inst.composite[i+2].grid[1]
    assert len(inst.components()) == 7
    
def test94():
    inst = MyInfra("test94")
    for i in range(5):
        _ = inst.grid[i]
    assert len(inst.grid) == 5
    
def test95():
    inst = MyInfra("test95")
    assert not inst.grid
    
def test96():
    inst = MyInfra("test96")
    assert inst.server
    
def test97():
    inst = MyInfra("test97")
    assert inst.server.name
    
def test98():
    inst = MyInfra("test98")
    assert not inst.server.provisionedName
    
def test99():
    inst = MyInfra("test99")
    inst.grid[1]
    assert inst.grid
    
def test100():
    inst = MyInfra("test100")
    inst.grid[1]
    assert inst.grid[1].name
    
def test101():
    inst = MyInfra("test101")
    inst.grid[1]
    assert not inst.grid[1].provisionedName
    
def test102():
    inst = MyInfra("test102")
    assert not inst.workers
    
def test103():
    inst = MyInfra("test103")
    inst.workers[1]
    assert inst.workers
    
def test104():
    inst = MyInfra("test104")
    inst.workers[1]
    assert inst.workers[1].handler
    
def test105():
    inst = MyInfra("test105")
    inst.workers[1]
    assert inst.workers[1].handler.name
    
def test106():
    inst = MyInfra("test106")
    inst.workers[1]
    assert not inst.workers[1].handler.provisionedName
    
def test107():
    inst = MyInfra("test107")
    assert not inst.composite
    
def test108():
    inst = MyInfra("test108")
    inst.composite[1]
    assert inst.composite
    
def test109():
    inst = MyInfra("test109")
    inst.composite[1]
    assert not inst.composite[1].grid
    
def test110():
    inst = MyInfra("test110")
    inst.composite[1]
    inst.composite[1].grid[1]
    assert inst.composite[1].grid
    
def test111():
    inst = MyInfra("test111")
    inst.composite[1]
    inst.composite[1].grid[1]
    assert inst.composite[1].grid[1].name
    
def test112():
    inst = MyInfra("test112")
    inst.composite[1]
    inst.composite[1].grid[1]
    assert not inst.composite[1].grid[1].provisionedName
    
def test113():
    inst = MyInfra("test113")
    inst.composite[1]
    assert not inst.composite[1].workers
    
def test114():
    inst = MyInfra("test114")
    inst.composite[1].workers[1]
    assert inst.composite[1].workers
    
def test115():
    inst = MyInfra("test115")
    inst.composite[1].workers[1]
    assert inst.composite[1].workers[1].handler
    
def test116():
    inst = MyInfra("test116")
    inst.composite[1].workers[1]
    assert inst.composite[1].workers[1].handler.name
    
def test117():
    inst = MyInfra("test117")
    inst.composite[1].workers[1]
    assert not inst.composite[1].workers[1].handler.provisionedName
    
def test118():
    #this is just ensuring we throw if a component derived class  fails to
    #implement fix_arguments()
    class MissedMethod1(AbstractModelingEntity):
        def __init__(self, name, arg1, arg2):
            super(MissedMethod1, self).__init__(name)
            self.arg1 = arg1
            self.arg2 = arg2
    comp = MissedMethod1("oops!", 1, 2)
    try:
        comp.fix_arguments()
        assert False, "fix_arguments should have thrown an exception"
    except TypeError, _:
        assert True
    except Exception, e:
        assert False, "got an unexpected exception: '%s'" % e.message
        
def test119():
    class CGTest1(InfraModel):
        group = ResourceGroup("group",
                               reqhandler=Server("reqhandler", mem="8GB"),
                               db=Database("db"))
    inst = CGTest1("cgtest1")
    assert inst.group.reqhandler
    
def test120():
    class CGTest2(InfraModel):
        group = ResourceGroup("group",
                               reqhandler=Server("reqhandler", mem="8GB"),
                               grid=MultiResource(Server("grid", mem="8GB")))
    inst = CGTest2("cgt2")
    _ = inst.group.grid[1]
    assert inst.group.grid[1] is inst.group.grid[1]
    
def test121():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiResource(Server("grid", mem="8GB")))
    class CGTest3(InfraModel):
        overlord = Server("overlord", mem="8GB")
        groups = MultiResource(group_thing)
        
    inst = CGTest3("cgt3")
    _ = inst.groups[1].grid[2]
    assert inst.groups[1].grid[2].value() is not inst.groups[2].grid[1].value()
    
def test122():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiResource(Server("grid", mem="8GB")))
    class CGTest4(InfraModel):
        group = group_thing

    inst1 = CGTest4("cgt4-1")
    inst2 = CGTest4("cgt4-2")
    assert inst1.group.reqhandler.value() is not inst2.group.reqhandler.value()

def test123():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiResource(Server("grid", mem="8GB")))
    class CGTest5a(InfraModel):
        group = group_thing

    class CGTest5b(InfraModel):
        group = group_thing

    inst1 = CGTest5a("cgt5a-1")
    inst2 = CGTest5b("cgt5b-2")
    assert inst1.group.value() is not inst2.group.value()
    
def test124():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiResource(Server("grid", mem="8GB",
                                                            rhm=ctxt.comp.container.container.reqhandler.mem)))
    class CGTest6(InfraModel):
        group = group_thing
        
    inst = CGTest6("ctg6")
    inst.group.grid[0]
    inst.group.grid[1]
    inst.refs_for_components()
    try:
        inst.group.fix_arguments()
    except Exception, e:
        assert False, "Fixing the arguments failed; %s" % e.message
    
def test125():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiResource(Server("grid", mem="8GB",
                                                            rhm=ctxt.comp.container.container.reqhandler.mem)))
    class CGTest7(InfraModel):
        group = group_thing
        
    inst = CGTest7("ctg7")
    inst.group.grid[0]
    inst.group.grid[1]
    inst.group.fix_arguments()
    assert inst.group.grid[0].rhm.value() is inst.group.grid[1].rhm.value()

def test126():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 slave=Server("grid", mem=ctxt.comp.container.reqhandler.mem))
    class CGTest8(InfraModel):
        group = group_thing
        
    inst = CGTest8("ctg8")
    inst.refs_for_components()
    inst.group.fix_arguments()
    assert inst.group.slave.mem.value() == "8GB"

def test127():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 slave=Server("grid", mem=ctxt.comp.container.reqhandler.mem))
    class CGTest9(InfraModel):
        top = Server("topper", mem=ctxt.model.group.reqhandler.mem)
        group = group_thing
        
    inst = CGTest9("ctg9")
    inst.refs_for_components()
    _ = inst.components()
    inst.top.fix_arguments()
    inst.group.fix_arguments()
    assert inst.top.mem.value() == "8GB"

def test128():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 slave=Server("grid", mem=ctxt.comp.container.reqhandler.mem,
                                              path=ctxt.comp.container.reqhandler._path))
    class CGTest10(InfraModel):
        group = group_thing
        
    inst = CGTest10("cgt10")
    inst.components()
    inst.refs_for_components()
    inst.group.fix_arguments()
    assert inst.group.slave.path.value() == ("reqhandler", "container", "comp")
    
def test130():
    class BadRefClass(AbstractModelReference):
        pass
    
    class Test130(InfraModel):
        ref_class = BadRefClass
        grid = MultiResource(Server("grid", mem="8GB"))
        
    inst = Test130("t130")
    try:
        _ = inst.grid[1]
        assert False, "Should have raised a TypeError about _get_item_ref_obj()"
    except TypeError, e:
        assert "get_item_ref_obj" in e.message
        
def test131():
    class Test131(InfraModel):
        server = Server("dummy", mem="8GB", adict={'a':1, 'b':2, 'c':3})
    inst = Test131("t131")
    assert inst.server.adict['a'] == 1
    
def test132():
    class Test132(InfraModel):
        server = Server("dummy", mem="8GB", no_key=5)
    inst = Test132("t132")
    try:
        inst.server.no_key[2]
        assert False, "We were allowed to use a key on a non-collection attribute"
    except TypeError, e:
        assert "keyed" in e.message
        
def test133():
    def tfunc(context):
        return context.model.server.mem
    
    class Test133(InfraModel):
        reqhandler = Server("dummy1", mem=tfunc)
        server = Server("dummy2", mem="16GB")
    
    inst = Test133("t133")
    _ = inst.components()
    inst.reqhandler.fix_arguments()
    assert inst.reqhandler.mem.value() == "16GB"

def test134():
    components = {"server":Server("dummy", mem="16GB"),
                  "db":Database("db", wibble=9)}

    class Test134(InfraModel):
        with_resources(**components)

    inst = Test134("t134")
    assert inst.server.mem.value() == "16GB" and inst.db.wibble.value() == 9

def test135():
    group_thing = ResourceGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 slaves=MultiResource(Server("grid", mem=ctxt.comp.container.container.reqhandler.mem)))
    components = {"group":group_thing}
    class Test135(InfraModel):
        with_resources(**components)

    inst = Test135("t135")
    _ = inst.group.slaves[1]
    _ = inst.group.slaves[2]
    inst.components()
    inst.refs_for_components()
    inst.group.fix_arguments()
    assert inst.group.slaves[2].mem.value() == "8GB"
    
def test136():
    class Test136(InfraModel):
        hive = MultiResource(Server("worker", mem="8GB"))
        
    inst = Test136("t136")
    for i in range(5):
        _ = inst.hive[i]
        
    assert len(inst.hive.keys()) == 5
    
def test137():
    class Test137(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test137("t137")
    for i in range(5):
        _ = inst.hive[i]
         
    assert len(inst.hive.values()) == 5 and inst.hive[2] in inst.hive.values()

def test138():
    class Test138(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test138("t138")
    for i in range(5):
        _ = inst.hive[i]
    
    d = {k:v for k, v in inst.hive.items()}
    assert len(d) == 5 and inst.hive[1] in d.values()

def test139():
    class Test139(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test139("t139")
    for i in range(5):
        _ = inst.hive[i]
         
    assert inst.hive.has_key(3)
    
def test140():
    class Test140(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test140("t140")
    for i in range(5):
        _ = inst.hive[i]
        
    assert inst.hive.get(3) is inst.hive[3]
    
def test141():
    class Test141(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test141("t141")
    for i in range(5):
        _ = inst.hive[i]
        
    assert len([k for k in inst.hive.iterkeys()]) == 5
    
def test142():
    class Test142(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test142("t142")
    for i in range(5):
        _ = inst.hive[i]
    
    l = [v for v in inst.hive.itervalues()]
    assert len(l) == 5 and inst.hive[4] in l
    
def test143():
    class Test143(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test143("t143")
    for i in range(5):
        _ = inst.hive[i]
    
    d = {k:v for k, v in inst.hive.iteritems()}
    assert len(d) == 5 and inst.hive[0] in d.values()
    
def test144():
    class Test144(InfraModel):
        hive = MultiResource(Server("drone", mem="8GB"))
         
    inst = Test144("t144")
    for i in range(5):
        _ = inst.hive[i]
    assert 3 in inst.hive
    
def test145():
    class Test145(InfraModel):
        hive = MultiResource(ResourceGroup("crowd", drones=Server("drone", mem="8GB"),
                                             dregs=MultiResource(Server("dreg", mem="2GB"))))
         
    inst = Test145("t145")
    for i in range(5):
        _ = inst.hive[0].dregs[i]
        
    d = {k:v for k, v in inst.hive[0].dregs.items()}
    assert (len(inst.hive[0].dregs) == 5 and
            len(inst.hive[0].dregs.keys()) == 5 and
            3 in inst.hive[0].dregs and
            len(inst.hive[0].dregs.values()) == 5 and
            len(d) == 5 and
            inst.hive[0].dregs[2] in d.values())
    
def test146():
    class Test(InfraModel):
        grid = MultiResource(Server("grid-node", mem="8GB"))
    
    inst = Test("key")
    for i in range(5):
        _ = inst.grid[i]
    assert inst.grid[3]._name == "3"
    
def test147():
    try:
        class Test(InfraModel):
            app_server = Server("app_server", mem="8GB")
            with_resources(grid="not a resource")
        assert False, "The class def should have raised an exception"
    except InfraException, e:
        assert "grid is not derived" in e.message
    
def test148():
    class Test(InfraModel):
        app_server = Server("app_server", mem="8GB")
    inst = Test("inst")
    assert not inst.provisioning_been_computed()
    
def test149():
    class Test(InfraModel):
        app_server = Server("app_server", mem="8GB")
    inst = Test("inst")
    inst.compute_provisioning_from_refs([Test.app_server])
    try:
        inst.compute_provisioning_from_refs([Test.app_server])
        assert False, "was allowed to compute provisioning twice"
    except InfraException, e:
        assert "has already been" in e.message
        
def test150():
    from actuator.infra import IPAddressable
    class NoAdminIP(IPAddressable):
        pass
    s = NoAdminIP()
    try:
        _ = s.get_ip()
        raise False, "Should not have been able to call get_ip()"
    except TypeError, e:
        assert "Not implemented" in e.message
        
def test151():
    s = Server("someserver", mem="8GB")
    class Test(InfraModel):
        s1 = s
        s2 = s
        s3 = s
        
    inst = Test("test")
    assert len(inst.components()) == 3
    
    
def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            

if __name__ == "__main__":
    do_all()
    
    