'''
Created on 13 Jul 2014

@author: tom
'''
from actuator import *
from actuator.config import _Dependency

MyConfig = None
search_path = ["p1", "p2", "p3"]


def setup():
    global MyConfig
    class MyTestConfig(ConfigSpec):
        with_searchpath(*search_path)
        t1 = MakeDir()
        t2 = Template()
        with_dependencies(t1 >> t2)
        
    MyConfig = MyTestConfig
    
    
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
            t1 = MakeDir()
            with_dependencies(t1 >> "other")
        raise Exception("Failed to catch dependency creation with non-task")
    except:
        assert True
        
def test05():
    try:
        _ = _Dependency(MakeDir(), "other")
        raise Exception("Failed to catch _Dependency creation with 'to' as non-task")
    except:
        assert True
        
def test06():
    try:
        _ = _Dependency("other", MakeDir())
        raise Exception("Failed to catch _Dependency creation with 'from' as non-task")
    except:
        assert True

def test07():
    assert 2 == len(MyConfig._node_dict_)
    
def test08():
    try:
        class TC8(ConfigSpec):
            t1 = MakeDir()
            t2 = MakeDir()
            t3 = MakeDir()
            with_dependencies(t1 >> t2,
                              t2 >> t3,
                              t3 >> t1)
        assert False, "Cycle in dependencies was not detected"
    except ConfigException, _:
        assert True
        
def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
