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
Created on 13 Jul 2014
'''

import threading

from actuator import *
from actuator.config import _Dependency, ConfigTask, StructuralTask,\
    with_config_options
from actuator.infra import IPAddressable

MyConfig = None
search_path = ["p1", "p2", "p3"]


def setup():
    global MyConfig
    class MyTestConfig(ConfigModel):
        with_searchpath(*search_path)
        t1 = NullTask("nt")
        t2 = NullTask("temp")
        with_dependencies(t1 | t2)
        
    MyConfig = MyTestConfig
    
    
def make_dep_tuple_set(config):
    return set([(d.from_task.path, d.to_task.path) for d in config.get_class_dependencies()])


def pretty_deps(deps):
    return [("{}-{}".format(d.from_task.name, str(id(d.from_task))[-4:]),
             "{}-{}".format(d.to_task.name, str(id(d.to_task))[-4:]))
            for d in deps]
    
    
def test01():
    assert MyConfig
    
def test02():
    expected_path = set(search_path)
    assert expected_path == set(MyConfig.__searchpath__)
    
def test03():
    assert 1 == len(MyConfig.__dependencies__)
    
def test04():
    try:
        class T4Config(ConfigModel):
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
        class TC8(ConfigModel):
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
    class TC9(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3)
    assert make_dep_tuple_set(TC9) == set([("t1", "t2"), ("t2", "t3")])
        
def test10():
    try:
        class TC10(ConfigModel):
            t1 = NullTask("t1", path="t1")
            t2 = NullTask("t2", path="t2")
            t3 = NullTask("t3", path="t3")
            with_dependencies(t1 | t2 | t3 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test10a():
    try:
        class TC10a(ConfigModel):
            t1 = NullTask("t1", path="t1")
            t2 = NullTask("t2", path="t2")
            t3 = NullTask("t3", path="t3")
            with_dependencies(t1 | t2 | t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def test11():
    try:
        class TC11(ConfigModel):
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
    class TC12(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
    assert make_dep_tuple_set(TC12) == set([("t1", "t3"), ("t2", "t3")])

def test13():
    class TC13(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1, t2 | t3) | t4)
    assert make_dep_tuple_set(TC13) == set([("t2", "t3"), ("t1", "t4"), ("t3", "t4")])

def test14():
    class TC14(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1, t2) | TaskGroup(t3, t4))
    assert make_dep_tuple_set(TC14) == set([("t2", "t3"), ("t1", "t4"),
                                            ("t1", "t3"), ("t2", "t4")])

def test15():
    class TC15(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        with_dependencies(TaskGroup(t1 | t2, t3 | t4))
    assert make_dep_tuple_set(TC15) == set([("t1", "t2"), ("t3", "t4")])

def test16():
    class TC16(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | TaskGroup(t2, t3))
    assert make_dep_tuple_set(TC16) == set([("t1", "t3"), ("t1", "t2")])

def test17():
    class TC17(ConfigModel):
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
    class TC18(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, TaskGroup(t2, TaskGroup(t3))))
    assert make_dep_tuple_set(TC18) == set()

def test19():
    class TC19(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
    assert make_dep_tuple_set(TC19) == set([("t1", "t2"), ("t2", "t3")])

def test20():
    class TC20(ConfigModel):
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
    class TC21(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2)
        with_dependencies(t2 | t3)
        with_dependencies(t1 | t2)
    assert make_dep_tuple_set(TC21) == set([("t1", "t2"), ("t2", "t3")])
    
def test22():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t3, t2 | t3)
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2) | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test23():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        with_dependencies(TaskGroup(t1, t1 | t2))
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        with_dependencies(t1 | t2)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test24():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1, t2, t3), t1 | t3)
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(TaskGroup(t1 | t3, t2))
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test25():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | TaskGroup(t2, t3))
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test26():
    TG = TaskGroup
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies(TG(TG(t1, t2, t3), t4 | t5),
                          t2 | t4,
                          t3 | t5)
        
    class Second(ConfigModel):
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
        
    
class ReportingTask(ConfigTask, StructuralTask):
    def __init__(self, name, target=None, report=lambda n, o: (n, o), **kwargs):
        super(ReportingTask, self).__init__(name, task_role=target, **kwargs)
        self.target = target
        self.report = report
        
    def get_init_args(self):
        args, kwargs = super(ReportingTask, self).get_init_args()
        try:
            kwargs.pop("task_role")
        except Exception, _:
            pass
        kwargs["target"] = self.target
        kwargs["report"] = self.report
        return args, kwargs
        
    def _perform(self, engine):
        comp = self.get_task_role()
        if not isinstance(comp, basestring):
            if isinstance(comp.name, basestring):
                comp = comp.name
            else:
                comp = comp.name.value()
        self.report(comp, self.name)


class BogusServerRef(IPAddressable):
    def get_ip(self):
        return "8.8.8.8"
    
    admin_ip = property(get_ip)
        

def test27():
    cap = Capture()
        
    class PingNamespace(NamespaceModel):
        ping_target = Role("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigModel):
        ping_task = ReportingTask("ping", target=PingNamespace.ping_target, report=cap)
        
    cfg = PingConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert cap.performed
    
def test28():
    cap = Capture()
    class PingNamespace(NamespaceModel):
        ping_target = Role("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigModel):
        t3 = ReportingTask("t3", target=PingNamespace.ping_target, report=cap, repeat_count=1)
        t2 = ReportingTask("t2", target=PingNamespace.ping_target, report=cap, repeat_count=1)
        t1 = ReportingTask("t1", target=PingNamespace.ping_target, report=cap, repeat_count=1)
        with_dependencies(t1 | t2 | t3)
    
    cfg = PingConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    try:
        ea.perform_config()
    except Exception, e:
        print "Unexpected performance failure with: %s" % e.message
        print "problems:"
        import traceback
        for t, et, ev, tb in ea.get_aborted_tasks():
            print ">>>Task %s" % t.name
            traceback.print_exception(et, ev, tb)
        assert False
    assert (cap.pos("ping_target", PingConfig.t1.name) <
            cap.pos("ping_target", PingConfig.t2.name) <
            cap.pos("ping_target", PingConfig.t3.name) )
        
def test29():
    cap = Capture()
    class PingNamespace(NamespaceModel):
        ping_target = Role("ping_target", host_ref=BogusServerRef())
    ns = PingNamespace()
        
    class PingConfig(ConfigModel):
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
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert (cap.pos("ping_target", PingConfig.t1.name) <
            cap.pos("ping_target", PingConfig.t2.name) <
            cap.pos("ping_target", PingConfig.t3.name) and
            cap.performed[-1] == ("ping_target", PingConfig.t3.name) and
            cap.pos("ping_target", PingConfig.t4.name) <
            cap.pos("ping_target", PingConfig.t2.name))
    
def test30():
    cap = Capture()
    class ElasticNamespace(NamespaceModel):
        ping_targets = MultiRole(Role("ping-target", host_ref=BogusServerRef()))
        pong_targets = MultiRole(Role("pong-target", host_ref=BogusServerRef()))
    ns = ElasticNamespace()
     
    class ElasticConfig(ConfigModel):
        ping = ReportingTask("ping", target=ElasticNamespace.ping_targets, report=cap)
        pong = ReportingTask("pong", target=ElasticNamespace.pong_targets, report=cap)
        with_dependencies(ping | pong)
         
    for i in range(5):
        _ = ns.ping_targets[i]
         
    cfg = ElasticConfig()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert (len(ns.ping_targets) == 5 and
            (set(["0", "1", "2", "3", "4"]) == set(ns.ping_targets.keys())) and
            len(ns.pong_targets) == 0)
            
def test31():
    class VarCapture(ConfigTask):
        def __init__(self, name, task_role, **kwargs):
            super(VarCapture, self).__init__(name, task_role=task_role, **kwargs)
            self.vars = {}
            
        def _perform(self, engine):
            vv = self.get_model_instance().namespace_model_instance.comp.get_visible_vars()
            self.vars.update({v.name:v.get_value(self.get_task_role())
                              for v in vv.values()})
        
    class SimpleNS(NamespaceModel):
        with_variables(Var("ID", "wrong"),
                       Var("ONE", "1"),
                       Var("TWO", "2"),
                       Var("THREE", "3"))
        comp = Role("test-comp", host_ref="!{ID}").add_variable(Var("ID", "right!"),
                                                                    Var("THREE", "drei"))
        
    class SimpleCfg(ConfigModel):
        comp_task = VarCapture("varcap", SimpleNS.comp)
        
    ns = SimpleNS()
    cfg = SimpleCfg()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert (cfg.comp_task.vars["ID"] == "right!" and
            cfg.comp_task.vars["THREE"] == "drei" and
            cfg.comp_task.vars["ONE"] == "1" and
            cfg.comp_task.vars["TWO"] == "2")
    
def test32():
    class VarCapture(ConfigTask):
        def __init__(self, name, task_role, **kwargs):
            super(VarCapture, self).__init__(name, task_role=task_role, **kwargs)
            self.vars = {}
            
        def _perform(self, engine):
            vv = self.get_model_instance().namespace_model_instance.get_visible_vars()
            self.vars.update({v.name:v.get_value(self.get_task_role())
                              for v in vv.values()})
        
    class SimpleNS(NamespaceModel):
        with_variables(Var("ID", "wrong"),
                       Var("ONE", "1"),
                       Var("TWO", "2"),
                       Var("THREE", "3"))
        comp = Role("test-comp", host_ref="!{ID}").add_variable(Var("ID", "right!"),
                                                                    Var("THREE", "drei"))
        
    class SimpleCfg(ConfigModel):
        comp_task = VarCapture("varcap", SimpleNS.comp)
        
    ns = SimpleNS()
    cfg = SimpleCfg()
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert (cfg.comp_task.vars["ID"] == "wrong" and
            cfg.comp_task.vars["THREE"] == "3" and
            cfg.comp_task.vars["ONE"] == "1" and
            cfg.comp_task.vars["TWO"] == "2")
    
def test33():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t2 & t3)
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | t3)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)

def test34():
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        with_dependencies(t1 | t2 | t3, t1 | (t2 & t3))
        
    class Second(ConfigModel):
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
    class First(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies((t1 & t2 & t3) & (t4 | t5),
                          t2 | t4,
                          t3 | t5)
        
    class Second(ConfigModel):
        t1 = NullTask("t1", path="t1")
        t2 = NullTask("t2", path="t2")
        t3 = NullTask("t3", path="t3")
        t4 = NullTask("t4", path="t4")
        t5 = NullTask("t5", path="t5")
        with_dependencies(t2 | t4 | t5,
                          t3 | t5)
        
    assert make_dep_tuple_set(First) == make_dep_tuple_set(Second)
    
def test36():
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    cfg.set_namespace(ns)
    cfg.grid_prep.fix_arguments()
    
    assert len(cfg.grid_prep.instances) == 5
    
def test37():
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    _ = ns.grid[0]
    cfg.set_namespace(ns)
    cfg.grid_prep.fix_arguments()
    
    assert (len(cfg.grid_prep.instances) == 1 and
            cfg.grid_prep.instances.value()[0].name == "gp-grid_0")
    
def test38():
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
    ns = NS()
    
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", NullTask("gp", path="gp"), NS.grid)
    cfg = Cfg()
    
    _ = ns.grid[0]
    cfg.set_namespace(ns)
    cfg.grid_prep.fix_arguments()
    
    assert (len(cfg.grid_prep.instances) == 1 and
            cfg.grid_prep.instances.value()[0].name == "gp-grid_0")

def test39():
    cap = Capture()
             
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
    ns = NS()
         
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert len(cfg.grid_prep.instances) == 5 and len(cap.performed) == 5

def test40():
    cap = Capture()
             
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
        static = Role("static", host_ref="127.0.0.1")
    ns = NS()
         
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.grid)
        before = ReportingTask("before", target=NS.static, report=cap)
        after = ReportingTask("after", target=NS.static, report=cap)
        with_dependencies(before | grid_prep | after)
    cfg = Cfg()
    
    for i in range(3):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    try:
        ea.perform_config()
    except Exception, e:
        print "Unexpected exception: %s" % e.message
        print "Aborted tasks:"
        import traceback
        for t, et, ev, tb in ea.get_aborted_tasks():
            print ">>>Task %s" % t.name
            traceback.print_exception(et, ev, tb)
        assert False
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
             
    class NS(NamespaceModel):
        grid = MultiRole(Role("grid", host_ref="127.0.0.1"))
    ns = NS()
         
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.q.grid)
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert len(cfg.grid_prep.instances) == 5 and len(cap.performed) == 5

def test42():
    cap = Capture()
             
    class NS(NamespaceModel):
        grid1 = MultiRole(Role("grid1", host_ref="127.0.0.1"))
        grid2 = MultiRole(Role("grid2", host_ref="127.0.0.1"))
    ns = NS()
         
    class Cfg(ConfigModel):
        grid_prep = MultiTask("grid_prep", ReportingTask("rt", report=cap),
                              NS.q.union(NS.q.grid1, NS.q.grid2))
    cfg = Cfg()
    
    for i in range(5):
        _ = ns.grid1[i]
    for i in range(3):
        _ = ns.grid2[i]
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        no_delay=True)
    ea.perform_config()
    assert len(cfg.grid_prep.instances) == 8 and len(cap.performed) == 8
    
def test43():
    """
    test43: set a default task performance host using the 'default_task_role'
    kwarg of with_config_options(), and then create a task with no task_role.
    create an instance of the config, and see that get_task_host() on the
    config's task returns the role's get_ip address
    """
    cap = Capture()
    
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref="127.0.0.1")
    ns = NS()
        
    class Cfg(ConfigModel):
        with_config_options(default_task_role=NS.task_performer)
        a_task = ReportingTask("atask", report=cap)
    cfg = Cfg()
    cfg.set_namespace(ns)
    
    assert cfg.a_task.get_task_host() == "127.0.0.1"

def test44():
    """
    test44: like test43, but get the task host from a StaticServer in the
    infra model
    """
    cap = Capture()
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
      
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
    ns = NS()
    ns.set_infra_model(infra)
          
    class Cfg(ConfigModel):
        with_config_options(default_task_role=NS.task_performer)
        a_task = ReportingTask("atask", report=cap)
    cfg = Cfg()
    cfg.set_namespace(ns)
      
    assert cfg.a_task.get_task_host() == "127.0.0.1"
    
def test44a():
    """
    test44a: like test44, setting the role on the task instead of getting
    it via the default for the config model
    """
    cap = Capture()
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
    infra.setup_server.fix_arguments()
      
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
    ns = NS()
    ns.set_infra_model(infra)
    ns.task_performer.fix_arguments()
          
    class Cfg(ConfigModel):
        a_task = ReportingTask("atask", report=cap, target=NS.task_performer)
    cfg = Cfg()
    cfg.set_namespace(ns)
    cfg.a_task.fix_arguments()
      
    assert cfg.a_task.get_task_host() == "127.0.0.1"
    
def test45():
    """
    test45: check if you drive config tasks from a nested config class
    """
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
    infra.setup_server.fix_arguments()
    
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
    ns = NS()
    ns.set_infra_model(infra)
    ns.task_performer.fix_arguments()
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        task = ReportingTask("inner_task", report=cap)
        
    class OuterCfg(ConfigModel):
        wrapped_task = ConfigClassTask("wrapper", InnerCfg, task_role=NS.task_performer)
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    assert len(cap.performed) == 1

def test46():
    """
    test46: wrap a config class with a sequence of tasks in ConfigClassTask
    wrapper and ensure they all get performed in order
    """
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
    
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
    ns = NS()
    ns.set_infra_model(infra)
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        t1 = ReportingTask("inner_task1", report=cap)
        t2 = ReportingTask("inner_task2", report=cap)
        t3 = ReportingTask("inner_task3", report=cap)
        with_dependencies(t1 | t2 | t3)
        
    class OuterCfg(ConfigModel):
        wrapped_task = ConfigClassTask("wrapper", InnerCfg, task_role=NS.task_performer)
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    assert (len(cap.performed) == 3 and
            cap.pos("tp", "inner_task1") < cap.pos("tp", "inner_task2") and
            cap.pos("tp", "inner_task2") < cap.pos("tp", "inner_task3"))

def test47():
    """
    test47: wrap a config class with a sequence of tasks in ConfigClassTask
    wrapper, then drive the creation of instances of the ConfigClassTask
    with a MultiTask wrapper.
    """
    class IPGen(object):
        def __init__(self):
            self.host_part = 0
            
        def __call__(self, context):
            self.host_part += 1
            return "127.0.0.{}".format(self.host_part)
    ipgen = IPGen()
        
    class Infra(InfraModel):
        setup_server = MultiResource(StaticServer("setup_helper", ipgen))
    infra = Infra("helper")
    
    class NS(NamespaceModel):
        task_role = MultiRole(Role("tp",
                                   host_ref=ctxt.nexus.inf.setup_server[ctxt.name]))
    ns = NS()
    ns.set_infra_model(infra)
    for i in range(3):
        _ = ns.task_role[i]
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        t1 = ReportingTask("inner_task1", report=cap)
        t2 = ReportingTask("inner_task2", report=cap)
        t3 = ReportingTask("inner_task3", report=cap)
        with_dependencies(t1 | t2 | t3)
        
    class OuterCfg(ConfigModel):
        wrapped_task = MultiTask("setupSuite",
                                 ConfigClassTask("wrapper", InnerCfg),
                                 NS.q.task_role.all())
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    cap.performed.sort(lambda x,y: cmp(x[0], y[0]))
    assert len(cap.performed) == 9

def test48():
    """
    test48: wrap a config class with a sequence of tasks in ConfigClassTask
    wrapper and ensure they all get performed in order, and the set up a final
    task in the outer config class and ensure that is is performed last
    """
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
    
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
        default = Role("default", host_ref="127.0.1.1")
    ns = NS()
    ns.set_infra_model(infra)
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        t1 = ReportingTask("inner_task1", report=cap)
        t2 = ReportingTask("inner_task2", report=cap)
        t3 = ReportingTask("inner_task3", report=cap)
        with_dependencies(t1 | t2 | t3)
        
    class OuterCfg(ConfigModel):
        wrapped_task = ConfigClassTask("wrapper", InnerCfg, task_role=NS.task_performer)
        final = ReportingTask("final", target=NS.default, report=cap)
        with_dependencies(wrapped_task | final)
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    assert (len(cap.performed) == 4 and
            cap.pos("tp", "inner_task1") < cap.pos("tp", "inner_task2") and
            cap.pos("tp", "inner_task2") < cap.pos("tp", "inner_task3") and
            cap.pos("tp", "inner_task3") < cap.pos("default", "final"))

def test49():
    """
    test49: wrap a config class with a sequence of tasks in ConfigClassTask
    wrapper and ensure they all get performed in order, and then set up
    initial and final tasks in the outer config and make sure everything is
    happening in the right order
    """
    class Infra(InfraModel):
        setup_server = StaticServer("setup_helper", "127.0.0.1")
    infra = Infra("helper")
    
    class NS(NamespaceModel):
        task_performer = Role("tp", host_ref=Infra.setup_server)
        default = Role("default", host_ref="127.0.1.1")
    ns = NS()
    ns.set_infra_model(infra)
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        t1 = ReportingTask("inner_task1", report=cap)
        t2 = ReportingTask("inner_task2", report=cap)
        t3 = ReportingTask("inner_task3", report=cap)
        
        with_dependencies(t1 | t2 | t3)
        
    class OuterCfg(ConfigModel):
        wrapped_task = ConfigClassTask("wrapper", InnerCfg, task_role=NS.task_performer)
        initial = ReportingTask("initial", target=NS.default, report=cap)
        final = ReportingTask("final", target=NS.default, report=cap)
        
        with_dependencies(initial | wrapped_task | final)
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    assert (len(cap.performed) == 5 and
            cap.pos("tp", "inner_task1") < cap.pos("tp", "inner_task2") and
            cap.pos("tp", "inner_task2") < cap.pos("tp", "inner_task3") and
            cap.pos("tp", "inner_task3") < cap.pos("default", "final") and
            cap.pos("default", "initial") < cap.pos("tp", "inner_task1"))

def test50():
    """
    test50: wrap a config class with a sequence of tasks in ConfigClassTask
    wrapper, then drive the creation of instances of the ConfigClassTask
    with a MultiTask wrapper.
    """
    class IPGen(object):
        def __init__(self):
            self.host_part = 0
            
        def __call__(self, context):
            self.host_part += 1
            return "127.0.0.{}".format(self.host_part)
    ipgen = IPGen()
        
    class Infra(InfraModel):
        setup_server = MultiResource(StaticServer("setup_helper", ipgen))
    infra = Infra("helper")
    
    class NS(NamespaceModel):
        task_role = MultiRole(Role("tp",
                                   host_ref=ctxt.nexus.inf.setup_server[ctxt.name]))
        default = Role("default", "127.0.1.1")
    ns = NS()
    ns.set_infra_model(infra)
    for i in range(3):
        _ = ns.task_role[i]
    
    cap = Capture()
    class InnerCfg(ConfigModel):
        t1 = ReportingTask("inner_task1", report=cap)
        t2 = ReportingTask("inner_task2", report=cap)
        t3 = ReportingTask("inner_task3", report=cap)
        with_dependencies(t1 | t2 | t3)
        
    class OuterCfg(ConfigModel):
        wrapped_task = MultiTask("setupSuite",
                                 ConfigClassTask("wrapper", InnerCfg),
                                 NS.q.task_role.all())
        initial = ReportingTask("initial", target=NS.default, report=cap)
        final = ReportingTask("final", target=NS.default, report=cap)
        
        with_dependencies(initial | wrapped_task | final)
        
    cfg = OuterCfg()
    cfg.set_namespace(ns)
    
    ea = ExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns,
                        infra_model_instance=infra, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message

    assert (len(cap.performed) == 11 and
            cap.pos("default", "final") == len(cap.performed) -1 and
            cap.pos("default", "initial") == 0)
    
def test51():
    class SkipemNS(NamespaceModel):
        with_variables(Var("ONE", "1"),
                       Var("TWO", "2"),
                       Var("THREE", "!{ONE}+!{TWO}", in_env=False))
        r = Role("me", host_ref="127.0.0.1")
    ns = SkipemNS()
    
    class SkipConfig(ConfigModel):
        t = NullTask("env-test", task_role=SkipemNS.r)
        
    cfg = SkipConfig()
    cfg.set_namespace(ns)
    
    assert "THREE" in cfg.t.task_variables() and "THREE" not in cfg.t.task_variables(for_env=True)
    

def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
