import sys
import os.path
import time
import random
import json
from actuator import (Role, MultiRole, with_variables, NamespaceModel, Var, ActuatorException,
                      InfraModel)
from actuator.task import Task, TaskExecControl
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.provisioners.azure import azure_class_factory
from actuator.provisioners.openstack import OpenStackProvisionerProxy

here, f = os.path.split(__file__)
runner_dir = os.path.join(here, "..", "scripts")
sys.path.append(runner_dir)
del f

from runner import (process_vars, OrchestrationEventPayload, ActuatorEvent, EngineEventPayload,
                    TaskEventPayload, process_proxies, process_models, ModelProcessor,
                    RunnerEventManager)


def mock_azure_creds_factory(subscription_id=None, client_id=None, secret=None, tenant=None):
    return {"subscription_id": subscription_id,
            "client_id": client_id,
            "secret": secret,
            "tenant": tenant}


real_azure_creds_func = None


dynamic_module_dir = os.path.join(here, "dmods")


def setup_module():
    global real_azure_creds_func
    real_azure_creds_func = azure_class_factory._real_get_azure_credentials
    azure_class_factory._real_get_azure_credentials = mock_azure_creds_factory

    if os.path.exists(dynamic_module_dir):
        for f in os.listdir(dynamic_module_dir):
            if os.path.isfile(os.path.join(dynamic_module_dir, f)):
                os.remove(os.path.join(dynamic_module_dir, f))


def teardown_module():
    azure_class_factory._real_get_azure_credentials = real_azure_creds_func


def test001():
    """
    test001: check that process_vars works properly
    """
    class NS(NamespaceModel):
        with_variables(Var("OUTER", "yep"))
        r = Role("r", variables=[Var("INNER", "inner")], host_ref="127.0.0.1")
        mr = MultiRole(Role("slave",
                            host_ref="127.0.0.1",
                            variables=[Var("SLAVE_VAR", "node")]))

    ns = NS("wibble")
    ns.mr[1]
    process_vars(ns, [{"varpath": [],
                       "name": "OUTER",
                       "value": "nope"},
                      {"varpath": ["r"],
                       "name": "INNER",
                       "value": "wibble",
                       "isoverride": True},
                      {"varpath": ["mr", "1"],
                       "name": "SLAVE_VAR",
                       "value": "blah"}])
    assert ns.var_value("OUTER") == "nope", "OUTER IS '{}'".format(ns.var_value("OUTER"))
    assert ns.r.var_value("INNER") == "wibble", "INNER IS '{}'".format(ns.r.var_value("INNER"))
    assert ns.mr[1].var_value("SLAVE_VAR") == "blah", "SLAVE_VAR is '{}'".format(ns.mr[1].var_value("SLAVE_VAR"))


def test002():
    """
    test002: test creating and accessing data in an orchestration payload
    """
    op = OrchestrationEventPayload(44)
    assert op.orchestration_id() == 44


def test003():
    """
    test003: test creating and accessing engine payload
    """
    ep = EngineEventPayload("wibble", 2354)
    assert ep.model_id() == '2354'
    assert ep.model_name() == "wibble"


def test004():
    """
    test004: test adding a node to the engine payload
    """
    ep = EngineEventPayload("test004", 567)
    t = Task("task004")
    t.performance_status = TaskExecControl.PERFORMING
    ep.add_task_node(t)
    tasks = ep.graph_nodes()
    assert len(tasks) == 1, "there are {} tasks".format(len(tasks))
    tp = tasks[0]
    assert tp["task_name"] == "task004"
    assert tp["task_type"] == str(type(t))
    assert tp["task_id"] == str(t._id)
    assert tp["task_status"] == TaskExecControl.PERFORMING


def test005():
    """
    test005: add a set of nodes
    """
    ep = EngineEventPayload("test005", 1024)
    for i in range(5):
        t = Task("task{}".format(i))
        t.performance_status = TaskExecControl.FAIL_FINAL
        ep.add_task_node(t)
    tasks = ep.graph_nodes()
    assert len(tasks) == 5
    tp = tasks[-1]
    assert tp["task_name"] == 'task4'
    assert tp["task_type"] == str(type(t))
    assert tp["task_id"] == str(t._id)
    assert tp["task_status"] == TaskExecControl.FAIL_FINAL


