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
from actuator import ActuatorOrchestration
from actuator import InfraModel
from actuator.provisioners.example_resources import Server
from actuator.utils import persist_to_dict, reanimate_from_dict


def test01():
    orch = ActuatorOrchestration()
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    assert op
    
    
class Infra1(InfraModel):
    pass
    
    
def test02():
    orch = ActuatorOrchestration(infra_model_inst=Infra1("t2"))
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    assert (hasattr(op, "infra_model_inst") and
            orch.infra_model_inst.name == op.infra_model_inst.name and
            orch.infra_model_inst.nexus is not op.infra_model_inst.nexus and 
            op.infra_model_inst.nexus is not None and
            op.infra_model_inst.nexus.find_instance(Infra1) is op.infra_model_inst)
    
class Infra2(InfraModel):
    s = Server("s1", mem="8GB")
    
def test03():
    i0 = Infra2("test3")
    orch = ActuatorOrchestration(infra_model_inst=i0)
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    assert (hasattr(op.infra_model_inst, "s") and
            op.infra_model_inst.s.name.value() == i0.s.name.value() and
            op.infra_model_inst.s.mem.value() == i0.s.mem.value())
    

def do_all():
    test02()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
    
if __name__ == "__main__":
    do_all()

