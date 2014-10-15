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
Created on 7 Jun 2014

@author: tom
'''
from actuator import (Var, NamespaceSpec, with_variables, NamespaceException,
                          Component, with_components, MultiComponent, 
                          MultiComponentGroup, ComponentGroup, ctxt, ActuatorException)
from actuator.namespace import NSComponentGroup, NSMultiComponent, NSMultiComponentGroup
from actuator.infra import InfraSpec
from actuator.provisioners.example_components import Server


def setup():
    pass


def test01():
    from actuator.modeling import _ComputeModelComponents
    class NoCompSource(_ComputeModelComponents):
        pass
    cs = NoCompSource()
    try:
        _ = cs._comp_source()
        assert False, "Non-overridden _comp_source() should have raised"
    except TypeError, e:
        assert "Derived class must implement" in e.message
        
def test02():
    try:
        _ = ComponentGroup("oopsGroup", server=Server("server", mem="8GB"), oops="not me")
        assert False, "Bad arg to ComponentGroup not caught"
    except TypeError, e:
        assert "isn't a kind of AbstractModelingEntity".lower() in e.message.lower()

def test03():
    ce = ctxt.one.two.three
    assert list(ce._path) == ["three", "two", "one"]
    
def test04():
    ce = ctxt.model.infra.grid[0]
    path = list(ce._path[1:])
    ki = ce._path[0]
    assert [ki.key] + path == ["0", "grid", "infra", "model"]
    
def test05():
    class Infra(InfraSpec):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    for i in range(3):
        _ = inst.grid[i]
    assert set(inst.grid) == set(["0", "1", "2"])

def test06():
    class Infra(InfraSpec):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    for i in range(3):
        _ = inst.grid[i]
    nada = "nada"
    assert inst.grid.get("10", default=nada) == nada
    
def test07():
    class Infra(InfraSpec):
        grid = MultiComponent(Server("grid", mem="8GB"))
    inst = Infra("iter")
    assert not inst.grid


def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()
    
