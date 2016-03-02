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
from itertools import chain
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.namespace import Role, Var, NamespaceModel, MultiRole
from actuator.task import TaskGroup
from actuator.config import (Task, ConfigTask, ConfigModel, MultiTask,
                             with_dependencies, ConfigClassTask)
from actuator.task import _Dependency

def pdeps(deps):
    """
    Debug helper; prints out dependencies in a sane format
    """
    for d in deps:
        print "%s:%s (%s) -> %s:%s (%s)" % (d.from_task.name, d.from_task.__class__.__name__,
                                            str(d.from_task._id)[:4],
                                            d.to_task.name, d.to_task.__class__.__name__,
                                            str(d.to_task._id)[:4])

def test01():
    """
    test01: test that a base task can persist/reanimate
    """
    t = Task("test1", repeat_til_success=False, repeat_count=5, repeat_interval=2)
    t.fix_arguments()
    d = persist_to_dict(t)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tp = reanimate_from_dict(d)
    assert (tp.name == "test1" and
            tp.repeat_til_success == False and
            tp.repeat_count == 5 and
            tp.repeat_interval == 2)
    
def test02():
    """
    test02: check if TaskGroups persist/reanimate
    """
    t1 = Task("t1")
    t2 = Task("t2")
    tg = TaskGroup(t1, t2)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    names = set([t.name for t in tgp.args])
    assert (len(tgp.args) == 2 and
            "t1" in names and
            "t2" in names and
            tgp.args[0].name == "t1")
    
def test03():
    """
    test03: check if TaskGroups with a dependency can persist/reanimate
    """
    t1 = Task("t1")
    t2 = Task("t2")
    tg = TaskGroup(t1 | t2)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    assert (len(tgp.args) == 1 and
            isinstance(tgp.args[0], _Dependency) and
            tgp.args[0].from_task.name == "t1" and
            tgp.args[0].to_task.name == "t2")
    
def test04():
    """
    test04: check more complex TaskGroups to ensure dependencies are reanimated
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1, t2 | t3)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    assert (len(tgp.args) == 2 and
            len(tgp.unpack()) == 1 and
            tgp.args[0].name == "t1" and
            tgp.args[1].from_task.name == "t2" and
            tgp.args[1].to_task.name == "t3")
    
def test05():
    """
    test05: more complex TaskGroup reanimations
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1, t2 | t3, t1 | t3)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    assert (len(tgp.args) == 3 and
            len(tgp.unpack()) == 2 and
            tgp.args[0].name == "t1" and
            tgp.args[1].from_task.name == "t2" and
            tgp.args[1].to_task.name == "t3" and
            tgp.args[2].from_task.name == "t1" and
            tgp.args[2].to_task.name == "t3")

def test06():
    """
    test06: TaskGroup with no dependencies
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1, t2, t3)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    assert (len(tgp.args) == 3 and
            len(tgp.unpack()) == 0 and
            tgp.args[0].name == "t1" and
            tgp.args[1].name == "t2" and
            tgp.args[2].name == "t3")

def test07():
    """
    test07: TaskGroup with serial and parallel tasks
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1 | (t2 & t3))
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    unpacked = tgp.unpack()
    assert (len(tgp.args) == 1 and
            len(unpacked) == 2 and
            unpacked[0].from_task.name == "t1" and
            unpacked[1].from_task.name == "t1" and
            unpacked[0].to_task.name == "t2" and
            unpacked[1].to_task.name == "t3")

def test08():
    """
    test08: TaskGroup with parallel and serial tasks
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1 & (t2 | t3))
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    unpacked = tgp.unpack()
    assert (len(tgp.args) == 1 and
            len(unpacked) == 1 and
            unpacked[0].from_task.name == "t2" and
            unpacked[0].to_task.name == "t3" and
            tgp.args[0].args[0].name == "t1" and
            isinstance(tgp.args[0].args[1], _Dependency))
    
def test09():
    """
    test09: TaskGroup with repeated tasks
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1 | t2, t1 | t3)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    unpacked = tgp.unpack()
    assert (len(tgp.args) == 2 and
            len(unpacked) == 2 and
            unpacked[0].from_task.name == "t1" and
            unpacked[1].from_task.name == "t1" and
            unpacked[0].to_task.name == "t2" and
            unpacked[1].to_task.name == "t3")
    
def test10():
    """
    test10: TaskGroup with dependency cycle; this shouldn't be possible
    """
    t1 = Task("t1")
    t2 = Task("t2")
    t3 = Task("t3")
    tg = TaskGroup(t1 | t2 | t3 | t1)
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    unpacked = tgp.unpack()
    assert (len(tgp.args) == 1 and
            len(unpacked) == 3 and
            unpacked[0].from_task.name == "t1" and
            unpacked[0].to_task.name == "t2" and
            unpacked[1].from_task.name == "t2" and
            unpacked[1].to_task.name == "t3" and
            unpacked[2].from_task.name == "t3" and
            unpacked[2].to_task.name == "t1")

