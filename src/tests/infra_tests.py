'''
Created on 4 Jun 2014

@author: tom
'''
from actuator import InfraSpec, MultiComponent, MultiComponentGroup, ComponentGroup
from actuator.infra import InfraModelReference, InfraModelInstanceReference, InfraComponentBase
from actuator.provisioners.example_components import Server, Database

MyInfra = None

def setup():
    global MyInfra
    class MyInfraLocal(InfraSpec):
        other = "some data"
        server = Server("wibble", mem="16GB")
        grid = MultiComponent(Server("grid-comp", mem="8GB"))
        database = Database("db")
        workers = MultiComponentGroup("workers",
                                      handler=Server("handler", mem="4GB"),
                                      query=Server("query", mem="8GB"),
                                      ncube=Server("ncube", mem="16GB"))
        composite = MultiComponentGroup("grid",
                                        grid=MultiComponent(Server("grid-comp", mem="8GB")),
                                        workers=MultiComponentGroup("inner_workers",
                                                                    handler=Server("handler", mem="4GB"),
                                                                    query=Server("query", mem="8GB"),
                                                                    ncube=Server("ncube", mem="16GB")))
    MyInfra = MyInfraLocal

def test01():
    assert type({}) == type(MyInfra.__components), "the __components attr is missing or the wrong type"
    
def test02():
    assert type(MyInfra.server) != Server, "the type of a component attribute isn't a ref"
    
def test03():
    assert MyInfra.server is MyInfra.server, "references aren't being reused"

def test04():
    assert type(MyInfra.server.logicalName) is InfraModelReference, \
            "data member on a component isn't being wrapped with a reference"
    
def test05():
    assert MyInfra.other == "some data", "plain class attrs aren't being passed thru"
    
def test06():
    try:
        _ = MyInfra.server.wibble
        assert False, "failed to raise AttributeError when accessing a bad attr"
    except AttributeError, _:
        pass
    
def test07():
    assert MyInfra.server.logicalName is MyInfra.server.logicalName, \
            "reference reuse not occurring on component attribute"
    
def test08():
    assert MyInfra.server.mem, "failed to create ref for kw-created attr"
    
def test09():
    assert type(MyInfra.server.provisionedName) == InfraModelReference, \
            "data member on a component isn't being wrapped with a reference"

def test10():
    assert MyInfra.server.value().__class__ is Server, \
            "value underlying a component ref is the wrong class"
    
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
    assert MyInfra.grid[1].__class__ == InfraModelReference, \
        "did not get a ref for a keyed MultiComponent"
    
def test14():
    assert MyInfra.grid.__class__ == InfraModelReference, \
        "did not get a ref for a MultiComponent"
    
def test15():
    assert MyInfra.grid[1] is MyInfra.grid[1], \
        "refs not being reused for keyed MultiCcmponent"
    
def test16():
    assert MyInfra.grid[2].logicalName.__class__ == InfraModelReference
    
def test17():
    assert (MyInfra.grid[3].logicalName is MyInfra.grid[3].logicalName)
    
def test18():
    assert MyInfra.grid[4].logicalName is not MyInfra.grid[5].logicalName
    
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
    assert MyInfra.grid[5].logicalName.get_path() == ["grid", "5", "logicalName"]
    
def test28():
    inst = MyInfra("test28")
    assert inst
    
def test29():
    inst = MyInfra("test29")
    assert inst.other == "some data"
    
def test30():
    inst = MyInfra("test30")
    assert inst.server.__class__ is InfraModelInstanceReference
    
def test31():
    inst = MyInfra("test31")
    assert inst.grid.__class__ is InfraModelInstanceReference
    
def test32():
    inst = MyInfra("test32")
    assert inst.grid[1].__class__ is InfraModelInstanceReference
    
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
    assert inst.grid[1].logicalName.value() == "grid-comp_1"
    
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
    assert MyInfra.workers[7].query.logicalName.value() == "query"
    
def test53():
    assert (MyInfra.workers[8].query.logicalName.get_path() ==
            ["workers", "8", "query", "logicalName"])
    
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
    assert (inst.workers[11].handler.logicalName.get_path() ==
            ["workers", "11", "handler", "logicalName"])
    
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
    assert MyInfra.composite[1].grid[2].logicalName
    
def test68():
    assert MyInfra.composite[2].workers[1].handler.logicalName
    
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
    assert MyInfra.composite[1].value().__class__.__name__ == "ComponentGroup"
    
def test73():
    assert MyInfra.grid[1].value().__class__ is Server
    
def test74():
    inst = MyInfra("test74")
    assert inst.composite[1].value().__class__.__name__ == "ComponentGroup"
    
def test75():
    inst = MyInfra("test75")
    assert inst.grid[1].value().__class__ is Server
    
def test76():
    assert MyInfra.composite.value().__class__ in (MultiComponentGroup, MultiComponent)
    