def test006():
    """
    test006: add an edge
    """
    ft = Task("from")
    ft.performance_status = TaskExecControl.UNPERFORMED
    tt = Task("to")
    tt.performance_status = TaskExecControl.UNPERFORMED
    ep = EngineEventPayload("test006", 2048)
    ep.add_task_edge(ft, tt)
    edges = ep.graph_edges()
    assert len(edges) == 1
    ftp = edges[0][0]
    ttp = edges[0][1]
    assert ftp == str(ft._id), "ftp: {}, ft._id: {}".format(ftp, ft._id)
    assert ttp == str(tt._id)


def test007():
    """
    test007: create and read a task event
    """
    t = Task('test007')
    t.performance_status = TaskExecControl.PERFORMING
    tp = TaskEventPayload(1234, t)
    assert tp.task_id() == str(t._id)
    assert tp.task_action() == TaskExecControl.PERFORMING
    assert tp.task_action() - time.time() < 1
    assert tp.model_id() == '1234'
    assert tp.errtext() == []


def test008():
    """
    test008: create an overall event and orch payload, save/restore to/from JSON
    """
    op = OrchestrationEventPayload(2345)
    ae = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_START, op)
    jstr = ae.to_json()
    ne = ActuatorEvent.from_json(jstr)
    ev = ne.event()
    assert isinstance(ev, OrchestrationEventPayload)
    assert ev.orchestration_id() == op.orchestration_id()
    assert ae.event_class() == ne.event_class()


def test009():
    """
    test009: create an overall event and an engine payload, save/restore to/from JSON
    """
    ee = EngineEventPayload("test009", 1234)
    all_tasks = []
    for i in range(10):
        t = Task("task{}".format(i))
        t.performance_status = TaskExecControl.PERFORMING
        all_tasks.append(t)
        ee.add_task_node(t)
    all_edges = []
    for i in range(8):
        all_edges.append((random.choice(all_tasks),
                         random.choice(all_tasks)))
        ee.add_task_edge(all_edges[-1][0], all_edges[-1][1])
    ae = ActuatorEvent(ActuatorEvent.eng_event, ActuatorEvent.E_START, ee)
    jstr = ae.to_json()
    nae = ActuatorEvent.from_json(jstr)
    nee = nae.event()
    assert type(nee) == EngineEventPayload, "recreated payload type is {}".format(type(nee))
    assert len(nae.event().graph_nodes()) == 10
    assert len(nae.event().graph_edges()) == 8
    assert nae.event().graph_edges()[-1] == [str(t._id) for t in all_edges[-1]]


def test010():
    """
    test010: check that AWS proxies are created properly
    """
    d = {"kind": "aws",
         "args": {
            "positional": ("test010",),
             "keyword": {'default_region': "reg1",
                         'aws_access_key': "the key",
                         'aws_secret_access_key': "the secret key"}
            }
        }
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == AWSProvisionerProxy


def test011():
    """
    test011: check that Azure proxies are created properly
    """
    d = {"kind": "az",
         "args": {
             "positional": ["test011"],
             "keyword": {
                 "subscription_id": "subid",
                 "client_id": "cliid",
                 "secret": "the secret",
                 "tenant": "tenant"
             }
         }
        }
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == AzureProvisionerProxy


def test012():
    """
    test012: create that openstack proxies are created properly.
    """
    d = {"kind": "os",
         "args": {
             "positional": ["test012"],
             "keyword": {
                 "config_files": ["file1"]
             }
          }
         }
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == OpenStackProvisionerProxy


