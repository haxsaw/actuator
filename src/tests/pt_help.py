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
from actuator.utils import persist_to_dict, reanimate_from_dict

def persistence_helper(ns_model=None, infra_model=None):
    orch = ActuatorOrchestration(infra_model_inst=infra_model,
                                 namespace_model_inst=ns_model)
    if infra_model is not None and ns_model is not None:
        ns_model.set_infra_model(infra_model)
    if infra_model is not None:
        _ = infra_model.refs_for_components()
        for c in infra_model.components():
            c.fix_arguments()
    if ns_model is not None:
        _ = ns_model.refs_for_components()
        for c in ns_model.components():
            c.fix_arguments()
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    o2 = reanimate_from_dict(d)
    return o2
