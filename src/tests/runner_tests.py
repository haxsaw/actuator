import fcntl
import json
import logging
import select
import sys
import os.path
import time
import random
import threading
import io
from actuator import (Role, MultiRole, with_variables, NamespaceModel, Var, ActuatorException,
                      InfraModel)
from actuator.task import Task, TaskExecControl
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.provisioners.azure import azure_class_factory
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.runner_utils.utils import (OrchestrationEventPayload, EngineEventPayload,
                                         TaskEventPayload, ActuatorEvent, setup_json_logging,
                                         RunnerJSONMessage, OrchestratorArgs, Proxy, RunVar,
                                         ModelSet, ModelDescriptor, ModelSetup, Keyset, Method,
                                         Arguments, ModuleDescriptor, JSONModuleDetails, JSONableDict)

here, f = os.path.split(__file__)
runner_dir = os.path.join(here, "..", "scripts")
sys.path.append(runner_dir)
del f

from runner import (process_vars, process_proxies, process_models, ModelProcessor,
                    RunnerEventManager, do_it, get_processor_from_file, JsonMessageProcessor)


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
    rv = [RunVar([], "OUTER", "nope"),
          RunVar(["r"], "INNER", "wibble", True),
          RunVar(["mr", "1"], "SLAVE_VAR", "blah")]
    process_vars(ns, rv)
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
    d = Proxy("aws", Arguments("test010", default_region="reg1", aws_access_key="the key",
                               aws_secret_access_key="the secret key"))
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == AWSProvisionerProxy


def test011():
    """
    test011: check that Azure proxies are created properly
    """
    d = Proxy("az", Arguments("test011", subscription_id="subid", client_id="cliid",
                              secret="the secret", tenant="tenant"))
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == AzureProvisionerProxy


def test012():
    """
    test012: create that openstack proxies are created properly.
    """
    d = Proxy("os", Arguments("test012", config_files="file1"))
    pl = process_proxies([d])
    assert len(pl) == 1
    assert type(pl[0]) == OpenStackProvisionerProxy


def test013():
    """
    test013: check that a set of different proxies can be created
    """
    aws = Proxy("aws", Arguments("test010", default_region="reg1", aws_access_key="the key",
                                 aws_secret_access_key="the secret key"))
    az = Proxy("az", Arguments("test011", subscription_id="subid", client_id="cliid",
                               secret="the secret", tenant="tenant"))
    op = Proxy("os", Arguments("test012", config_files="file1"))
    pl = process_proxies([aws, az, op])
    assert len(pl) == 3
    assert type(pl[0]) == AWSProvisionerProxy
    assert type(pl[1]) == AzureProvisionerProxy
    assert type(pl[2]) == OpenStackProvisionerProxy


def test014():
    """
    test014: simple infra model test of ModelProcessor
    """
    model_str = open(os.path.join(here, "model014.py"), "r").read()
    jmd = JSONModuleDetails(content=model_str)
    setup = ModelSetup(Arguments("test014"))
    d = ModelDescriptor("json", "model014saved", jmd, "Infra014", setup)

    mp = ModelProcessor(d, dmodule_dir=dynamic_module_dir)
    assert mp
    inst = mp.get_model_instance()
    assert inst.name == "test014"


