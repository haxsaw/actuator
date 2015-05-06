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

from actuator.utils import *
from actuator.utils import _Persistable, _reanimator

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
    assert (d[Mock._obj]['x'] == 22 and d[Mock._obj]['y'] == 33 and
            d[Mock._class_name] == "Mock" and
            d[Mock._module_name] == Mock.__module__)
    
def test16():
    """
    test16: check that we can recreate an instance that was persisted
    """
    m = Mock(1, 2)
    d = m.get_attrs_dict()
    mprime = _reanimator(d)
    assert m.x == mprime.x and m.y == mprime.y
    
class Mock2(_Persistable):
    def __init__(self, some_str, obj):
        self.some_str = some_str
        self.obj = obj
    
    def _get_attrs_dict(self):
        d = super(Mock2, self)._get_attrs_dict()
        d.update( {"some_str":self.some_str,
                "obj":self.obj} )
        return d
    
    def recover_attr_value(self, k, v):
        return (_reanimator(v)
                if self.persisted_persistable(v)
                else v)
    
def test17():
    m = Mock2("wibble", Mock(1,2))
    d = m.get_attrs_dict()
    mp = _reanimator(d)
    assert isinstance(mp.obj, Mock) and mp.obj.x == 1
    
class Mock3(_Persistable):
    def __init__(self, some_str, obj_list):
        self.some_str = some_str
        self.obj_list = list(obj_list)
        
    def _get_attrs_dict(self):
        d = super(Mock3, self)._get_attrs_dict()
        d.update({"some_str":self.some_str,
                  "obj_list":[(o.get_attrs_dict()
                               if isinstance(o, _Persistable)
                               else o) for o in self.obj_list]})
        return d
    
    def recover_attr_value(self, k, v):
        if k == "obj_list":
            return [(_reanimator(d)
                     if self.persisted_persistable(d)
                     else d) for d in v]
        else:
            return v
    
def test18():
    m = Mock3("M3", [Mock(1,2), Mock(3,4), Mock(5, 6)])
    d = m.get_attrs_dict()
    mp = _reanimator(d)
    assert (mp.some_str == "M3" and
            len(mp.obj_list) == 3 and
            mp.obj_list[1].x == 3)
    
def test19():
    m = Mock3("M3", [Mock(1,2), Mock2("m2", Mock(3,4))])
    d = m.get_attrs_dict()
    mp = _reanimator(d)
    assert (mp.some_str == "M3" and
            len(mp.obj_list) == 2 and
            mp.obj_list[1].obj.y == 4)
    
#modeling.KeyAsAttr is going to not come back properly unless
#something is done to flag that these are objects and not just
#numeric strings.
    
    
def do_all():
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()

    
