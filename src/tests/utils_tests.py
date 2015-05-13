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

import sys
import subprocess
import json

from actuator.utils import *
from actuator.utils import _Persistable, persist_to_dict, reanimate_from_dict
from actuator.infra import InfraModel
from keystoneclient.utils import arg

#class mapping tests setup

dom1 = "dom1"
dom2 = "dom2"

class Dom1Source1(object): pass

class Dom1Source2(object): pass

class Dom2Source1(object): pass

class Dom2Source2(object): pass


@capture_mapping(dom1, Dom1Source1)
class Dom1Target1(object):
    pass

@capture_mapping(dom1, Dom1Source2)
class Dom1Target2(object):
    pass

@capture_mapping(dom2, Dom2Source1)
class Dom2Target1(object):
    pass

@capture_mapping(dom2, Dom2Source2)
class Dom2Target2(object):
    pass


#ClassModifier tests setup
magic_args_attr = "MAGIC_ARGS"
def wif_fings(cls, *args, **kwargs):
    stuff_list = cls.__dict__.get(magic_args_attr)
    if stuff_list is None:
        stuff_list = []
        setattr(cls, magic_args_attr, stuff_list)
    stuff_list.extend(args)
    for k, v in kwargs.items():
        setattr(cls, k, v)
wif_fings = ClassModifier(wif_fings)
    

def test01():
    m = get_mapper(dom1)
    assert m and isinstance(m, dict)
    
def test02():
    m = get_mapper(dom1)
    cls = m[Dom1Source1]
    assert cls is Dom1Target1
    
def test03():
    m = get_mapper(dom2)
    cls = m[Dom2Source2]
    assert cls is Dom2Target2
    
def test04():
    class Bogus(object): pass
    m = get_mapper(dom1)
    try:
        cls = m[Bogus]
        assert False, "should have raised a KeyError"
    except KeyError, _:
        pass
    
def test05():
    class D1T1Derived(Dom1Source1):
        pass
    m = get_mapper(dom1)
    cls = m[D1T1Derived]
    assert cls is Dom1Target1

def test06():
    class Test06(object):
        wif_fings(1, 2, 3)
    process_modifiers(Test06)
    assert hasattr(Test06, magic_args_attr)

def test07():
    class Test07(object):
        wif_fings(1, 2, 3)
    process_modifiers(Test07)
    assert set(Test07.MAGIC_ARGS) == set([1,2,3])

def test08():
    class Test08(object):
        wif_fings(1, 2, 3)
        wif_fings(4, 5)
    process_modifiers(Test08)
    assert set(Test08.MAGIC_ARGS) == set([1,2,3,4,5])

def test09():
    class Test09(object):
        wif_fings(a=1, b=2)
    process_modifiers(Test09)
    assert Test09.a == 1 and Test09.b == 2

def test10():
    class Test10(object):
        wif_fings(a=1, b=2)
        wif_fings(c="c", d=4.3)
    process_modifiers(Test10)
    assert Test10.a == 1 and Test10.b == 2 and Test10.c == "c" and Test10.d == 4.3

def test11():
    class Test11(object):
        wif_fings(a=1, b=2)
        wif_fings(c="c", d=4.3)
        wif_fings(1, 2, 3)
        wif_fings(4, 5)
    process_modifiers(Test11)
    assert (Test11.a == 1 and Test11.b == 2 and Test11.c == "c" and Test11.d == 4.3
            and set(Test11.MAGIC_ARGS) == set([1,2,3,4,5]))

def test12():
    class Test12(object):
        wif_fings(1, 2, 3, 4, 5, a=1, b=2, c="c", d=4.3)
    process_modifiers(Test12)
    assert (Test12.a == 1 and Test12.b == 2 and Test12.c == "c" and Test12.d == 4.3
            and set(Test12.MAGIC_ARGS) == set([1,2,3,4,5]))

def test13():
    '''
    This tests the operation of adb, but does it with a subprocess. look at flagger.py
    '''
    sp = subprocess.Popen([sys.executable, find_file("flagger.py")],
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE)
    sp.stdin.write("c\n")
    returncode = sp.wait()
    assert returncode == 0, "flagger failed!"
    