def test015():
    """
    test015: load module with infra and namespace in the same module
    """
    model_str = open(os.path.join(here, "model015.py"), "r").read()
    jmd = JSONModuleDetails(content=model_str)
    infra_setup = ModelSetup(Arguments("infra015"))
    ns_setup = ModelSetup(Arguments("namespace015"))
    imd = ModelDescriptor("json", "model015saved", jmd, "Infra015", infra_setup)
    nsmd = ModelDescriptor("json", "model015saved", jmd, "Namespace015", ns_setup)
    d = ModelSet(infra=imd, namespace=nsmd)

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
    model_str = open(os.path.join(here, "model016.py"), "r").read()
    jmd = JSONModuleDetails(content=model_str)
    infra_setup = ModelSetup(Arguments("infra016"))
    ns_keys = Keyset(["dudes"], [1, 2, 3, 4, 0])
    ns_setup = ModelSetup(Arguments("namespace016"), keys=[ns_keys])
    imd = ModelDescriptor("json", "model016saved", jmd, "Infra016", infra_setup)
    nsmd = ModelDescriptor("json", "model016saved", jmd, "Namespace016", ns_setup)
    d = ModelSet(infra=imd, namespace=nsmd)

    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models["namespace"]
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test017():
    """
    test017: test putting a call to a method into the setup of a model
    """
    model_str = open(os.path.join(here, 'model017.py'), 'r').read()
    jmd = JSONModuleDetails(content=model_str)
    infra_setup = ModelSetup(Arguments("infra017"))
    meth = Method("make_dudes", Arguments(5))
    ns_setup = ModelSetup(Arguments("namespace017"), methods=[meth])
    imd = ModelDescriptor("json", "model017saved", jmd, "Infra017", infra_setup)
    nsmd = ModelDescriptor("json", "model017saved", jmd, "Namespace017", ns_setup)
    d = ModelSet(infra=imd, namespace=nsmd)

    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test018():
    """
    test018: test including a support module that is imported by a model module
    """
    # all the infra stuff first this time
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model018.py'))
    support_str = open(os.path.join(here, "support018.py"), "r").read()
    smd = JSONModuleDetails(content=support_str)
    infra_support = ModuleDescriptor("json", "support018saved", smd)
    infra_setup = ModelSetup(Arguments("infra018"))
    imd = ModelDescriptor("json", "model018saved", jmd, "Infra018", infra_setup,
                          support=[infra_support])

    # now the namespace bits
    meth = Method("make_dudes", Arguments(5))
    ns_setup = ModelSetup(Arguments("namespace018"), methods=[meth])
    nsmd = ModelDescriptor("json", "model018saved", jmd, "Namespace018", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    ni = nm.get_model_instance()
    assert len(ni.dudes) == 5
    assert not set([str(x) for x in ni.dudes.keys()]).difference(set([str(x) for x in range(5)]))


def test019():
    """
    test019: test a model with a syntax error
    """
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model019.py'))
    infra_setup = ModelSetup(Arguments("infra019"))
    imd = ModelDescriptor("json", "model019saved", jmd, "Infra019", infra_setup)

    meth = Method("make_dudes", Arguments(5))
    ns_setup = ModelSetup(Arguments("namespace019"), methods=[meth])
    nsmd = ModelDescriptor("json", "model019saved", jmd, "Namespace019", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

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
        def get_model(self):
            return self

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
        def get_model(self):
            return self

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
        def get_model(self):
            return self

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
        def get_model(self):
            return self

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
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model034.py'))
    infra_setup = ModelSetup(Arguments("infra034"))
    imd = ModelDescriptor("json", "model034saved", jmd, "Infra034", infra_setup)

    meth = Method("make_dudes", Arguments(5))
    ns_setup = ModelSetup(Arguments("namespace034"), methods=[meth])
    nsmd = ModelDescriptor("json", "model034saved", jmd, "Namespace034", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

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
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model035.py'))
    infra_setup = ModelSetup(Arguments("infra035"))
    imd = ModelDescriptor("json", "model035saved", jmd, "Infra035", infra_setup)

    meth = Method("make_dudes", Arguments(5))
    ns_setup = ModelSetup(Arguments("namespace035"), methods=[meth])
    nsmd = ModelDescriptor("json", "model035saved", jmd, "Namespace035", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

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
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model036.py'))
    infra_setup = ModelSetup(Arguments("infra036"))
    imd = ModelDescriptor("json", "model036saved", jmd, "Infra036", infra_setup)

    meth = Method("make_dudes", Arguments(5))
    ks = Keyset(["non_multi_role"], [1, 2, 3])
    ns_setup = ModelSetup(Arguments("namespace036"), methods=[meth], keys=[ks])
    nsmd = ModelDescriptor("json", "model036saved", jmd, "Namespace036", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

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
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model037.py'))
    infra_setup = ModelSetup(Arguments("infra037"))
    imd = ModelDescriptor("json", "model037saved", jmd, "Infra037", infra_setup)

    ks = Keyset(["dudes", "wibble", "wobble"], [1, 2, 3])
    ns_setup = ModelSetup(Arguments("namespace037"), keys=[ks])
    nsmd = ModelDescriptor("json", "model037saved", jmd, "Namespace037", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


def test038():
    """
    test038: test getting a non-existent method to call (json indicates make_duds, not make_dudes
    """
    jmd = JSONModuleDetails(source_file=os.path.join(here, 'model038.py'))
    infra_setup = ModelSetup(Arguments("infra038"))
    imd = ModelDescriptor("json", "model038saved", jmd, "Infra038", infra_setup)

    meth = Method("make_duds", Arguments(5))
    ks = Keyset(["non_multi_role"], [1, 2, 3])
    ns_setup = ModelSetup(Arguments("namespace038"), methods=[meth], keys=[ks])
    nsmd = ModelDescriptor("json", "model038saved", jmd, "Namespace038", ns_setup)

    d = ModelSet(infra=imd, namespace=nsmd)

    models = process_models(d, module_dir=dynamic_module_dir)
    nm = models['namespace']
    try:
        ni = nm.get_model_instance()
        assert False, "this should have raised an exception"
    except ActuatorException as e:
        print(str(e))


def test039():
    """
    test039: test the overall processing of a complete JSON message
    """
    jmd = JSONModuleDetails(content="from actuator import InfraModel\rclass Infra039(InfraModel):\r    pass\r")
    infra_setup = ModelSetup(Arguments("test039"))
    imd = ModelDescriptor("json", "model039saved", jmd, "Infra039", infra_setup)

    p = Proxy("aws", Arguments("test039", default_region="reg1", aws_access_key="the key",
                               aws_secret_access_key="the secret key"))
    o = OrchestratorArgs(post_prov_pause=1)
    ms = ModelSet(infra=imd)
    msg = RunnerJSONMessage(ms, proxies=[p], orchestrator_args=o)
    jfile = io.StringIO(msg.to_json())

    processor = get_processor_from_file(jfile, module_dir=dynamic_module_dir)
    assert isinstance(processor, JsonMessageProcessor)


class DoItRunner(object):
    def __init__(self):
        self.is_running = None
        self.success = None

    def run_do_it(self, jfile, input, output):
        self.is_running = True
        self.success, self.is_running = do_it(jfile, input, output, module_dir=dynamic_module_dir)


def test040():
    """
    test040: test do_it to make the processor and quit
    """
    jmd = JSONModuleDetails(content="from actuator import InfraModel\rclass Infra040(InfraModel):\r    pass\r")
    infra_setup = ModelSetup(Arguments("test040"))
    imd = ModelDescriptor("json", "model040saved", jmd, "Infra040", infra_setup)

    p = Proxy("aws", Arguments("test040", default_region="reg1", aws_access_key="the key",
                               aws_secret_access_key="the secret key"))
    o = OrchestratorArgs(post_prov_pause=1)
    ms = ModelSet(infra=imd)
    msg = RunnerJSONMessage(ms, proxies=[p], orchestrator_args=o)
    jfile_path = os.path.join(here, "model040new.json")
    f = open(jfile_path, "w")
    f.write(msg.to_json())
    f.close()

    do_it_input, write_to_do_it = os.pipe()
    read_from_do_id, do_it_output = os.pipe()
    input = os.fdopen(do_it_input, "r")
    output = os.fdopen(do_it_output, "w")
    to_do_it = os.fdopen(write_to_do_it, "w")
    from_do_it = os.fdopen(read_from_do_id, "r")
    to_do_it.write("q\n")
    to_do_it.flush()
    di = DoItRunner()

    t = threading.Thread(target=di.run_do_it, args=(jfile_path, input, output))
    t.start()
    t.join(timeout=5)
    assert "READY:" in from_do_it.readline()
    assert not di.is_running


class FileEventDrain(object):
    """
    This class is made to read lines of JSON pumped out of a file (usually stderr);
    each line is separated by '--END--'
    """
    def __init__(self, reader):
        self.quit = False
        self.reader = reader
        self.this_line = None
        self.previous_line = None

    def stop_reading(self):
        self.quit = True

    def drain_until_event(self, event_id):
        self.quit = False
        # first, drain any lines that may be buffered in the file object
        self.this_line = self.reader.readline().strip()
        while len(self.this_line) and not self.quit:  # this will return '' if it would have otherwise blocked
            if '--END--' in self.this_line:
                d = json.loads(self.previous_line)
                if event_id == d.get("event_id", None):
                    self.quit = True
            if not self.quit:
                self.previous_line = self.this_line
                self.this_line = self.reader.readline().strip()
        # now go to the file descriptor for new data
        while not self.quit:
            rr, wr, er = select.select([self.reader], [], [], 0.1)
            if rr:
                self.this_line = self.reader.readline().strip()
                while len(self.this_line) and not self.quit:  # this will return '' if it would have otherwise blocked
                    if '--END--' in self.this_line:
                        d = json.loads(self.previous_line)
                        if event_id == d.get("event_id", None):
                            self.quit = True
                    if not self.quit:
                        self.previous_line = self.this_line
                        self.this_line = self.reader.readline().strip()
        return


def test041():
    """
    test041: test actually running processor's model then quit
    """
    jmd = JSONModuleDetails(content="from actuator import InfraModel\rclass Infra041(InfraModel):\r    pass\r")
    infra_setup = ModelSetup(Arguments("test041"))
    imd = ModelDescriptor("json", "model041saved", jmd, "Infra041", infra_setup)

    p = Proxy("aws", Arguments("test041", default_region="reg1", aws_access_key="the key",
                               aws_secret_access_key="the secret key"))
    o = OrchestratorArgs(post_prov_pause=1)
    ms = ModelSet(infra=imd)
    msg = RunnerJSONMessage(ms, proxies=[p], orchestrator_args=o)
    jfile_path = os.path.join(here, "model041new.json")
    f = open(jfile_path, "w")
    f.write(msg.to_json())
    f.close()
    
    # command/control pipes and files
    do_it_input, write_to_do_it = os.pipe()
    read_from_do_it, do_it_output = os.pipe()
    input = os.fdopen(do_it_input, "r", 1)
    output = os.fdopen(do_it_output, "w", 1)
    to_do_it = os.fdopen(write_to_do_it, "w", 1)
    from_do_it = os.fdopen(read_from_do_it, "r", 1)
    # stderr capture pipes and files
    old_stderr = sys.stderr
    stderr_read, stderr_write = os.pipe()
    flags = fcntl.fcntl(stderr_read, fcntl.F_GETFD)
    fcntl.fcntl(stderr_read, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    stderr_input = os.fdopen(stderr_read, "r", 1)
    stderr_ouput = os.fdopen(stderr_write, "w", 1)
    sys.stderr = stderr_ouput
    fed = FileEventDrain(stderr_input)
    # remember the old logging handler
    logger = logging.getLogger()
    old_handler = logger.handlers[0]

    di = DoItRunner()
    t = threading.Thread(target=di.run_do_it, args=(jfile_path, input, output))
    try:
        del logger.handlers[:]
        setup_json_logging()
        t.start()
        time.sleep(0.1)
        assert "READY:" in from_do_it.readline().strip()

        to_do_it.write("r\n")
        to_do_it.flush()

        fed.drain_until_event(ActuatorEvent.O_FINISH)
        to_do_it.write("q\n")
        to_do_it.flush()
        t.join(timeout=2)

        assert di.success, "success is {}".format(di.success)

    finally:
        to_do_it.write("q\n")
        to_do_it.flush()
        t.join(timeout=2)
        sys.stderr = old_stderr
        del logger.handlers[:]
        logger.handlers.append(old_handler)
        time.sleep(0.1)
        assert not di.is_running


def test042():
    """
    test042: Check that JSONModuleDetails goes to/from JSON properly
    """
    content = open(__file__, "r").read()
    jmd1 = JSONModuleDetails(content)
    j1 = jmd1.to_json()
    jmd1p = JSONableDict.from_json(j1)
    assert isinstance(jmd1p, JSONModuleDetails)
    assert content == jmd1p.content

    jmd2 = JSONModuleDetails(source_file=__file__)
    j2 = jmd2.to_json()
    jmd2p = JSONableDict.from_json(j2)
    assert isinstance(jmd2p, JSONModuleDetails)
    assert content == jmd2p.content


def test043():
    """
    test043: Check that ModuleDescriptors go to/from JSON
    """
    jmd = JSONModuleDetails(content=open(__file__, "r").read())
    md = ModuleDescriptor("json", module_name="wibble", module_details=jmd)
    j = md.to_json()
    mdp = JSONableDict.from_json(j)
    assert isinstance(mdp, ModuleDescriptor)
    assert mdp.module_name == md.module_name
    assert mdp.kind == md.kind
    assert isinstance(mdp.details, JSONModuleDetails)
    assert md.details.content == mdp.details.content


def test044():
    """
    test044: Check that Arguments go to/from JSON
    """
    a1 = Arguments(1, 2, x=1, y=4)
    j = a1.to_json()
    a1p = JSONableDict.from_json(j)
    assert isinstance(a1p, Arguments)
    assert list(a1.positional) == a1p.positional
    assert a1.keyword == a1p.keyword

    a2 = Arguments(x=1, y=2)
    j = a2.to_json()
    a2p = JSONableDict.from_json(j)
    assert isinstance(a2p, Arguments)
    assert a2.keyword == a2p.keyword

    a3 = Arguments( *(1, 2), **{'x': 6, 'b': 7})
    j = a3.to_json()
    a3p = JSONableDict.from_json(j)
    assert isinstance(a3p, Arguments)
    assert a3.keyword == a3p.keyword
    assert list(a3.positional) == a3p.positional


def test045():
    """
    test045: Check that Methods go to/from JSON
    """
    args = Arguments(1, 2, 3, x=1, b=3)
    m = Method("wibble", args)
    j = m.to_json()
    mp = JSONableDict.from_json(j)
    assert isinstance(mp, Method)
    assert mp.method == m.method, "m.method={}, mp.method={}".format(m.method, mp.method)
    assert mp.arguments.positional == list(m.arguments.positional)
    assert mp.arguments.keyword == m.arguments.keyword


def test046():
    """
    test046: Check that Keyset goes to/from JSON
    """
    ks = Keyset(['a', 'b', 'c'], [1,2,3,4,5])
    j = ks.to_json()
    ksp = JSONableDict.from_json(j)
    assert isinstance(ksp, Keyset)
    assert ks.keys == ksp.keys
    assert ks.path == ksp.path


def test047():
    """
    test047: Check that a ModelSetup goes to/from JSON
    """
    args = Arguments(1, 'a', 5, x=9, y='wibble')
    keys = Keyset(['cluster', 'slaves'], [1, 2, 3, 4, 5])
    method = Method("wibblemeth", Arguments(1, 2))
    ms = ModelSetup(args, [method], [keys])
    j = ms.to_json()
    msp = JSONableDict.from_json(j)
    assert isinstance(msp, ModelSetup)
    assert isinstance(msp.keys[0], Keyset)
    assert isinstance(msp.methods[0], Method)
    assert list(ms.methods[0].arguments.positional) == msp.methods[0].arguments.positional
    assert ms.keys[0].path == msp.keys[0].path


def test048():
    """
    test048: Check that a ModelDescriptor goes to/from JSON
    """
    deets = JSONModuleDetails(source_file=__file__)
    keys = Keyset(['cluster', 'slaves'], [1, 2, 3, 4, 5])
    setup = ModelSetup(Arguments(1, 2, 3), keys=[keys])
    desc = ModelDescriptor("json", "wibble", deets, "Wibble", setup)
    j = desc.to_json()
    d2 = JSONableDict.from_json(j)
    assert isinstance(d2, ModelDescriptor)
    assert desc.kind == d2.kind
    assert desc.classname == d2.classname
    assert desc.module_name == d2.module_name
    assert desc.details.content == d2.details.content
    assert list(desc.setup.init.positional) == d2.setup.init.positional


def test049():
    """
    test049: Check that a ModelSet goes to/from JSON
    """
    ms1 = ModelSet()
    j = ms1.to_json()
    ms1p = JSONableDict.from_json(j)
    assert isinstance(ms1p, ModelSet)

    deets = JSONModuleDetails(source_file=__file__)
    keys = Keyset(['cluster', 'slaves'], [1, 2, 3, 4, 5])
    setup = ModelSetup(Arguments(1, 2, 3), keys=[keys])
    desc = ModelDescriptor("json", "wibble", deets, "Wibble", setup)
    ms2 = ModelSet(infra=desc, namespace=desc)
    j = ms2.to_json()
    ms2p = JSONableDict.from_json(j)
    assert isinstance(ms2p, ModelSet)
    assert isinstance(ms2p.infra, ModelDescriptor)


def test050():
    """
    test050: Check that RunVar goes to/from JSON
    """
    rv = RunVar(["a", 'b'], "WIBBLE", "wobble")
    j = rv.to_json()
    rvp = JSONableDict.from_json(j)
    assert isinstance(rvp, RunVar)
    assert rv.varpath == rvp.varpath
    assert rv.name == rvp.name
    assert rv.isoverride == rvp.isoverride
    assert rv.value == rvp.value


def test051():
    """
    test051: Check that Proxy goes to/from JSON
    """
    p = Proxy("aws", Arguments(1, 2,3,4))
    j = p.to_json()
    pp = JSONableDict.from_json(j)
    assert isinstance(pp, Proxy)
    assert isinstance(pp.args, Arguments)
    assert p.kind == pp.kind


def test052():
    """
    test052: Check that OrchestratorArgs goes to/from JSON
    """
    oa = OrchestratorArgs(no_delay=True, post_prov_pause=5, num_threads=20)
    j = oa.to_json()
    oap = JSONableDict.from_json(j)
    assert isinstance(oap, OrchestratorArgs)
    assert oa.no_delay == oap.no_delay
    assert oa.post_prov_pause == oap.post_prov_pause
    assert oa.num_threads == oap.num_threads
    assert oa.client_keys == oap.client_keys


def test053():
    """
    test053: Check that RunnerJSONMessage goes to/from JSON
    """
    deets = JSONModuleDetails(source_file=__file__)
    keys = Keyset(['cluster', 'slaves'], [1, 2, 3, 4, 5])
    setup = ModelSetup(Arguments(1, 2, 3), keys=[keys])
    desc = ModelDescriptor("json", "wibble", deets, "Wibble", setup)
    ms2 = ModelSet(infra=desc, namespace=desc)
    rv = RunVar(["a", 'b'], "WIBBLE", "wobble")
    p = Proxy("aws", Arguments(1, 2,3,4))
    oa = OrchestratorArgs(no_delay=True, post_prov_pause=5, num_threads=20)
    msg = RunnerJSONMessage(ms2, vars=[rv], proxies=[p], orchestrator_args=oa)
    j = msg.to_json()
    msgp = JSONableDict.from_json(j)
    assert isinstance(msgp, RunnerJSONMessage), "msgp is a {}".format(type(msgp))


if __name__ == "__main__":
    setup_module()
    passed = failed = 0
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