def test77():
    inst = MyInfra("test77")
    assert inst.composite.value().__class__ in (MultiComponentGroup, MultiComponent)
    
def test78():
    modrefs = [MyInfra.composite,
               MyInfra.composite[1],
               MyInfra.composite[2].grid,
               MyInfra.composite[3].grid[1],
               MyInfra.composite[3].grid[1].logicalName]
    s = set([ref.get_containing_provisionable()
             for ref in modrefs
             if ref.get_containing_provisionable() is not None])
    assert len( s ) == 1, "There was more than one provisionable"
    
def test79():
    assert MyInfra.grid[1].get_containing_provisionable() == MyInfra.grid[1].logicalName.get_containing_provisionable()
    
def test80():
    assert (MyInfra.composite[1].grid[1].get_containing_provisionable() ==
            MyInfra.composite[1].grid[1].logicalName.get_containing_provisionable())
    
def test81():
    inst = MyInfra("test81")
    modrefs = [inst.grid[1].logicalName,
               inst.grid[2].logicalName,
               inst.grid[3].logicalName,
               inst.grid[3],
               inst.grid]
    assert len(set([p for p in [r.get_containing_provisionable() for r in modrefs] if p is not None])) == 3
    
def test82():
    inst = MyInfra("test82")
    assert len(inst.provisionables()) == 2
    
def test83():
    class ProvTest(InfraSpec):
        grid = MultiComponent(Server("prov1", mem="8GB"))
    inst = ProvTest("prov1")
    _ = inst.grid[1]
    assert len(inst.provisionables()) == 1
    
def test84():
    inst = MyInfra("test84")
    _ = inst.grid[1]
    assert len(inst.provisionables()) == 3
    
def test85():
    inst = MyInfra("test85")
    for i in range(5):
        _ = inst.grid[i]
    assert len(inst.provisionables()) == 7
    
def test86():
    inst = MyInfra("test86")
    _ = inst.workers[1]
    assert len(inst.provisionables()) == 5
    
def test87():
    inst = MyInfra("test87")
    _ = inst.workers[1].handler
    assert len(inst.provisionables()) == 5
    
def test88():
    inst = MyInfra("test88")
    for i in range(2):
        _ = inst.workers[i]
    assert len(inst.provisionables()) == 8
    
def test89():
    inst = MyInfra("test89")
    _ = inst.composite[1]
    assert len(inst.provisionables()) == 2
    
def test90():
    inst = MyInfra("test90")
    _ = inst.composite[1].grid[1]
    assert len(inst.provisionables()) == 3

def test91():
    inst = MyInfra("test91")
    _ = inst.composite[1].workers
    assert len(inst.provisionables()) == 2
    
def test92():
    inst = MyInfra("test92")
    _ = inst.composite[1].workers[1]
    assert len(inst.provisionables()) == 5
    
def test93():
    inst = MyInfra("test93")
    _ = inst.composite[1].workers[1]
    for i in range(2):
        _ = inst.composite[i+2].grid[1]
    assert len(inst.provisionables()) == 7
    
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
    assert inst.server.logicalName
    
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
    assert inst.grid[1].logicalName
    
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
    assert inst.workers[1].handler.logicalName
    
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
    assert inst.composite[1].grid[1].logicalName
    
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
    assert inst.composite[1].workers[1].handler.logicalName
    
def test117():
    inst = MyInfra("test117")
    inst.composite[1].workers[1]
    assert not inst.composite[1].workers[1].handler.provisionedName
    
def test118():
    class MissedMethod1(InfraComponentBase):
        def __init__(self, logicalName, arg1, arg2):
            super(MissedMethod1, self).__init__(logicalName)
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
    class CGTest1(InfraSpec):
        group = ComponentGroup("group",
                               reqhandler=Server("reqhandler", mem="8GB"),
                               db=Database("db"))
    inst = CGTest1("cgtest1")
    assert inst.group.reqhandler
    
def test120():
    class CGTest2(InfraSpec):
        group = ComponentGroup("group",
                               reqhandler=Server("reqhandler", mem="8GB"),
                               grid=MultiComponent(Server("grid", mem="8GB")))
    inst = CGTest2("cgt2")
    _ = inst.group.grid[1]
    assert inst.group.grid[1] is inst.group.grid[1]
    
def test121():
    group_thing = ComponentGroup("group",
                                 reqhandler=Server("reqhandler", mem="8GB"),
                                 grid=MultiComponent(Server("grid", mem="8GB")))
    class CGTest3(InfraSpec):
        overlord = Server("overlord", mem="8GB")
        groups = MultiComponent(group_thing)
        
    inst = CGTest3("cgt3")
    _ = inst.groups[1].grid[2]
    assert inst.groups[1].grid[2].value() is not inst.groups[2].grid[1].value()
    

def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()
    
    