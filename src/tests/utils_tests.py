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

@author: tom
'''
from actuator.utils import *

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