def test013():
    """
    test013: check that a set of different proxies can be created
    """
    aws = {"kind": "aws",
           "args": {
                "positional": ("test010",),
                "keyword": {'default_region': "reg1",
                            'aws_access_key': "the key",
                            'aws_secret_access_key': "the secret key"}
            }
           }
    az = {"kind": "az",
          "args": {
              "positional": ["test011"],
              "keyword": {
                  "subscription_id": "subid",
                  "client_id": "cliid",
                  "secret": "the secret",
                  "tenant": "tenant"
              }
           }
          }
    op = {"kind": "os",
          "args": {
              "positional": ["test012"],
              "keyword": {
                  "config_files": ["file1"]
              }
           }
          }
    pl = process_proxies([aws, az, op])
    assert len(pl) == 3
    assert type(pl[0]) == AWSProvisionerProxy
    assert type(pl[1]) == AzureProvisionerProxy
    assert type(pl[2]) == OpenStackProvisionerProxy


def test014():
    """
    test014: simple infra model test of ModelProcessor
    """
    jstr = open(os.path.join(here, "model014.json"), "r").read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, "model014.py"), "r").read()
    d["details"]["content"] = model_str
    mp = ModelProcessor(d, dmodule_dir=dynamic_module_dir)
    assert mp
    inst = mp.get_model_instance()
    assert inst.name == "test014"


def test015():
    """
    test015: load module with infra and namespace in the same module
    """
    jstr = open(os.path.join(here, "model015.json"), "r").read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, "model015.py"), "r").read()
    d["infra"]["details"]["content"] = model_str
    d["namespace"]["details"]["content"] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    im = models["infra"]
    nm = models["namespace"]
    ii = im.get_model_instance()
    assert ii.name == "infra015"
    ni = nm.get_model_instance()
    assert ni.name == "namespace015"