def test14():
    """
    test14: check the basic operation of the _Persistable class
    """
    p = _Persistable()
    d = p.get_attrs_dict()
    assert _Persistable._class_name in d and _Persistable._class_name in d
    
#for test15
class Mock(_Persistable):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    def _get_attrs_dict(self):
        d = super(Mock, self)._get_attrs_dict()
        d.update( {'x':self.x, 'y':self.y} )
        return d
    
def test15():
    """
    test15: check that deriving a _Persistable class works properly
    """
    m = Mock(22, 33)
    d = m.get_attrs_dict()
    d_json = json.dumps(d)
    d = json.loads(d_json)
    assert (d[Mock._obj]['x'] == 22 and d[Mock._obj]['y'] == 33 and
            d[Mock._class_name] == "Mock" and
            d[Mock._module_name] == Mock.__module__)
    
def test16():
    """
    test16: check that we can recreate an instance that was persisted
    """
    m = Mock(1, 2)
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mprime = reanimate_from_dict(d)
    assert m.x == mprime.x and m.y == mprime.y
    
class Mock2(_Persistable):
    def __init__(self, some_str, obj):
        self.some_str = some_str
        self.obj = obj
        
    def _find_persistables(self):
        if self.obj:
            for p in self.obj.find_persistables():
                yield p
    
    def _get_attrs_dict(self):
        d = super(Mock2, self)._get_attrs_dict()
        d.update( {"some_str":self.some_str,
                   "obj":self.obj} )
        return d
    
    
def test17():
    """
    test17: test a persistable which contains another persistable
    """
    m = Mock2("wibble", Mock(1,2))
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert isinstance(mp.obj, Mock) and mp.obj.x == 1
    
    
class Mock3(_Persistable):
    def __init__(self, some_str, obj_list):
        self.some_str = some_str
        self.obj_list = list(obj_list)
        
    def _get_attrs_dict(self):
        d = super(Mock3, self)._get_attrs_dict()
        d.update({"some_str":self.some_str,
                  "obj_list":self.obj_list})
        return d
    
    def _find_persistables(self):
        for p in [o for o in self.obj_list if isinstance(o, _Persistable)]:
            for q in p.find_persistables():
                yield q
    
        
def test18():
    """
    test18: test a persistable which contains a list of persistables
    """
    m = Mock3("M3", [Mock(1,2), Mock(3,4), Mock(5, 6)])
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert (mp.some_str == "M3" and
            len(mp.obj_list) == 3 and
            mp.obj_list[1].x == 3)
    
def test19():
    """
    test19: persistable with a list of persistables, which contain other persistables
    """
    m = Mock3("M3", [Mock(1,2), Mock2("m2", Mock(3,4))])
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert (mp.some_str == "M3" and
            len(mp.obj_list) == 2 and
            mp.obj_list[1].obj.y == 4)
    
    
class Mock4(_Persistable):
    def __init__(self, num_mocks=None, mock_list=None):
        if num_mocks is not None:
            self.mocks = {i:Mock(i, i+1) for i in range(num_mocks)}
        elif mock_list is not None:
            self.mocks = {i:m for i, m in enumerate(mock_list)}
        
    def _get_attrs_dict(self):
        d = super(Mock4, self)._get_attrs_dict()
        d.update( {"mocks":self.mocks} )
        return d
        
    def _find_persistables(self):
        for m in self.mocks.values():
            for p in m.find_persistables():
                yield p
                
    def finalize_reanimate(self):
        for k in list(self.mocks.keys()):
            self.mocks[int(k)] = self.mocks[k]
            del self.mocks[k]
                

def test20():
    """
    test20: persistable with a dict of persistables
    """
    m = Mock4(num_mocks=10)
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert (len(mp.mocks) == 10 and
            mp.mocks[0].x == 0 and
            mp.mocks[9].x == 9)
    
def test21():
    """
    test21: persistable with a dict of persisteables with other nested persistables
    """
    m = Mock4(mock_list=[Mock2("m2", Mock(99, 100)),
                         Mock3("m3", [Mock2("innerm2", Mock(2, 3))])])
    d = persist_to_dict(m, "mock4")
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert (isinstance(mp, Mock4) and
            len(mp.mocks) == 2 and
            mp.mocks[0].obj.x == 99
            and mp.mocks[1].obj_list[0].obj.y == 3)
    
    
