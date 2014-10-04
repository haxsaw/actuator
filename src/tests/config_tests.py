'''
Created on 13 Jul 2014

@author: tom
'''
from actuator import *
from actuator.config import _Dependency, _ConfigTask
from actuator.infra import ServerRef

MyConfig = None
search_path = ["p1", "p2", "p3"]


def setup():
    global MyConfig
    class MyTestConfig(ConfigSpec):
        with_searchpath(*search_path)
        t1 = NullTask()
        t2 = Template()
        with_dependencies(t1 | t2)
        
    MyConfig = MyTestConfig
    
    
def make_dep_tuple_set(config):
    return set([(d.from_task.path, d.to_task.path) for d in config.get_dependencies()])
    
    
def test01():
    assert MyConfig
    
def test02():
    expected_path = set(search_path)
    assert expected_path == set(MyConfig.__searchpath__)
    
def test03():
    assert 1 == len(MyConfig.__dependencies__)
    
def test04():
    try:
        class T4Config(ConfigSpec):
            t1 = NullTask()
            with_dependencies(t1 | "other")
        raise Exception("Failed to catch dependency creation with non-task")
    except:
        assert True
        
def test05():
    try:
        _ = _Dependency(NullTask(), "other")
        raise Exception("Failed to catch _Dependency creation with 'to' as non-task")
    except:
        assert True
        
def test06():
    try:
        _ = _Dependency("other", NullTask())
        raise Exception("Failed to catch _Dependency creation with 'from' as non-task")
    except:
        assert True

def test07():
    assert 2 == len(MyConfig._node_dict_)
    