def test016():
    """
    test016: put a multirole into the namespace and make a bunch of roles
    """
    jstr = open(os.path.join(here, "model016.json"), "r").read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, "model016.py"), "r").read()
    d["infra"]["details"]["content"] = model_str
    d["namespace"]["details"]["content"] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models["namespace"]
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test017():
    """
    test017: test putting a call to a method into the setup of a model
    """
    jstr = open(os.path.join(here, 'model017.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model017.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test018():
    """
    test018: test including a support module that is imported by a model module
    """
    jstr = open(os.path.join(here, 'model018.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model018.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    support_str = open(os.path.join(here, "support018.py"), "r").read()
    d["infra"]["support"][0]["details"]["content"] = support_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test019():
    """
    test019: test a model with a syntax error
    """
    jstr = open(os.path.join(here, 'model019.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model019.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


# the following classes are used to test RunnerEventManager; it is the destination
# the JSON messages are 'written' to, a fake orchestrator, and a fake NetworkX digraph
class MockDestination(object):
    def __init__(self):
        self.message = None

    def reset(self):
        self.message = None

    def write(self, jstr):
        self.message = jstr

    def get_message(self):
        return self.message


class MockOrchestrator(object):
    def __init__(self):
        self._id = 1


class MockDiGraph(object):
    def __init__(self):
        self.all_tasks = []
        for i in range(10):
            t = Task("task{}".format(i))
            t.performance_status = TaskExecControl.PERFORMING
            self.all_tasks.append(t)

        self.all_edges = []
        for i in range(8):
            self.all_edges.append((random.choice(self.all_tasks),
                                   random.choice(self.all_tasks)))

    def nodes(self):
        return self.all_tasks

    def edges(self):
        return self.all_edges


def test020():
    """
    test020: test writing out the JSON event for an orchestration starting message
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.orchestration_starting(orch)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_START


def test021():
    """
    test021: test generating an orchestration finished JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.orchestration_finished(orch, True)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_FINISH


def test022():
    """
    test022: test generating a provisioning started JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.provisioning_starting(orch)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_PROV_START


def test023():
    """
    test023: test generating a provisioning finished JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.provisioning_finished(orch, False)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_PROV_FINISH


def test024():
    """
    test024: test generating a configuration starting JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.configuration_starting(orch)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_CONFIG_START


def test025():
    """
    test025: test generating a configuration finished JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.configuration_finished(orch, True)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_CONFIG_FINISH


def test026():
    """
    test026: test generating an execution starting JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.execution_starting(orch)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_EXEC_START


def test027():
    """
    test027: test generating an execution finished JSON event
    """
    md = MockDestination()
    rem = RunnerEventManager(md)
    orch = MockOrchestrator()
    rem.execution_finished(orch, False)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == OrchestrationEventPayload
    assert orig.event_id() == ActuatorEvent.O_EXEC_FINISH


def test028():
    """
    test028: test generating an engine starting JSON event
    """
    class Infra028(InfraModel):
        pass
    model = Infra028("test028")

    md = MockDestination()
    rem = RunnerEventManager(md)

    mdg = MockDiGraph()
    rem.engine_starting(model, mdg)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == EngineEventPayload
    assert orig.event_id() == ActuatorEvent.E_START
    
    
def test029():
    """
    test029: test generating an engine finishing JSON event
    """
    class Infra029(InfraModel):
        pass
    model = Infra029("test029")

    md = MockDestination()
    rem = RunnerEventManager(md)

    rem.engine_finished(model)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == EngineEventPayload
    assert orig.event_id() == ActuatorEvent.E_FINISH


def test030():
    """
    test030: test generating a task starting JSON event
    """
    class MockInfra(InfraModel):
        pass
    model = MockInfra("mockInfra")
    t = Task("task030")
    t.performance_status = TaskExecControl.PERFORMING
    md = MockDestination()
    rem = RunnerEventManager(md)
    rem.task_starting(model, t)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == TaskEventPayload
    assert orig.event_id() == ActuatorEvent.T_START


def test031():
    """
    test031: test generating a task finishing JSON event
    """
    class MockInfra(InfraModel):
        pass
    model = MockInfra("mockInfra")
    t = Task("task031")
    t.performance_status = TaskExecControl.PERFORMING
    md = MockDestination()
    rem = RunnerEventManager(md)
    rem.task_finished(model, t)
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == TaskEventPayload
    assert orig.event_id() == ActuatorEvent.T_FINISH


def test032():
    """
    test032: test generating a task failed JSON event
    """
    class MockInfra(InfraModel):
        pass
    model = MockInfra("mockInfra")
    t = Task("task032")
    t.performance_status = TaskExecControl.PERFORMING
    md = MockDestination()
    rem = RunnerEventManager(md)
    rem.task_failed(model, t, ["very bad error message"])
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == TaskEventPayload
    assert orig.event_id() == ActuatorEvent.T_FAIL_FINAL


def test033():
    """
    test033: test generating a task fail/retry JSON event
    """
    class MockInfra(InfraModel):
        pass
    model = MockInfra("mockInfra")
    t = Task("task033")
    t.performance_status = TaskExecControl.PERFORMING
    md = MockDestination()
    rem = RunnerEventManager(md)
    rem.task_retry(model, t, ["very bad error message"])
    msg = md.get_message()
    orig = ActuatorEvent.from_json(msg)
    assert type(orig.event()) == TaskEventPayload
    assert orig.event_id() == ActuatorEvent.T_FAIL_RETRY


def test034():
    """
    test034: test handling an error during instance creation
    """
    jstr = open(os.path.join(here, 'model034.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model034.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


def test035():
    """
    test035: test handling an error during calling a method in model instance setup
    """
    jstr = open(os.path.join(here, 'model035.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model035.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


def test036():
    """
    test036: test handling an error while applying keys to a multicomponent
    """
    jstr = open(os.path.join(here, 'model036.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model036.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


def test037():
    """
    test037: test handling an incorrect path for a setup key
    """
    jstr = open(os.path.join(here, 'model037.json'), 'r').read()
    d = json.loads(jstr)
    model_str = open(os.path.join(here, 'model037.py'), 'r').read()
    d['infra']['details']['content'] = model_str
    d['namespace']['details']['content'] = model_str
    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


# test non-existent method name

if __name__ == "__main__":
    setup_module()
    passed = failed = 0
    test035()
    for k, v in sorted(globals().items()):
        if k.startswith("test"):
            try:
                v()
                passed += 1
            except:
                failed += 1
                import traceback
                print(">>>>Test {} failed:".format(k))
                traceback.print_exception(*sys.exc_info())
            else:
                print("test {} successful".format(k))
    print("passed: {}, failed {}".format(passed, failed))
    teardown_module()