class Mock5(_Persistable):
    def __init__(self, arg):
        self.my_obj = Mock(99, 100)
        self.arg = arg
        
    def set_arg(self, arg):
        self.arg = arg
    
    def _find_persistables(self):
        if self.my_obj:
            for p in self.my_obj.find_persistables():
                yield p
        
    def _get_attrs_dict(self):
        d = super(Mock5, self)._get_attrs_dict()
        d.update( {"arg":self.arg,
                   "my_obj":self.my_obj} )
        return d
        
        
def test22():
    """
    test22: ensure ref to an arg that is persisted ties back out
    """
    m = Mock5(None)
    m.set_arg(m.my_obj)
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert mp.my_obj is mp.arg
     
def test23():
    """
    test23: ensure that a ref arg that is None reanimates to None
    """
    m = Mock5(None)
    d = persist_to_dict(m)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    mp = reanimate_from_dict(d)
    assert mp.arg is None
     
def test24():
    """
    test24: ensure that a missing persistable arg doesn't cause a problem
    """
    m = Mock5(Mock(1,2))
    m2 = Mock3("m2 in t24", [m, m.arg])
    m.my_obj = None
    d = persist_to_dict(m2)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    m2p = reanimate_from_dict(d)
    assert (m2p.obj_list[0].my_obj is None and
            m2p.obj_list[0].arg is m2p.obj_list[1])
     
def test25():
    """
    test25: ensure that cycles of persistables from find_persistables() don't cause a problem
    """
    m3 = Mock3("m3-cycle", [])
    m2 = Mock2("m2-cycle", m3)
    m3.obj_list.append(m2)
    d = persist_to_dict(m3)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    m3p = reanimate_from_dict(d)
    assert m3p.obj_list[0].obj is m3p
     
def test26():
    """
    test26: a different cycle test
    """
    m1 = Mock2("m1", None)
    m2 = Mock2("m2", m1)
    m3 = Mock2("m3", m2)
    m1.obj = m3
    d = persist_to_dict(m1)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    m1p = reanimate_from_dict(d)
    assert m1.obj.obj.obj is m1
    
def test27():
    """
    test27: ensuring that duplicated objects don't signal a cycle
    """
    m1 = Mock(5, 6)
    m3 = Mock3("m3", [m1, m1])
    d = persist_to_dict(m3)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    m3p = reanimate_from_dict(d)
    assert (m3p.obj_list[0] is m3p.obj_list[1] and
            m3p.obj_list[0].x == 5)
    
class Mock6(Mock3):
    def __init__(self, some_str, obj_list, anudder_obj):
        super(Mock6, self).__init__(some_str, obj_list)
        self.anudder_obj = anudder_obj
        
    def _find_persistables(self):
        for p in super(Mock6, self)._find_persistables():
            yield p
        if self.anudder_obj:
            for p in self.anudder_obj.find_persistables():
                yield p
                
    def _get_attrs_dict(self):
        d = super(Mock6, self)._get_attrs_dict()
        d.update( {"anudder_obj":self.anudder_obj} )
        return d
    
def test28():
    """
    test28: testing proper behaviour with _Persistable inheritance
    """
    m2 = Mock2("m2", Mock(33, 44))
    m6 = Mock6("m6", [Mock(1,2), Mock(2,3), m2], Mock5(m2))
    
    d = persist_to_dict(m6)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    m6p = reanimate_from_dict(d)
    assert (isinstance(m6p, Mock6) and
            isinstance(m6p.anudder_obj, Mock5) and
            isinstance(m6p.obj_list[0], Mock) and
            isinstance(m6p.anudder_obj.arg, Mock2))
    
    
#need to be able to detect that we have a persistable dict that won't reload
#need to add a generator on _CatalogEntry() that yields each contained
#_PersistableRef, and then in persist_to_dict() we need to iterate over the
#catalog and use the iterator on _CatalogEntry to check that every _PersistableRef
#is in the catalog. Perhaps the action to take can be selectable, and perhaps
#we can also make selectable the action to take if we can't find an id in the
#catalog that there's a ref to
    
        
    
def do_all():
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()

    