def test11():
    """
    test11: Complex task group with loads o' tasks
    """
    for i in range(1, 11):
        exec "t%d = Task('t%d')" % (i, i)
    tg = TaskGroup(t1 | (t2 & (t3 | t4)),  # @UndefinedVariable
                   t3 | ((t5 | t6) & t7),  # @UndefinedVariable
                   (t6 & t8) | (t9 & t10))  # @UndefinedVariable
    d = persist_to_dict(tg)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    tgp = reanimate_from_dict(d)
    unpacked = tgp.unpack()
    assert (len(unpacked) == 10 and
            set([(d.from_task.name, d.to_task.name) for d in unpacked]) ==
            set([("t1", "t2"), ("t1", "t3"), ("t3", "t4"),
                 ("t3", "t5"), ("t3", "t7"), ("t5", "t6"),
                 ("t6", "t9"), ("t6", "t10"), ("t8", "t9"),
                 ("t8", "t10")]))

class CTNamespace(NamespaceModel):
    r1 = Role("r1")
    r2 = Role("r2")

def test12():
    """
    test12: try persisting/reanimating a ConfigTask
    """
    ct = ConfigTask("ct11", task_role=CTNamespace.r1, run_from=CTNamespace.r2,
                    remote_user="willie", remote_pass="notonyourlife",
                    private_key_file="somepath", repeat_til_success=False,
                    repeat_count=5, repeat_interval=14)
    ct.fix_arguments()
    d = persist_to_dict(ct)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    ctp = reanimate_from_dict(d)
    assert (ctp.remote_user == "willie" and
            ctp.remote_pass == "notonyourlife" and
            ctp.task_role == CTNamespace.r1 and
            ctp.run_from == CTNamespace.r2 and
            ctp.private_key_file == "somepath" and
            ctp.repeat_til_success == False and
            ctp.repeat_count == 5 and
            ctp.repeat_interval == 14)
    
class CC13(ConfigModel):
    ct = ConfigTask("ct13", task_role=CTNamespace.r1, run_from=CTNamespace.r2,
                    remote_user="willie", remote_pass="notonyourlife",
                    private_key_file="somepath", repeat_til_success=False,
                    repeat_count=5, repeat_interval=14)
    
def test13():
    """
    test13: try persisting/reanimating a config class; initial test
    """
    conf = CC13()
    ns = CTNamespace()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    assert (hasattr(cp, "ct") and
            len(conf.get_tasks()) == len(cp.get_tasks()) and
            hasattr(cp, "namespace_model_instance") and
            len(conf.get_dependencies()) == len(cp.get_dependencies()) and
            cp.ct.task_role.name.value() == "r1")

def test14():
    """
    test14: try persisting a single Role
    """
    r = Role("wibble")
    d = persist_to_dict(r)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    rp = reanimate_from_dict(d)
    assert rp.name == "wibble"
    
def test15():
    """
    test15: persist a Role with Vars and make sure they come back properly
    """
    r = Role("wibble1", variables=[Var("v1", "summat")])
    d = persist_to_dict(r)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    rp = reanimate_from_dict(d)
    assert (rp.name == "wibble1" and rp.get_visible_vars() and
            rp.var_value("v1") == "summat")

class NS16(NamespaceModel):
    grid = MultiRole(Role("node"))
    def gen_nodes(self, num):
        return [self.grid[i] for i in range(num)]
    
class CC16(ConfigModel):
    conf = MultiTask("node_fixer",
                     ConfigTask("fixer"),
                     NS16.q.grid.all(),
                     run_from="me")

def test16():
    """
    test16: persist a config model with a MultiTask
    """
    conf = CC16()
    ns = NS16()
    ns.gen_nodes(5)
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    assert (len(cp.conf) == 5 and len(cp.conf.dependencies) == 10 and
            cp.conf.value().instances[0] is not conf.conf.value().instances[0] and
            len(conf.get_graph().nodes()) == len(cp.get_graph().nodes()) and
            len(conf.get_graph().edges()) == len(cp.get_graph().edges()) and
            len(conf.get_graph().nodes()) != 0 and len(conf.get_graph().edges()) != 0 and
            cp.nexus.ns is not None)
    
class NS17(NamespaceModel):
    r1 = Role("r1")

class CC17(ConfigModel):
    t1 = ConfigTask("t1", task_role=NS17.r1)
    t2 = ConfigTask("t2", task_role=NS17.r1)
    with_dependencies(t1 | t2)
    
def test17():
    """
    test17: persist a config model with dependencies & check they are correct upon reanimation
    """
    conf = CC17()
    ns = NS17()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    assert (len(cp.dependencies) == 1 and
            cp.dependencies[0].from_task is cp.t1.value() and
            cp.dependencies[0].to_task is cp.t2.value())
            
class NS18(NamespaceModel):
    r1 = Role("r1")
    
class CC18(ConfigModel):
    t1 = ConfigTask("t1", task_role=NS18.r1)
    t2 = ConfigTask("t2", task_role=NS18.r1)
    t3 = ConfigTask("t3", task_role=NS18.r1)
    with_dependencies(t1 | t2 | t3)
    
