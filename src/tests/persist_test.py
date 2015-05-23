import json
from actuator import (ActuatorOrchestration, InfraModel, ctxt)
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.namespace import NamespaceModel, Role, Var
from actuator.provisioners.example_resources import Server

def persistence_helper(ns_model=None, infra_model=None):
    if ns_model and infra_model:
        infra_model.nexus.merge_from(ns_model.nexus)
    if infra_model is not None:
        for c in infra_model.components():
            c.fix_arguments()
    if ns_model is not None:
        for c in ns_model.components():
            c.fix_arguments()
    orch = ActuatorOrchestration(infra_model_inst=infra_model,
                                 namespace_model_inst=ns_model)
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    o2 = reanimate_from_dict(d)
    return o2

def test13():
    r = Role("wibble")
    d = r.get_attrs_dict()
    d_json = json.dumps(d)
    d = json.loads(d_json)
    assert r.name == "wibble"
    
def test14():
    r = Role("wibble1", variables=[Var("v1", "summat")])
    d = r.get_attrs_dict()
    d_json = json.dumps(d)
    d = json.loads(d_json)
    assert (r.name == "wibble1" and r.get_visible_vars() and
            r.var_value("v1") == "summat")
    

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
