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
from actuator import ctxt
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.namespace import Role, Var
from actuator.config import Task, TaskGroup
from actuator.provisioners.example_resources import Server
from pt_help import persistence_helper
from actuator.task import _Dependency

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

def test06():
    """
    test06: TaskGroup with serial and parallel tasks
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

def test07():
    """
    test07: TaskGroup with parallel and serial tasks
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
    
def test08():
    """
    test08: TaskGroup with repeated tasks
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
    
def test09():
    """
    test09: TaskGroup with dependency cycle; this shouldn't be possible
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

def test10():
    """
    test10: Complex task group with loads o' tasks
    """
    for i in range(1, 11):
        exec "t%d = Task('t%d')" % (i, i)
    tg = TaskGroup(t1 | (t2 & (t3 | t4)),
                   t3 | ((t5 | t6) & t7),
                   (t6 & t8) | (t9 & t10))
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

def test13():
    r = Role("wibble")
    d = persist_to_dict(r)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    rp = reanimate_from_dict(d)
    assert rp.name == "wibble"
    
def test14():
    r = Role("wibble1", variables=[Var("v1", "summat")])
    d = persist_to_dict(r)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    rp = reanimate_from_dict(d)
    assert (rp.name == "wibble1" and rp.get_visible_vars() and
            rp.var_value("v1") == "summat")
    

def do_all():
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
