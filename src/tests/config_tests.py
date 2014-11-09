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
from actuator.namespace import NSMultiComponent

'''
Created on 13 Jul 2014
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
        t1 = NullTask("nt")
        t2 = Template("temp")
        with_dependencies(t1 | t2)
        
    MyConfig = MyTestConfig
    
    
def make_dep_tuple_set(config):
    return set([(d.from_task.path, d.to_task.path) for d in config.get_class_dependencies()])
    
    
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
            t1 = NullTask("nt")
            with_dependencies(t1 | "other")
        raise Exception("Failed to catch dependency creation with non-task")
    except:
        assert True
        
def test05():
    try:
        _ = _Dependency(NullTask("nt"), "other")
        raise Exception("Failed to catch _Dependency creation with 'to' as non-task")
    except:
        assert True
        
def test06():
    try:
        _ = _Dependency("other", NullTask("nt"))
        raise Exception("Failed to catch _Dependency creation with 'from' as non-task")
    except:
        assert True

def test07():
    assert 2 == len(MyConfig._node_dict)
    
def test08():
    try:
        class TC8(ConfigSpec):
            t1 = NullTask("nt")
            t2 = NullTask("nt")
            t3 = NullTask("nt")
            with_dependencies(t1 | t2,
                              t2 | t3,
                              t3 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test09():
    class TC9(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3)
    assert make_dep_tuple_set(TC9) == set([("t1", "t2"), ("t2", "t3")])
        
def test10():
    try:
        class TC10(ConfigSpec):
            t1 = NullTask("t1", path="t1")
            t2 = NullTask("t2", path="t2")
            t3 = NullTask("t3", path="t3")
            with_dependencies(t1 | t2 | t3 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test10a():
    try:
        class TC10a(ConfigSpec):
            t1 = NullTask("t1", path="t1")
            t2 = NullTask("t2", path="t2")
            t3 = NullTask("t3", path="t3")
            with_dependencies(t1 | t2 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test11():
    try:
        class TC11(ConfigSpec):
            t1 = NullTask("t1", path="t1")
            t2 = NullTask("t2", path="t2")
            t3 = NullTask("t3", path="t3")
            t4 = NullTask("t4", path="t4")
            t5 = NullTask("t5", path="t5")
            with_dependencies(t1 | t2 | t3 | t4)
            with_dependencies(t3 | t4 | t5)
            with_dependencies(t4 | t2)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test12():
    class TC12(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
    assert make_dep_tuple_set(TC12) == set([("t1", "t3"), ("t2", "t3")])

def test13():
    class TC13(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1, t2 | t3) | t4)
    assert make_dep_tuple_set(TC13) == set([("t2", "t3"), ("t1", "t4"), ("t3", "t4")])

def test14():
    class TC14(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1, t2) | TaskGroup(t3, t4))
    assert make_dep_tuple_set(TC14) == set([("t2", "t3"), ("t1", "t4"),
                                            ("t1", "t3"), ("t2", "t4")])

def test15():
    class TC15(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1 | t2, t3 | t4))
    assert make_dep_tuple_set(TC15) == set([("t1", "t2"), ("t3", "t4")])

def test16():
    class TC16(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | TaskGroup(t2, t3))
    assert make_dep_tuple_set(TC16) == set([("t1", "t3"), ("t1", "t2")])

def test17():
    class TC17(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        t6 = NullTask("t6", path="t6")
        t7 = NullTask("t7", path="t7")
        t8 = NullTask("t8", path="t8")
        t9 = NullTask("t9", path="t9")
        t0 = NullTask("t0", path="t0")
        with_dependencies(TaskGroup(t1 | t2, TaskGroup(t3, t4)) | t5 |
                          TaskGroup(TaskGroup(t6, t7, t8), t9 | t0))
    assert make_dep_tuple_set(TC17) == set([("t1", "t2"), ("t2", "t5"),
                                            ("t3", "t5"), ("t4", "t5"),
                                            ("t5", "t6"), ("t5", "t7"),
                                            ("t5", "t8"), ("t5", "t9"),
                                            ("t9", "t0")])

def test18():
    class TC18(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, TaskGroup(t2, TaskGroup(t3))))
    assert make_dep_tuple_set(TC18) == set()

def test19():
    class TC19(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
    assert make_dep_tuple_set(TC19) == set([("t1", "t2"), ("t2", "t3")])

def test20():
    class TC20(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        t6 = NullTask("t6", path="t6")
        t7 = NullTask("t7", path="t7")
        t8 = NullTask("t8", path="t8")
        t9 = NullTask("t9", path="t9")
        t0 = NullTask("t0", path="t0")
        with_dependencies(TaskGroup(t1 | t2, TaskGroup(t3, t4)) | t5)
        with_dependencies(t5 | TaskGroup(TaskGroup(t6, t7, t8), t9 | t0))
    assert make_dep_tuple_set(TC20) == set([("t1", "t2"), ("t2", "t5"),
                                            ("t3", "t5"), ("t4", "t5"),
                                            ("t5", "t6"), ("t5", "t7"),
                                            ("t5", "t8"), ("t5", "t9"),
                                            ("t9", "t0")])

def test21():
    class TC21(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
        with_dependencies(t1 | t2)
    assert make_dep_tuple_set(TC21) == set([("t1", "t2"), ("t2", "t3")])
    
def test22():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t3, t2 | t3)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test23():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        with_dependencies(TaskGroup(t1, t1 | t2))
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        with_dependencies(t1 | t2)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test24():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2, t3), t1 | t3)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1 | t3, t2))
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test25():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | TaskGroup(t2, t3))
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test26():
    TG = TaskGroup
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies(TG(TG(t1, t2, t3), t4 | t5),
                          t2 | t4,
                          t3 | t5)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
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
    def __init__(self, name, target=None, report=lambda n, o: (n, o), **kwargs):
        super(ReportingTask, self).__init__(name, task_component=target, **kwargs)
        self.target = target
        self.report = report
        
    def get_init_args(self):
        args, kwargs = super(ReportingTask, self).get_init_args()
        try:
            kwargs.pop("task_component")
        except Exception, _:
            pass
        kwargs["target"] = self.target
        kwargs["report"] = self.report
        return args, kwargs
        
    def perform(self):
#         self.report(self.target.name.value(), self.name)
        self.report(self.task_component.name.value(), self.name)


class BogusServerRef(ServerRef):
    def get_admin_ip(self):
        return "8.8.8.8"
    
    admin_ip = property(get_admin_ip)
        

def test27():
    cap = Capture()
        
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        ping_task = ReportingTask("ping", target=PingNamespace.ping_target, report=cap)
        
    cfg = PingConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert cap.performed
    
def test28():
    cap = Capture()
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        t3 = ReportingTask("t3", target=PingNamespace.ping_target, report=cap)
        t2 = ReportingTask("t2", target=PingNamespace.ping_target, report=cap)
        t1 = ReportingTask("t1", target=PingNamespace.ping_target, report=cap)
        with_dependencies(t1 | t2 | t3)
    
    cfg = PingConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (cap.pos("ping_target", PingConfig.t1.name) <
            cap.pos("ping_target", PingConfig.t2.name) <
            cap.pos("ping_target", PingConfig.t3.name) )
        
def test29():
    cap = Capture()
    class PingNamespace(NamespaceSpec):
        ping_target = Component("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigSpec):
        t3 = ReportingTask("t3", target=PingNamespace.ping_target, report=cap)
        t2 = ReportingTask("t2", target=PingNamespace.ping_target, report=cap)
        t1 = ReportingTask("t1", target=PingNamespace.ping_target, report=cap)
        t4 = ReportingTask("t4", target=PingNamespace.ping_target, report=cap)
        t5 = ReportingTask("t5", target=PingNamespace.ping_target, report=cap)
        with_dependencies(t1 | t2 | t3,
                          t4 | t2,
                          t4 | t3,
                          t5 | t3)
    
    cfg = PingConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (cap.pos("ping_target", PingConfig.t1.name) <
            cap.pos("ping_target", PingConfig.t2.name) <
            cap.pos("ping_target", PingConfig.t3.name) and
            cap.performed[-1] == ("ping_target", PingConfig.t3.name) and
            cap.pos("ping_target", PingConfig.t4.name) <
            cap.pos("ping_target", PingConfig.t2.name))
    
def test30():
    cap = Capture()
    class ElasticNamespace(NamespaceSpec):
        ping_targets = NSMultiComponent(Component("ping-target", host_ref=BogusServerRef()))
        pong_targets = NSMultiComponent(Component("pong-target", host_ref=BogusServerRef()))
    ns = ElasticNamespace()
     
    class ElasticConfig(ConfigSpec):
        ping = ReportingTask("ping", target=ElasticNamespace.ping_targets, report=cap)
        pong = ReportingTask("pong", target=ElasticNamespace.pong_targets, report=cap)
        with_dependencies(ping | pong)
         
    for i in range(5):
        _ = ns.ping_targets[i]
         
    cfg = ElasticConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (len(ns.ping_targets) == 5 and
            (set(["0", "1", "2", "3", "4"]) == set(ns.ping_targets.keys())) and
            len(ns.pong_targets) == 0)
            
def test31():
    class VarCapture(_ConfigTask):
        def __init__(self, name, task_component, **kwargs):
            super(VarCapture, self).__init__(name, task_component=task_component, **kwargs)
            self.vars = {}
            
        def perform(self):
            vv = self._model_instance.namespace_model_instance.comp.get_visible_vars()
            self.vars.update({v.name:v.get_value(self.task_component)
                              for v in vv.values()})
        
    class SimpleNS(NamespaceSpec):
        with_variables(Var("ID", "wrong"),
                       Var("ONE", "1"),
                       Var("TWO", "2"),
                       Var("THREE", "3"))
        comp = Component("test-comp", host_ref="!ID!").add_variable(Var("ID", "right!"),
                                                                    Var("THREE", "drei"))
        
    class SimpleCfg(ConfigSpec):
        comp_task = VarCapture("varcap", SimpleNS.comp)
        
    ns = SimpleNS()
    cfg = SimpleCfg()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (cfg.comp_task.vars["ID"] == "right!" and
            cfg.comp_task.vars["THREE"] == "drei" and
            cfg.comp_task.vars["ONE"] == "1" and
            cfg.comp_task.vars["TWO"] == "2")
    
def test32():
    class VarCapture(_ConfigTask):
        def __init__(self, name, task_component, **kwargs):
            super(VarCapture, self).__init__(name, task_component=task_component, **kwargs)
            self.vars = {}
            
        def perform(self):
            vv = self._model_instance.namespace_model_instance.get_visible_vars()
            self.vars.update({v.name:v.get_value(self.task_component)
                              for v in vv.values()})
        
    class SimpleNS(NamespaceSpec):
        with_variables(Var("ID", "wrong"),
                       Var("ONE", "1"),
                       Var("TWO", "2"),
                       Var("THREE", "3"))
        comp = Component("test-comp", host_ref="!ID!").add_variable(Var("ID", "right!"),
                                                                    Var("THREE", "drei"))
        
    class SimpleCfg(ConfigSpec):
        comp_task = VarCapture("varcap", SimpleNS.comp)
        
    ns = SimpleNS()
    cfg = SimpleCfg()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (cfg.comp_task.vars["ID"] == "wrong" and
            cfg.comp_task.vars["THREE"] == "3" and
            cfg.comp_task.vars["ONE"] == "1" and
            cfg.comp_task.vars["TWO"] == "2")
    
def test33():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t2 & t3)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test34():
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | (t2 & t3))
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test35():
    #this is a re-statement of test26 using '&' instead of
    #TasgGroup (TG). It's a pretty literal translation,
    #although algebraically one set of parends isn't needed.
    TG = TaskGroup
    class First(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies((t1 & t2 & t3) & (t4 | t5),
                          t2 | t4,
                          t3 | t5)
        
    class Second(ConfigSpec):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies(t2 | t4 | t5,
                          t3 | t5)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)
    
def test36():
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    cfg.set_namespace(ns)
    cfg.grid_prep._fix_arguments()
    
    assert len(cfg.grid_prep.instances) == 5
    
def test37():
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    _ = ns.grid[0]
    cfg.set_namespace(ns)
    cfg.grid_prep._fix_arguments()
    
    assert (len(cfg.grid_prep.instances) == 1 and
            cfg.grid_prep.instances.value()[0].name == "gp-grid_0")
    
def test38():
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    _ = ns.grid[0]
    cfg.set_namespace(ns)
    cfg.grid_prep._fix_arguments()
    
    assert (len(cfg.grid_prep.instances) == 1 and
            cfg.grid_prep.instances.value()[0].name == "gp-grid_0")

def test39():
    cap = Capture()
             
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
    ns = NS()
         
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert len(cfg.grid_prep.instances) == 5 and len(cap.performed) == 5

def test40():
    cap = Capture()
             
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
        static = Component("static", host_ref="127.0.0.1")
    ns = NS()
         
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.grid)
        before = ReportingTask("before", target=NS.static, report=cap)
        after = ReportingTask("after", target=NS.static, report=cap)
        with_dependencies(before | grid_prep | after)
    cfg = Cfg()
    
    for i in range(3):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert (len(cfg.grid_prep.instances) == 3 and
            len(cap.performed) == 5 and
            (cap.pos("static", "before") < cap.pos("grid_0", "rt-grid_0") and
             cap.pos("static", "before") < cap.pos("grid_1", "rt-grid_1") and
             cap.pos("static", "before") < cap.pos("grid_2", "rt-grid_2") and
             cap.pos("static", "after") > cap.pos("grid_0", "rt-grid_0") and
             cap.pos("static", "after") > cap.pos("grid_1", "rt-grid_1") and
             cap.pos("static", "after") > cap.pos("grid_2", "rt-grid_2")))

def test41():
    cap = Capture()
             
    class NS(NamespaceSpec):
        grid = NSMultiComponent(Component("grid", host_ref="127.0.0.1"))
    ns = NS()
         
    class Cfg(ConfigSpec):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.q.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    ea.perform_config()
    assert len(cfg.grid_prep.instances) == 5 and len(cap.performed) == 5

def do_all():
    setup()
    test37()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