def test18():
    """
    test18: test reanimating more complex dependencies
    """
    conf = CC18()
    ns = NS18()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    deps = cp.get_dependencies()
    assert (len(deps) == 2 and
            deps[0].from_task is cp.t1.value() and
            deps[0].to_task is cp.t2.value() and
            deps[1].from_task is cp.t2.value() and
            deps[1].to_task is cp.t3.value())
    
class NS19(NamespaceModel):
    r1 = Role("r1")
    
class CC19(ConfigModel):
    t1 = ConfigTask("t1", task_role=NS19.r1)
    t2 = ConfigTask("t2", task_role=NS19.r1)
    t3 = ConfigTask("t3", task_role=NS19.r1)
    with_dependencies(t1 | (t2 & t3))

def test19():
    """
    test19: test reanimating more complex dependencies
    """
    conf = CC19()
    ns = NS19()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    deps = cp.get_dependencies()
    assert (len(deps) == 2 and
            deps[0].from_task is cp.t1.value() and
            deps[0].to_task is cp.t2.value() and
            deps[1].from_task is cp.t1.value() and
            deps[1].to_task is cp.t3.value())
    
class NS20(NamespaceModel):
    r = Role("r")
    
class NodeConf20(ConfigModel):
    t1 = ConfigTask("t1",)
    t2 = ConfigTask("t2",)
    t3 = ConfigTask("t3",)
    with_dependencies(t1 | (t2 & t3))
    
class CC20(ConfigModel):
    t0 = ConfigClassTask("t0", NodeConf20, task_role=NS20.r)
    
def test20():
    """
    test20: test ConfigClassTask reanimation where the inner model has dependencies
    """
    conf = CC20()
    ns = NS20()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    deps = cp.get_dependencies()
    assert len(deps) == 5
    
class NS21(NamespaceModel):
    r = Role("r")
    
class NodeConf21(ConfigModel):
    t1 = ConfigTask("t1",)
    t2 = ConfigTask("t2",)
    t3 = ConfigTask("t3",)
    with_dependencies(t1 | t3, t2 | t3)
    
class CC21(ConfigModel):
    t0 = ConfigClassTask("t0", NodeConf21, task_role=NS21.r)
    
def test21():
    """
    test21: test ConfigClassTask reanimation where there a multiple entry tasks
    """
    conf = CC21()
    ns = NS21()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    deps = cp.get_dependencies()
    deps.sort(lambda x, y: cmp((x.from_task.name, x.to_task.name), (y.from_task.name, y.to_task.name)))
    assert (len(deps) == 5 and
            deps[0].from_task is cp.t0.value() and
            deps[0].to_task is cp.t0.instance.t1.value() and
            deps[1].from_task is cp.t0.value() and
            deps[1].to_task is cp.t0.instance.t2.value() and
            deps[2].from_task is cp.t0.instance.t1.value() and
            deps[2].to_task is cp.t0.instance.t3.value() and
            deps[3].from_task is cp.t0.instance.t2.value() and
            deps[3].to_task is cp.t0.instance.t3.value())
    
class NS22(NamespaceModel):
    r = Role("r")
    slaves = MultiRole(Role("slave"))
    def grow_slaves(self, num):
        return [self.slaves[i] for i in range(num)]
    
class SlaveConf22(ConfigModel):
    t1 = ConfigTask("t1")
    t2 = ConfigTask("t2")
    t3 = ConfigTask("t3")
    with_dependencies( (t1 & t2) | t3 )
    
class GridConf22(ConfigModel):
    t01 = ConfigTask("t01", task_role=NS22.r)
    t02 = MultiTask("t02", ConfigClassTask("t02-a", SlaveConf22),
                    NS22.q.slaves.all())
    t03 = ConfigTask("t03", task_role=NS22.r)
    with_dependencies(t01 | t02 | t03)
    
def test22():
    """
    test22: test ConfigClassTask reanimation inside a MultiTask
    """
    conf = GridConf22()
    ns = NS22()
    conf.set_namespace(ns)
    ns.grow_slaves(2)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    deps = cp.get_dependencies()
    deps.sort(lambda x, y: cmp((x.from_task.name, x.to_task.name), (y.from_task.name, y.to_task.name)))
    assert len(deps) == 16
    
    
class NS23(NamespaceModel):
    slaves = MultiRole(Role("slave"))


class Conf23(ConfigModel):
    t1 = ConfigTask("t01", task_role=NS23.slaves["r1"])
    
    
def test23():
    """
    test23: trying to break the use of of keyed references
    """
    conf = Conf23()
    ns = NS23()
    conf.set_namespace(ns)
    for c in chain(ns.components(), conf.components()):
        c.fix_arguments()
    d = persist_to_dict(conf)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    cp = reanimate_from_dict(d)
    obj = conf
    for a in ["t1", "task_role", "value"]:
        obj = getattr(obj, a)
    assert obj()
    assert conf.t1.task_role.name.value() == 'slave_r1'
    assert isinstance(cp, ConfigModel)
    obj = cp
    for a in ["t1", "task_role", "value"]:
        obj = getattr(obj, a)
    assert obj()
    assert cp.t1.task_role.name.value() == 'slave_r1'
    
    
def do_all():
    test23()
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