def test08():
    try:
        class TC8(ConfigSpec):
            t1 = NullTask()
            t2 = NullTask()
            t3 = NullTask()
            with_dependencies(t1 | t2,
                              t2 | t3,
                              t3 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test09():
    class TC9(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t2 | t3)
    assert make_dep_tuple_set(TC9) == set([("t1", "t2"), ("t2", "t3")])
        
def test10():
    try:
        class TC10(ConfigSpec):
            t1 = NullTask()
            t2 = NullTask()
            t3 = NullTask()
            with_dependencies(t1 | t2 | t3 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test10a():
    try:
        class TC10a(ConfigSpec):
            t1 = NullTask("t1")
            t2 = NullTask("t2")
            t3 = NullTask("t3")
            with_dependencies(t1 | t2 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test11():
    try:
        class TC11(ConfigSpec):
            t1 = NullTask("t1")
            t2 = NullTask("t2")
            t3 = NullTask("t3")
            t4 = NullTask("t4")
            t5 = NullTask("t5")
            with_dependencies(t1 | t2 | t3 | t4)
            with_dependencies(t3 | t4 | t5)
            with_dependencies(t4 | t2)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test12():
    class TC12(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
    assert make_dep_tuple_set(TC12) == set([("t1", "t3"), ("t2", "t3")])

def test13():
    class TC13(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        with_dependencies(TaskGroup(t1, t2 | t3) | t4)
    assert make_dep_tuple_set(TC13) == set([("t2", "t3"), ("t1", "t4"), ("t3", "t4")])

def test14():
    class TC14(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        with_dependencies(TaskGroup(t1, t2) | TaskGroup(t3, t4))
    assert make_dep_tuple_set(TC14) == set([("t2", "t3"), ("t1", "t4"),
                                            ("t1", "t3"), ("t2", "t4")])

def test15():
    class TC15(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        with_dependencies(TaskGroup(t1 | t2, t3 | t4))
    assert make_dep_tuple_set(TC15) == set([("t1", "t2"), ("t3", "t4")])

def test16():
    class TC16(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | TaskGroup(t2, t3))
    assert make_dep_tuple_set(TC16) == set([("t1", "t3"), ("t1", "t2")])

def test17():
    class TC17(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        t5 = NullTask("t5")
        t6 = NullTask("t6")
        t7 = NullTask("t7")
        t8 = NullTask("t8")
        t9 = NullTask("t9")
        t0 = NullTask("t0")
        with_dependencies(TaskGroup(t1 | t2, TaskGroup(t3, t4)) | t5 |
                          TaskGroup(TaskGroup(t6, t7, t8), t9 | t0))
    assert make_dep_tuple_set(TC17) == set([("t1", "t2"), ("t2", "t5"),
                                            ("t3", "t5"), ("t4", "t5"),
                                            ("t5", "t6"), ("t5", "t7"),
                                            ("t5", "t8"), ("t5", "t9"),
                                            ("t9", "t0")])

def test18():
    class TC18(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(TaskGroup(t1, TaskGroup(t2, TaskGroup(t3))))
    assert make_dep_tuple_set(TC18) == set()

def test19():
    class TC19(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
    assert make_dep_tuple_set(TC19) == set([("t1", "t2"), ("t2", "t3")])

def test20():
    class TC20(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        t5 = NullTask("t5")
        t6 = NullTask("t6")
        t7 = NullTask("t7")
        t8 = NullTask("t8")
        t9 = NullTask("t9")
        t0 = NullTask("t0")
        with_dependencies(TaskGroup(t1 | t2, TaskGroup(t3, t4)) | t5)
        with_dependencies(t5 | TaskGroup(TaskGroup(t6, t7, t8), t9 | t0))
    assert make_dep_tuple_set(TC20) == set([("t1", "t2"), ("t2", "t5"),
                                            ("t3", "t5"), ("t4", "t5"),
                                            ("t5", "t6"), ("t5", "t7"),
                                            ("t5", "t8"), ("t5", "t9"),
                                            ("t9", "t0")])

def test21():
    class TC21(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
        with_dependencies(t1 | t2)
    assert make_dep_tuple_set(TC21) == set([("t1", "t2"), ("t2", "t3")])
    
def test22():
    class First(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t3, t2 | t3)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test23():
    class First(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        with_dependencies(TaskGroup(t1, t1 | t2))
        
    class Second(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        with_dependencies(t1 | t2)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test24():
    class First(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(TaskGroup(t1, t2, t3), t1 | t3)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(TaskGroup(t1 | t3, t2))
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test25():
    class First(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t2 | t3, t1 | TaskGroup(t2, t3))
        
    class Second(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test26():
    TG = TaskGroup
    class First(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        t5 = NullTask("t5")
        with_dependencies(TG(TG(t1, t2, t3), t4 | t5),
                          t2 | t4,
                          t3 | t5)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1")
        t2 = NullTask("t2")
        t3 = NullTask("t3")
        t4 = NullTask("t4")
        t5 = NullTask("t5")
        with_dependencies(t2 | t4 | t5,
                          t3 | t5)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

#tests after this point will use these classes
class Capture(object):
    def __init__(self):
        self.performed = []
        
    def __call__(self, name, task):
        self.performed.append((name, task))
        
    def pos(self, name, task):
        return self.performed.index((name, task))
        
    
class ReportingTask(_ConfigTask):
    def __init__(self, target, report=lambda n, o: (n, o), **kwargs):
        super(ReportingTask, self).__init__(**kwargs)
        self.target = target
        self.report = report
        
    def perform(self):
        self.report(self.target.name, self)

class BogusServerRef(ServerRef):
    def get_admin_ip(self):
        return "8.8.8.8"
        

def test27():
    cap = Capture()
        
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        ping_task = ReportingTask(PingNamespace.ping_target, report=cap)
        
    cfg = PingConfig()
    cfg.perform_with(ns)
    assert cap.performed
    
def test28():
    cap = Capture()
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        t3 = ReportingTask(PingNamespace.ping_target, report=cap)
        t2 = ReportingTask(PingNamespace.ping_target, report=cap)
        t1 = ReportingTask(PingNamespace.ping_target, report=cap)
        with_dependencies(t1 | t2 | t3)
    
    cfg = PingConfig()
    cfg.perform_with(ns)
    assert (cap.pos("ping_target", PingConfig.t1) <
            cap.pos("ping_target", PingConfig.t2) <
            cap.pos("ping_target", PingConfig.t3) )
        
def test29():
    cap = Capture()
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        t3 = ReportingTask(PingNamespace.ping_target, report=cap)
        t2 = ReportingTask(PingNamespace.ping_target, report=cap)
        t1 = ReportingTask(PingNamespace.ping_target, report=cap)
        t4 = ReportingTask(PingNamespace.ping_target, report=cap)
        t5 = ReportingTask(PingNamespace.ping_target, report=cap)
        with_dependencies(t1 | t2 | t3,
                          t4 | t2,
                          t4 | t3,
                          t5 | t3)
    
    cfg = PingConfig()
    cfg.perform_with(ns)
    assert (cap.pos("ping_target", PingConfig.t1) <
            cap.pos("ping_target", PingConfig.t2) <
            cap.pos("ping_target", PingConfig.t3) and
            cap.performed[-1] == ("ping_target", PingConfig.t3) and
            cap.pos("ping_target", PingConfig.t4) <
            cap.pos("ping_target", PingConfig.t2))
        

def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
