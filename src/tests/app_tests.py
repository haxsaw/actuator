import json
import six
from nose import SkipTest
from errator import reset_all_narrations, set_default_options
from actuator import (ServiceModel, ctxt, MultiResource, ActuatorException, ActuatorOrchestration,
                      ExecutionException)
from actuator.namespace import with_variables, Var, NamespaceModel, Role
from actuator.infra import InfraModel, StaticServer
from actuator.config import ConfigModel, NullTask, with_dependencies
from actuator.config_tasks import WaitForTaskTask
from actuator.modeling import ModelReference, ModelInstanceReference, channel, CallContext
from actuator.utils import persist_to_dict, reanimate_from_dict, adb
from actuator.provisioners.openstack.resources import (SecGroup, SecGroupRule)
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.provisioners.core import ProvisioningTaskEngine
from actuator.task import TaskEventHandler


def setup_module():
    reset_all_narrations()
    set_default_options(check=True)


class TestInfra(InfraModel):
    server = StaticServer("server", ctxt.nexus.svc.v.SERVER_IP)


class TestNamespace(NamespaceModel):
    with_variables(Var("NS-GLOBAL", "global"))

    role = Role("role", host_ref=ctxt.nexus.inf.server,
                variables=[Var("NS_LOCAL", "local"),
                           Var("buried2", None)])


class TestConfig(ConfigModel):
    task = NullTask("task", task_role=ctxt.nexus.ns.role)


class TestSvc(ServiceModel):
    server_ip = ctxt.nexus.svc.infra.server.hostname_or_ip
    with_variables(Var("WIBBLE", "hiya"),
                   Var("buried", server_ip),
                   Var("SERVER_IP", "127.0.0.1"))
    infra = TestInfra
    namespace = TestNamespace
    config = TestConfig
    non_model = 1


def get_simple_instance():
    return TestSvc("testsvc", infra_args=[["infra"], {}],
                   namespace_args=[["namespace"], {}],
                   config_args=[["config"], {}])


def test001():
    """
    test001: check that we get proper refs for app class attributes
    """
    assert isinstance(TestSvc.infra, ModelReference), "infra isn't a model reference"
    assert isinstance(TestSvc.namespace, ModelReference), "namespace isn't a model reference"
    assert isinstance(TestSvc.config, ModelReference), "config isn't a model reference"
    assert isinstance(TestSvc.non_model, int), "non_model isn't a plain value"


def test002():
    """
    test002: check that we get proper refs for app class instance attributes
    """
    a = get_simple_instance()
    assert isinstance(a.infra, ModelInstanceReference), "infra isn't an instance ref"
    assert isinstance(a.namespace, ModelInstanceReference), "namespace isn't an instance ref"
    assert isinstance(a.config, ModelInstanceReference), "config isn't an instance ref"
    assert isinstance(a.non_model, int), "non_model isn't a plain value"


def test003():
    """
    test003: check that we can reach an underlying data attribute
    """
    a = get_simple_instance()
    assert a.infra.server.name.value() == "server"


def test004():
    """
    test004: check being able to express a path to a component as a context expr on the service
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    v = Var("t4", a.server_ip)
    assert v.get_value(a) == "127.0.0.1", "server_ip is {}".format(a.server_ip())


def test005():
    """
    test005: check that a component can find a value for a shortcut to an attribute
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    v, o = a.namespace.find_variable("buried")
    assert v and v.get_value(a.namespace.value()) == "127.0.0.1"
    assert v.get_value(a.namespace.role.value()) == "127.0.0.1"


def test006():
    """
    test006: check that a subcomponent can be told how to find a value
    """
    a = get_simple_instance()
    a.add_variable(Var("buried2", a.server_ip))
    a.infra.server.fix_arguments()
    v, o = a.namespace.find_variable("buried2")
    assert v and v.get_value(a.namespace.value()) == "127.0.0.1"
    v, o = a.namespace.role.find_variable("buried2")
    assert v.get_value(a.namespace.role.value()) != "127.0.0.1"


def test007():
    """
    test007: check that a accessing a Var via the 'v' attribute is working
    """
    a = get_simple_instance()
    a.add_variable(Var("buried2", a.server_ip))
    a.infra.server.fix_arguments()

    assert a.v.buried2() == "127.0.0.1"
    assert a.namespace.v.buried2() == "127.0.0.1"
    assert a.namespace.role.v.buried2() == "127.0.0.1"


def test008():
    """
    test008: check that var_value() on a container yields correct results
    """
    a = get_simple_instance()
    a.add_variable(Var("buried2", a.server_ip))
    a.infra.server.fix_arguments()

    assert a.var_value("buried2") == "127.0.0.1"
    assert a.namespace.var_value("buried2") == "127.0.0.1"
    assert a.namespace.role.var_value("buried2") == "127.0.0.1"


def test009():
    """
    test009: checking that overrides at a more local level work
    """
    a = get_simple_instance()
    a.add_variable(Var("buried2", a.server_ip),
                   Var("NS_LOCAL", 'non-local'))
    a.infra.server.fix_arguments()

    assert a.v.NS_LOCAL() == "non-local"
    assert a.namespace.v.NS_LOCAL() == "non-local"
    assert a.namespace.role.v.NS_LOCAL() == "local"


def test010():
    """
    test010: checking that path stuff works
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()

    assert ".".join(a.namespace.get_path()) == "namespace", "path was {}".format(a.namespace.get_path())
    assert ".".join(a.namespace.role.get_path()) == "namespace.role", \
           "path was {}".format(a.namespace.role.get_path())
    assert ".".join(a.namespace.role.name.get_path()) == "namespace.role.name", \
           "path was {}".format(a.namespace.role.name.get_path())
    assert ".".join(a.infra.server.name.get_path()) == "infra.server.name", \
           "path was {}".format(a.infra.server.name.get_path())
    assert ".".join(a.config.task.name.get_path()) == "config.task.name",  \
           "path was {}".format(a.config.task.name.get_path())


def test011():
    """
    test011: AbstractModelingEntity method check: idx
    """
    a = get_simple_instance()

    assert a.namespace.idx.value() is None, "the idx is {}".format(a.namespace.idx.value())


def test012():
    """
    test012: AbstractModelingEntity method check: index_of
    """
    a = get_simple_instance()

    assert a.infra.index_of(a.infra.server.value()) is None


def test13():
    """
    test013: AbstractModelingEntity method check: fix_arguments
    """
    a = get_simple_instance()
    a.fix_arguments()
    assert True


def test14():
    """
    test014: AbstractModelingEntity method check: _get_arg_value
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    assert a._get_arg_value(a.server_ip) == "127.0.0.1"


def test015():
    """
    test015: AbstractModelingEntity method check: get_init_args
    """
    a = get_simple_instance()
    pargs, kwargs = a.get_init_args()
    assert pargs == ("testsvc",)


def test016():
    """
    test016: AbstractModelingEntity method check: clone
    """
    a = get_simple_instance()
    a_clone = a.clone()
    assert a.name == a_clone.name
    assert a._infra == a_clone._infra
    assert a._namespace == a_clone._namespace
    assert a._config == a_clone._config


def test017():
    """
    test017: basic persistence check
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    d = persist_to_dict(a)
    a_clone = reanimate_from_dict(d)
    assert a.name == a_clone.name
    assert a._infra_args == a_clone._infra_args
    assert a.namespace.role.name.value() == a_clone.namespace.role.name.value()
    assert a.infra.server.name.value() == a_clone.infra.server.name.value()
    assert a.config.task.name.value() == a_clone.config.task.name.value()
    assert a.infra.server.hostname_or_ip.value() == a_clone.infra.server.hostname_or_ip.value()


class Infra017a(InfraModel):
    none = StaticServer("017a", "11.11.11.11")


def test017a():
    """
    test017a: work out errors in persistence due to copy of __components to model instances
    """
    i = Infra017a("17a")
    i.fix_arguments()
    d = persist_to_dict(i)
    i_clone = reanimate_from_dict(d)
    assert isinstance(i_clone, Infra017a)
    assert i.name == i_clone.name
    assert i.none.hostname_or_ip.value() == i_clone.none.hostname_or_ip.value(), "orig={}, clone={}".format(i.none.hostname_or_ip,
                                                                                            i_clone.none.hostname_or_ip)


def test018():
    """
    test018: checking persisted form goes to json and back
    """
    # @FIXME
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    d = persist_to_dict(a)
    d_prime = json.loads(json.dumps(d))
    a_clone = reanimate_from_dict(d_prime)
    assert a.name == a_clone.name
    assert a.namespace.role.name.value() == a_clone.namespace.role.name.value()
    assert a.infra.server.name.value() == a_clone.infra.server.name.value()
    assert a.config.task.name.value() == a_clone.config.task.name.value()
    assert a.infra.server.hostname_or_ip.value() == a_clone.infra.server.hostname_or_ip.value()


def test19():
    """
    test19: check we can tell when we have the wrong kind of value for the infra class attr
    """
    try:
        class T19a(ServiceModel):
            infra = 1
        assert False, "this should have raised with infra = 1"
    except Exception as e:
        assert "'infra' attribute" in str(e)
    try:
        class T19b(ServiceModel):
            infra = TestNamespace
        assert False, "this should have raised with infra = TestNamespace"
    except Exception as e:
        assert "'infra' attribute" in str(e)


def test20():
    """
    test20: check we can tell when we have the wrong kind of value for the namespace class attr
    """
    try:
        class T20a(ServiceModel):
            namespace = 1
        assert False, "this should have raised with namespace = 1"
    except Exception as e:
        assert "'namespace' attribute" in str(e)
    try:
        class T20b(ServiceModel):
            namespace = TestInfra
        assert False, "this should have raised with namespace = TestNamespace"
    except Exception as e:
        assert "'namespace' attribute" in str(e)


def test21():
    """
    test21: check we can tell when we have the wrong kind of value for the config class attr
    """
    try:
        class T21a(ServiceModel):
            config = 1
        assert False, "this should have raised with config = 1"
    except Exception as e:
        assert "'config' attribute" in str(e)
    try:
        class T21b(ServiceModel):
            config = TestInfra
        assert False, "this should have raised with config = TestNamespace"
    except Exception as e:
        assert "'config' attribute" in str(e)
    try:
        class T21c(ServiceModel):
            config = TestNamespace("wibble")
        assert False, "this should have raised with config = TestInfra('wibble')"
    except Exception as e:
        assert "'config' attribute" in str(e)


def test022():
    """
    test022: Nest a service inside another service, connect them using Vars and context exprs
    """
    class T22(ServiceModel):
        with_variables(Var("buried2", "127.0.0.1"))
        inner = TestSvc
        infra = TestInfra
        namespace = TestNamespace
        config = TestConfig

    a = T22("t22", infra_args=(("outersvc",), {}),
            services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    a.fix_arguments()
    assert a.inner.namespace.role.var_value("buried2") == "127.0.0.1"


def test023():
    """
    test023: Nest a service inside another service, create context expr for a var in the outer
    """
    class T23(ServiceModel):
        with_variables(Var("buried2", ctxt.nexus.parent.svc.v.THE_IP),
                       Var("THE_IP", "127.0.0.1"))
        inner = TestSvc
        infra = TestInfra
        namespace = TestNamespace
        config = TestConfig

    a = T23("t23", infra_args=(("outer",), {}),
            services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    a.fix_arguments()
    assert a.inner.namespace.role.var_value("buried2") == "127.0.0.1"


class OuterNamespace(NamespaceModel):
    pass


class OuterConfig(ConfigModel):
    pass


def test024():
    """
    test024: Nest a service inside another service, fish a host ip out of another infra
    """
    class T24(ServiceModel):
        with_variables(Var("buried2", ctxt.nexus.parent.svc.infra.server.hostname_or_ip),
                       Var("THE_IP", "127.0.0.1"),
                       Var("SERVER_IP", "!{THE_IP}"))
        inner = TestSvc
        infra = TestInfra
        namespace = OuterNamespace
        config = OuterConfig

    a = T24("t24",
            infra_args=(("outer",), {}),
            services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    a.inner.infra.server.fix_arguments()
    a.infra.server.fix_arguments()
    assert a.inner.namespace.role.var_value("buried2") == "127.0.0.1"


def test25():
    """
    test25: create a service with model instances instead of just classes
    """
    class T25(ServiceModel):
        with_variables(Var("buried2", ctxt.nexus.svc.infra.server.hostname_or_ip),
                       Var("SERVER_IP", "127.0.0.1"))
        infra = TestInfra("t25-infra")
        namespace = TestNamespace("t25-namespace")
        config = TestConfig("t25-config")

    a = T25("t25")
    a.infra.server.fix_arguments()
    assert a.infra.value() is not T25.infra.value()
    assert a.infra.server.value is not T25.infra.server.value()
    assert a.namespace.value() is not T25.namespace.value()
    assert a.config.value() is not T25.config.value()
    assert a.namespace.var_value("buried2") is not None


class T26(ServiceModel):
    with_variables(Var("buried2", ctxt.nexus.parent.svc.v.THE_IP),
                   Var("SERVER_IP", "wibble"),
                   Var("THE_IP", "127.0.0.1"))
    inner = TestSvc
    infra = TestInfra
    namespace = TestNamespace
    config = TestConfig


def compare_t26(t1, t2):
    assert isinstance(t1, T26)
    assert isinstance(t2, T26)
    assert t1.inner.name.value() == t2.inner.name.value()
    assert t1.inner.infra.server.name.value() == t2.inner.infra.server.name.value()
    assert t1.inner.infra.server.hostname_or_ip.value() == t2.inner.infra.server.hostname_or_ip.value()
    assert t1.inner.namespace.var_value("buried") == t2.inner.namespace.var_value("buried")
    assert t1.inner.namespace.role.var_value("buried2") == t2.inner.namespace.role.var_value("buried2")
    assert t1.inner.config.task.name.value() == t2.inner.config.task.name.value()
    assert t1.inner.config.task.task_role.name.value() == t2.inner.config.task.task_role.name.value()


def test026():
    """
    test026: test persistence/reanimation service with a nested service
    """
    t26 = T26("t26-outer", infra_args=(("outer",), {}),
              services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    t26.infra.server.fix_arguments()
    t26.inner.infra.server.fix_arguments()
    t26.config.task.fix_arguments()
    t26.inner.config.task.fix_arguments()
    d = persist_to_dict(t26)
    d_prime = json.loads(json.dumps(d))
    franken_t26 = reanimate_from_dict(d_prime)
    compare_t26(t26, franken_t26)


def test027():
    """
    test027: manually create an inner TestSvc, check if the same before/after persistence/reanim
    """
    t27 = T26("t27-outer", infra_args=(("outer",), {}),
              services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    t27.infra.server.fix_arguments()
    t27.inner.infra.server.fix_arguments()
    t27.config.task.fix_arguments()
    t27.inner.config.task.fix_arguments()
    d = persist_to_dict(t27)
    d_prime = json.loads(json.dumps(d))
    franken_t27 = reanimate_from_dict(d_prime)
    compare_t26(t27, franken_t27)


def test028():
    """
    test028: manually create the TestInfra, default the rest, check before/after persistence
    """
    t28 = T26("t28-outer", infra=TestInfra("t28Infra"),
              services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    t28.infra.server.fix_arguments()
    t28.inner.infra.server.fix_arguments()
    t28.config.task.fix_arguments()
    t28.inner.config.task.fix_arguments()
    d = persist_to_dict(t28)
    d_prime = json.loads(json.dumps(d))
    franken_t28 = reanimate_from_dict(d_prime)
    compare_t26(t28, franken_t28)


def test029():
    """
    test029: manually create the TestNamespace, default the rest, check before/after persistence
    """
    t29 = T26("t29-outer", namespace=TestNamespace("t29_namespace"),
              infra_args=(("outer",), {}),
              services={"inner": (("inner",), {"infra_args": (("isvc",), {})})})
    t29.infra.server.fix_arguments()
    t29.inner.infra.server.fix_arguments()
    t29.config.task.fix_arguments()
    t29.inner.config.task.fix_arguments()
    d = persist_to_dict(t29)
    d_prime = json.loads(json.dumps(d))
    franken_t29 = reanimate_from_dict(d_prime)
    compare_t26(t29, franken_t29)


def test030():
    """
    test030: manually create the TestConfig, default the rest, check before/after persistence
    """
    t30 = T26("t30-outer", config=TestConfig("t30-conf"),
              infra_args=(("outer",), {}),
              services={"inner": (("inner",), {})})
    t30.infra.server.fix_arguments()
    t30.inner.infra.server.fix_arguments()
    t30.config.task.fix_arguments()
    t30.inner.config.task.fix_arguments()
    d = persist_to_dict(t30)
    d_prime = json.loads(json.dumps(d))
    franken_t30 = reanimate_from_dict(d_prime)
    compare_t26(t30, franken_t30)


class BaseInfra(InfraModel):
    server = StaticServer("server", "127.0.0.1")


class BaseService(ServiceModel):
    infra = BaseInfra


class FinalService(BaseService):
    theip = channel(ctxt.nexus.svc.infra.server.hostname_or_ip)
    ip_no_nexus = channel(ctxt.model.infra.server.hostname_or_ip)
    namespace = NamespaceModel


def test031():
    """
    test031: try deriving one service from another
    """
    fs = FinalService("fs", infra_args=(('baseinfra',), {}))
    fs.fix_arguments()
    assert fs.theip == "127.0.0.1", "theip is {}".format(fs.theip)
    assert fs.ip_no_nexus == "127.0.0.1", "ip_no_nexus is {}".format(fs.ip_no_nexus)


class BaseService32(ServiceModel):
    infra = BaseInfra
    theip = channel(ctxt.model.infra.server.hostname_or_ip)


class FinalService32(BaseService32):
    pass


def test032():
    """
    test032: test if a channel is inherited properly
    """
    fs = FinalService32("fs32", infra_args=(("ba32",), {}))
    fs.fix_arguments()
    assert fs.theip == "127.0.0.1", "theip is {}".format(fs.theip)


class BaseService33(ServiceModel):
    infra = BaseInfra
    theip = channel(ctxt.model.infra.server.hostname_or_ip)


class FinalServive33(BaseService33):
    redirected_ip = channel(ctxt.model.theip)


def test033():
    """
    test033: test if a channel can be redirected
    """
    fs = FinalServive33("fs33", infra_args=(("ba33",), {}))
    fs.fix_arguments()
    assert fs.redirected_ip == "127.0.0.1", "redirected is {}".format(fs.redirected_ip)


class BaseInfra34(InfraModel):
    server = StaticServer("someserver", "99.99.99.99")
    server_ip = channel(ctxt.model.server.hostname_or_ip)


class BaseService34(ServiceModel):
    infra = BaseInfra34
    theip = channel(ctxt.model.infra.server_ip)


def test034():
    """
    test034: check that you can channel an attribute on an infra and access in a service
    """
    fs = BaseService34("bs34", infra_args=(("bi34",), {}))
    fs.fix_arguments()
    assert fs.infra.server_ip.value() == "99.99.99.99", "wrong value for infra's server ip: {}".format(fs.infra.server_ip)
    assert fs.theip == "99.99.99.99", "wrong value for the server's theip: {}".format(fs.theip)


class ExposeViaVar(ServiceModel):
    with_variables(Var("EXPOSED", ctxt.model.theip))
    infra = BaseInfra
    theip = channel(ctxt.model.infra.server.hostname_or_ip)


def test035():
    """
    test035: check that a channel attr value is available via a variable.
    :return:
    """
    s = ExposeViaVar("t35", infra_args=(("bi35",), {}))
    s.fix_arguments()
    assert s.v.EXPOSED() == "127.0.0.1", "the EXPOSED var is {}".format(s.v.EXPOSED())


class InfraMissingIP(InfraModel):
    server = StaticServer("missingip", ctxt.nexus.svc.v.SERVER_IP)


class IPSupplierSvc(ServiceModel):
    with_variables(Var("SERVER_IP", "66.66.66.66"))
    svcip = channel(ctxt.model.infra.server.hostname_or_ip)
    infra = InfraMissingIP


def test036():
    """
    test036: check that we can specify an infra that get's an IP from the service namespace
    """
    s = IPSupplierSvc("t36", infra_args=(("i36",), {}))
    s.fix_arguments()
    assert s.svcip == "66.66.66.66", "svcip is {}".format(s.svcip)


class InnerInfra37(InfraModel):
    server = StaticServer("inner37", ctxt.model.container.ip)


class Service37(ServiceModel):
    ip = "55.55.55.55"
    somevar = StaticServer("yum", "0.0.0.0")
    infra = InnerInfra37


def test037():
    """
    tes037: test that we can write a context expression that fetches a value from a service
    from a contained component
    """
    s = Service37("s37", infra_args=(("i37",), {}))
    s.refs_for_components()
    s.fix_arguments()
    assert s.infra.server.hostname_or_ip.value() == "55.55.55.55"


class BaseInfra38(InfraModel):
    bs = StaticServer("base", "127.0.0.1")


class DerivedInfra(BaseInfra38):
    annudder = StaticServer("annudder", "127.0.1.1")


def test038():
    """
    test038: check that derived model processing works for infra resources
    """
    assert isinstance(DerivedInfra.bs, ModelReference), "bs via class is {}".format(DerivedInfra.bs)
    i = DerivedInfra("di")
    assert isinstance(i.bs, ModelInstanceReference), "bs via instance is {}".format(i.bs)
    assert BaseInfra38.bs.value() is not i.bs.value(), "they were the same!"


class BaseInfra39(InfraModel):
    slaves = MultiResource(StaticServer("slave", "127.0.0.1"))


class Derived39(BaseInfra39):
    nn = StaticServer("namenode", "127.0.1.1")


def test039():
    """
    test039: check that multi-resources derive properly over infras
    """
    assert isinstance(Derived39.slaves[1], ModelReference), "slave ref via class is {}".format(Derived39.slaves[1])
    i = Derived39("d39")
    for x in range(5):
        _ = i.slaves[x]
    assert len(i.slaves) == 5, "wrong length: {}".format(len(i.slaves))
    assert len(i.components()) == 6, "wrong number of components: {}".format(len(i.components()))


class TestSetInfra40(InfraModel):
    server = StaticServer("svr", "127.0.0.1")
    svrip = channel()


def test040():
    """
    test040: test basic setting of an 'channel' descriptor into an infra
    """
    i = TestSetInfra40("tsi")
    i.svrip = ctxt.model.server.hostname_or_ip
    i.fix_arguments()
    assert i.svrip == "127.0.0.1", "the svrip is {}".format(i.svrip)


class TestSetChannel41(InfraModel):
    server1 = StaticServer("s1", "11.11.11.11")
    server2 = StaticServer("s2", "22.22.22.22")
    theip = channel()


def test041():
    """
    test041: ensure independence of channel properties across infra instances
    """
    i1 = TestSetChannel41("t41a")
    i1.theip = ctxt.model.server1.hostname_or_ip
    i2 = TestSetChannel41("t41b")
    i2.theip = ctxt.model.server2.hostname_or_ip
    i1.fix_arguments()
    i2.fix_arguments()
    assert i1.theip == "11.11.11.11", "wrong ip: {}".format(i1.theip)
    assert i2.theip == "22.22.22.22", "wrong ip: {}".format(i2.theip)


class Inner42(InfraModel):
    inner_svr = StaticServer("inner", ctxt.model.theip)
    theip = channel()


class Outer42(ServiceModel):
    infra = Inner42("inner svc")
    infra.theip = ctxt.nexus.svc.theip
    theip = "22.22.22.22"


def test042():
    """
    test042: see if we can set the ip on an inner service from a containing svc
    """
    out = Outer42("outer")
    out.fix_arguments()
    assert out.infra.inner_svr.hostname_or_ip.value() == "22.22.22.22", "the ip was {}".format(
        out.infra.inner_svr.hostname_or_ip.value())


# test043 support
class SubInfra1(InfraModel):
    srvr = StaticServer("sub1-43", "43.43.43.43")
    my_cidr = channel(ctxt.model.srvr.get_cidr4)


class SubSvc1(ServiceModel):
    infra = SubInfra1("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2(ServiceModel):
    infra = SubInfra2("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc43(ServiceModel):
    sub1 = SubSvc1("ss1")
    sub2 = SubSvc2("ss2")
    sub2.conn_pt = ctxt.nexus.parent.svc.sub1.the_cidr


def test043():
    """
    test043: compose a svc from two sub-services with channels that allow getting an IP from the sibling svc
    """
    # @NOTE: this points up the issue of fix_arguments() being blind to dependencies
    # we currently rely on the discovered task dependencies for each component to
    # ensure we do our "fixing" in the right time. The need for dependency management at
    # global fixing time is unclear, as there are values we may want to fix that won't
    # actually be available until some of the tasks have executed. For instance, if
    # on service wants to create a security group rule that uses a host IP from another
    # service, than until that host has been provisioned you can't determine the IP, and hence
    # fixing before execution will never lead to a useful value. Hence it isn't clear as to
    # whether or not making fixing respect dependencies is even useful in the first place.
    svc = Svc43("test43")
    # force the order that should be generated just to see if the chaing of ctxt-exprs are respected
    svc.sub1.infra.srvr.fix_arguments()
    svc.fix_arguments()
    assert svc.sub2.infra.sgr.cidr.value() == "43.43.43.43/32", "the cidr was {}".format(
        svc.sub2.infra.sgr.cidr.value()
    )


class Test044(InfraModel):
    wibble = channel()
    wobble = channel(ctxt.model.wibble)


def test044():
    """
    test044: check that we can test for the presence/absence of an channel descriptor
    """
    i = Test044("test044")
    assert i.has_channel_descriptor("wibble")
    assert i.has_channel_descriptor("wobble")
    assert not i.has_channel_descriptor("wamble")


class Test045(InfraModel):
    wibble = channel()
    wobble = channel(ctxt.model.wibble)


def test045():
    """
    test045: check that we get appropriate values when fetching cexprs for channel descriptors
    """
    i = Test045("test045")
    assert i.get_channel_cexpr("wibble") is None
    assert i.get_channel_cexpr("wobble")._path == ("wibble", "model"), "path is: {}".format(
        i.get_channel_cexpr("wobble")._path
    )
    try:
        _ = i.get_channel_cexpr("wamble")
        assert False, "this should have raised"
    except ActuatorException:
        pass


class SubInfra1_046(InfraModel):
    srvr = StaticServer("sub1-43", "43.43.43.43")
    my_cidr = channel(ctxt.model.srvr.get_cidr4)


class SubSvc1_046(ServiceModel):
    infra = SubInfra1_046("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2_046(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2_046(ServiceModel):
    infra = SubInfra2_046("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc046(ServiceModel):
    sub1 = SubSvc1_046("ss1")
    sub2 = SubSvc2_046("ss2")
    sub2.conn_pt = ctxt.nexus.parent.svc.sub1.the_cidr


def test046():
    """
    test046: check that we detect the proper containing component for a value in an channel chain
    """
    i = Svc046("t046")
    cexpr = i.sub2.infra.sgr._cidr
    cc = CallContext(i.sub2.infra.value(), i.sub2.infra.sgr)
    owner = cexpr.get_containing_component(cc)
    assert owner is i.sub1.infra.srvr.value()


class Infra047(InfraModel):
    sg = SecGroup("wibble")
    # An interesting note:
    # we could make the cidr= kwarg of SecGroupRule below
    # be cidr=ctxt.model.svr.hostname_or_ip to get the same info into the rule.
    # However, the containing component in this case will be the StaticServer, not the
    # instance of Svc047. This is because we don't chase across chained context expressions
    # for attribute values like we do for channel() attributes. Nonetheless you get the right
    # answer, as you'd only get an different dependency between the Rule and the Server instead
    # of the Rule and the ServiceModel. Since the ServiceModel is dependent on the Server, the net effect
    # is the same. An open question is whether we should make argument resolution also
    # chain through
    sgr = SecGroupRule("rest", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_ip)
    allowed_ip = channel()
    svr = StaticServer("server047", ctxt.model.allowed_ip)


class Svc047(ServiceModel):
    infra = Infra047("wamble")
    theip = "75.75.75.75"
    infra.allowed_ip = ctxt.nexus.svc.theip


def test047():
    """
    test047: check that we detect the proper parent container
    """
    i = Svc047("asfd")
    cexpr = i.infra.sgr._cidr
    cc = CallContext(i.infra.value(), i.infra.sgr)
    owner = cexpr.get_containing_component(cc)
    assert owner is i, "owner is {}".format(owner)
    cexpr = i.infra.svr._hostname_or_ip
    cc = CallContext(i.infra.value(), i.infra.svr)
    owner = cexpr.get_containing_component(cc)
    assert owner is i, "owner is {}".format(owner)
    i.fix_arguments()
    assert i.infra.svr.hostname_or_ip.value() == "75.75.75.75"


class Svc048(ServiceModel):
    recover = channel(ctxt.model.wibble)
    wibble = "wobble"


def test048():
    """
    test048: check the recovery of a channel's context expression
    """
    svc = Svc048("test048")
    svc.fix_arguments()
    d = persist_to_dict(svc)
    svc_prime = reanimate_from_dict(d)
    assert svc_prime.wibble == "wobble"
    assert svc_prime.recover == "wobble", "recover has {}".format(svc_prime.recover)
    path = svc_prime.get_channel_cexpr("recover")._path
    assert ["wibble", "model"] == path, "path is {}".format(path)


class Svc049(ServiceModel):
    recover = channel()
    someattr = "glee"


def test049():
    """
    test049: check recovery of a assigned context expression
    """
    svc = Svc049("s049")
    svc.recover = ctxt.model.someattr
    d = persist_to_dict(svc)
    sp = reanimate_from_dict(d)
    path = svc.get_channel_cexpr("recover")._path
    assert ["someattr", "model"] == list(path), "path is {}".format(path)
    path = sp.get_channel_cexpr("recover")._path
    assert ["someattr", "model"] == list(path), "path is {}".format(path)


class BaseInfra050(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("sgr", ctxt.model.sg, ip_protocol="tcp",
                       from_port=5000, to_port=5000, cidr=ctxt.model.host.get_cidr4)
    host = channel()


class DerivedInfra050(BaseInfra050):
    svr = StaticServer("svr050", "64.64.64.64")
    host = ctxt.model.svr


class Svc050(ServiceModel):
    infra = DerivedInfra050("50")


def test050():
    """
    test050: check that setting a channel on a derived class works, persists/comes back as well
    """
    i = Svc050("t050")
    i.infra.svr.fix_arguments()
    i.fix_arguments()
    assert i.infra.sgr.cidr.value() == "64.64.64.64/32", "cidr before is {}".format(i.infra.sgr.cidr.value())
    d = persist_to_dict(i)
    newi = reanimate_from_dict(d)
    assert newi.infra.sgr.cidr.value() == "64.64.64.64/32", "cidr after is {}".format(newi.infra.sgr.cidr.value())


class SubInfra1_051(InfraModel):
    srvr = StaticServer("sub1-51", "51.51.51.51")
    my_cidr = channel(ctxt.model.srvr.get_cidr4)


class SubSvc1_051(ServiceModel):
    infra = SubInfra1_051("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2_051(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2_051(ServiceModel):
    infra = SubInfra2_051("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc051(ServiceModel):
    sub1 = SubSvc1_051("ss1")
    sub2 = SubSvc2_051("ss2")
    sub2.conn_pt = ctxt.nexus.parent.svc.sub1.the_cidr


def test051():
    """
    test051: check that composed services persist/reanimate properly
    """
    i = Svc051("t051")
    cexpr = i.sub2.infra.sgr._cidr
    cc = CallContext(i.sub2.infra.value(), i.sub2.infra.sgr)
    owner = cexpr.get_containing_component(cc)
    assert owner is i.sub1.infra.srvr.value()
    d = persist_to_dict(i)
    newi = reanimate_from_dict(d)
    cc = CallContext(newi.sub2.infra.value(), newi.sub2.infra.sgr)
    owner = cexpr.get_containing_component(cc)
    assert owner is newi.sub1.infra.srvr.value()


class BaseInfra052(InfraModel):
    pass


class DeepBaseSvc_052(ServiceModel):
    infra = BaseInfra052("deepinfra")


class BaseSvc1_052(ServiceModel):
    dbs = DeepBaseSvc_052("dbs1")


class BaseSvc2_052(ServiceModel):
    infra = BaseInfra052("annuder")


class FinalSvc_052(ServiceModel):
    svc1 = BaseSvc1_052("svc1")
    svc2 = BaseSvc2_052("svc2")


def test052():
    """
    test052: check that we can find all the services in a nested collection of services
    """
    s = FinalSvc_052("final")

    thesvcs = s.all_services()
    assert len(thesvcs) == 4, "the services are: {}".format(thesvcs)


class SvcInfra1_053(InfraModel):
    sg = SecGroup("sg053")


class Svc1_053(ServiceModel):
    infra = SvcInfra1_053("sg")


class SvcInfra2_053(InfraModel):
    sgr = SecGroupRule("sgr053", ctxt.nexus.svc.thesg, ip_protocol="tcp",
                       from_port=5000, to_port=5000,
                       cidr="127.0.0.1/32")


class Svc2_053(ServiceModel):
    infra = SvcInfra2_053("sgr053")
    thesg = channel()


class TopSvc_053(ServiceModel):
    svc1 = Svc1_053("svc1")
    svc2 = Svc2_053("svc2")
    svc2.thesg = ctxt.nexus.parent.svc.svc1.infra.sg


def test053():
    """
    test053: test cross model dependencies
    """
    svc = TopSvc_053("testy053")
    svc.fix_arguments()
    pp = OpenStackProvisionerProxy("citycloud")
    pte = ProvisioningTaskEngine(svc.svc2.infra.value(), [pp])
    deps, ei = pte.get_dependencies()
    total_ei = sum(len(x) for x in ei.values())
    assert total_ei == 1, "deps is {}".format(ei)


class CountingTaskEventHandler(TaskEventHandler):
    def __init__(self):
        self.starting = set()
        self.finished = set()
        self.failed = set()
        self.retry = set()

    def task_starting(self, model, tec):
        self.starting.add(tec)

    def task_finished(self, model, tec):
        self.finished.add(tec)

    def task_retry(self, model, tec, errtext):
        self.retry.add(tec)

    def task_failed(self, model, tec, errtext):
        self.failed.add(tec)


class Infra054(InfraModel):
    server = StaticServer("s054", "127.0.0.1")


class Service054(ServiceModel):
    infra = Infra054


def test054():
    """
    test054: basic test of orchestration using a simple service
    """
    teh = CountingTaskEventHandler()
    svc = Service054("service054")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0.0, event_handler=teh)
    result = ao.initiate_system()
    assert result
    assert len(teh.starting) == 1
    assert len(teh.finished) == 1
    assert not teh.starting.symmetric_difference(teh.finished)


class Infra055(InfraModel):
    server = StaticServer("s055", "127.0.0.1")


class SvcInner055(ServiceModel):
    infra = Infra055


class SvcOuter055(ServiceModel):
    infra = Infra055
    inner = SvcInner055


def test055():
    """
    test055: Test nested services, outer svc has it's own infra
    """
    teh = CountingTaskEventHandler()
    svc = SvcOuter055("service055", services={"inner": (("inner055",), {})})
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0.0, event_handler=teh)
    result = ao.initiate_system()
    assert result
    assert len(teh.starting) == 2
    assert len(teh.finished) == 2
    assert not teh.starting.symmetric_difference(teh.finished)


class Infra056A(InfraModel):
    svc = StaticServer("svrA", ctxt.nexus.svc.ip)


class Svc056A(ServiceModel):
    infra = Infra056A("wibble")
    ip = channel()


class Infra056B(InfraModel):
    svc = StaticServer("svrB", "88.88.88.88")


class Svc056B(ServiceModel):
    infra = Infra056B("wobble")
    ip = channel(ctxt.nexus.svc.infra.svc.hostname_or_ip)


class Svc056(ServiceModel):
    svc_a = Svc056A("inner_a")
    svc_b = Svc056B("inner_b")
    svc_a.ip = ctxt.nexus.parent.svc.svc_b.ip
    svcb_ip = channel(ctxt.nexus.svc.svc_b.ip)


def test056():
    """
    test056: first cross-model dependency check
    """
    teh = CountingTaskEventHandler()
    svc = Svc056("service056")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0.0, event_handler=teh)
    result = ao.initiate_system()
    assert result
    assert len(teh.starting) == 2
    assert len(teh.finished) == 2
    assert not teh.starting.symmetric_difference(teh.finished)
    assert svc.svc_a.infra.svc.hostname_or_ip.value() == "88.88.88.88",  \
           "ip: {}".format(svc.svc_a.infra.svc.hostname_or_ip.value())
    deps, exts = ao.pte.get_dependencies()
    assert not exts
    assert len(deps) == 1, "deps is {}".format(deps)
    assert ("svrB", "svrA") == (deps[0].from_task.rsrc.name, deps[0].to_task.rsrc.name)


class NS057(NamespaceModel):
    midpoint = channel(ctxt.model.v.ENDPOINT)
    with_variables(Var("STARTPOINT", ctxt.model.midpoint),
                   Var("ENDPOINT", "bingo!"))


def test057():
    """
    test057: check that var that uses a channel that uses a var works
    """
    ns = NS057("wow")
    assert ns.v.STARTPOINT() == "bingo!", "it was {}".format(ns.v.STARTPOINT())
    assert ns.midpoint == "bingo!", "it was {}".format(ns.midpoint.value())


class NS058(NamespaceModel):
    final = "target"
    midpoint = channel(ctxt.model.final)
    with_variables(Var("START", ctxt.model.midpoint))


def test058():
    """
    test058: have a variable ref a channel that refs a plain attribute
    """
    ns = NS058("asdf")
    assert ns.v.START() == "target", "it was {}".format(ns.v.START())
    assert ns.midpoint == "target", "it was {}".format(ns.midpoint)


class NS059(NamespaceModel):
    with_variables(Var("START", ctxt.model.middle))
    middle = channel(ctxt.model.v.END)
    with_variables(Var("END", ctxt.model.v.START))


def test059():
    """
    test059: check that a var loop involving a channel is detected
    """
    # FIXME
    # This test is deactivated for now, as it points up an issue that is too broad
    # to address at this time. While we are able to detect reference cycles within
    # a homogeneous reference space (all variables, only model components), we can't
    # detect cycles where we change the reference space. For instance, in this test,
    # the variable START references a channel named 'middle', which has a context
    # expression that takes it to a variable named END. However, the value of END
    # is a reference to the START variable. Only variables actively detect cycles,
    # although when models attempt to build execution graphs for their components
    # they will also detect cycles. However, the arrangement in this test won't detect
    # the cycle, and that causes a stack overflow runtime error. *This is not easy to
    # fix*, as it would involve somehow tracking a path more globally to see if you
    # get back to where you were before. Until we can dedicate some time to addressing
    # this, this will just have to remain an issue that still needs to be resolved.
    raise SkipTest("Difficult problem that we don't have the time to fix right now")
    ns = NS059("059")
    try:
        value = ns.v.START()
        assert False, "this should not have been allowed: {}".format(value)
    except Exception as e:
        pass


class NS060(NamespaceModel):
    start = channel(ctxt.model.middle)
    middle = channel(ctxt.model.end)
    end = channel(ctxt.model.start)


def test060():
    """
    test060: check that a channel loop is detected
    """
    # FIXME
    # This test is deactivated for now, as it points up an issue that is too broad
    # to address at this time. While we are able to detect reference cycles within
    # a homogeneous reference space (all variables, only model components), we can't
    # detect cycles where we change the reference space. For instance, in this test,
    # the variable START references a channel named 'middle', which has a context
    # expression that takes it to a variable named END. However, the value of END
    # is a reference to the START variable. Only variables actively detect cycles,
    # although when models attempt to build execution graphs for their components
    # they will also detect cycles. However, the arrangement in this test won't detect
    # the cycle, and that causes a stack overflow runtime error. *This is not easy to
    # fix*, as it would involve somehow tracking a path more globally to see if you
    # get back to where you were before. Until we can dedicate some time to addressing
    # this, this will just have to remain an issue that still needs to be resolved.
    raise SkipTest("Difficult problem that we don't have the time to fix right now")
    ns = NS060("asdf")
    try:
        value = ns.start
        assert False, "this should not have been allowed: {}".format(value)
    except Exception as e:
        pass


class Inf061(InfraModel):
    server = StaticServer("test061", "25.25.25.25")
    server_ip = channel(ctxt.model.server.hostname_or_ip)


class NS061(NamespaceModel):
    with_variables(Var("SERVER_IP", ctxt.model.ippath))
    ippath = channel()


class Service061(ServiceModel):
    infra = Inf061("wibble")
    namespace = NS061("wobble")
    namespace.ippath = ctxt.nexus.svc.infra.server_ip


def test061():
    """
    test061: check that a variable can be populated from a cross-model channel
    """
    svc = Service061("061")
    svc.fix_arguments()
    assert svc.namespace.v.SERVER_IP() == "25.25.25.25", "the ip is {}".format(svc.namespace.v.SERVER_IP())


class Inf062(InfraModel):
    server = StaticServer("test061", ctxt.model.server_ip)
    server_ip = channel()


class NS062(NamespaceModel):
    with_variables(Var("SERVER_IP", "23.23.23.23"))
    ippath = channel(ctxt.model.v.SERVER_IP)


class Service062(ServiceModel):
    infra = Inf062("asdf")
    namespace = NS062("dfg")
    infra.server_ip = ctxt.nexus.svc.namespace.ippath


def test062():
    """
    test062: check that param can be fetched from a var using channels
    """
    service = Service062("test062")
    service.fix_arguments()
    assert service.infra.server.hostname_or_ip.value() == "23.23.23.23", \
        "it was {}".format(service.infra.server.hostname_or_ip.value())


class Infra063(InfraModel):
    svr = StaticServer("wibble", "127.0.0.1")


class NS063(NamespaceModel):
    s = Role("s", host_ref=ctxt.model.svchost)
    svchost = channel()


class Cfg063(ConfigModel):
    t = NullTask("nul063", task_role=ctxt.model.taskrole)
    taskrole = channel()


class Svc063(ServiceModel):
    infra = Infra063("infra")
    namespace = NS063("ns")
    config = Cfg063("cfg")
    namespace.svchost = ctxt.nexus.svc.infra.svr
    config.taskrole = ctxt.nexus.svc.namespace.svchost


def test063():
    """
    test063: initial test of service support for configuration
    """
    eh = CountingTaskEventHandler()
    svc = Svc063("wibble")
    # svc.config.set_event_handler(eh)
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0.0, event_handler=eh)
    result = ao.initiate_system()
    assert result
    assert len(eh.starting) == 2


class NSInner064(NamespaceModel):
    with_variables(Var("QUESTION", ctxt.model.source))
    source = channel()


class SvcInner064(ServiceModel):
    namespace = NSInner064("inner")
    namespace.source = ctxt.nexus.svc.bridge
    bridge = channel()


class NSOuter064(NamespaceModel):
    with_variables(Var("TARGET", "answer"))
    answer = channel(ctxt.model.v.TARGET)


class SvcOuter064(ServiceModel):
    namespace = NSOuter064("outer")
    inner_svc = SvcInner064("inner-svc")
    inner_svc.bridge = ctxt.nexus.parent.svc.namespace.answer


def test064():
    """
    test064: checking that a namespace in a nested service can get a var value from outside
    """
    svc = SvcOuter064("test")
    svc.fix_arguments()
    assert svc.inner_svc.namespace.v.QUESTION() == "answer"


class NSInner065(NamespaceModel):
    role = Role("inner_role", host_ref=ctxt.model.the_host)
    the_host = channel()


class SvcInner065(ServiceModel):
    namespace = NSInner065("inner_ns")
    namespace.the_host = ctxt.nexus.svc.supplied_host
    supplied_host = channel()


class InfraOuter065(InfraModel):
    server = StaticServer("t065outer", "67.67.67.67")


class SvcOuter065(ServiceModel):
    infra = InfraOuter065("outer")
    inner_svc = SvcInner065("inner")
    inner_svc.supplied_host = ctxt.nexus.parent.svc.infra.server


def test065():
    """
    test065: check that a role in a inner svc namespace can get the host from an outer infra
    """
    svc = SvcOuter065("outer")
    svc.fix_arguments()
    assert svc.infra.server.value() is svc.inner_svc.namespace.role.host_ref.value()


class NSInner1_066(NamespaceModel):
    role = Role("inner1", host_ref=ctxt.model.host1)
    host1 = channel()


class ConfigInner1_066(ConfigModel):
    task = NullTask("cfg1_inner", task_role=ctxt.model.role)
    role = channel()


class SvcInner1_066(ServiceModel):
    namespace = NSInner1_066("asfd")
    config = ConfigInner1_066("asdf")
    config.role = ctxt.nexus.svc.namespace.role
    host1 = channel()
    namespace.host1 = ctxt.nexus.svc.host1


class NSInner2_066(NamespaceModel):
    role = Role("inner2", host_ref=ctxt.model.host2)
    host2 = channel()


class ConfigInner2_066(ConfigModel):
    task = NullTask("cfg2_inner", task_role=ctxt.model.role)
    role = channel()


class SvcInner2_066(ServiceModel):
    namespace = NSInner2_066("asfd")
    config = ConfigInner2_066("asdg")
    config.role = ctxt.nexus.svc.namespace.role
    host2 = channel()
    namespace.host2 = ctxt.nexus.svc.host2


class Infra066(InfraModel):
    server = StaticServer("adkfh", "89.89.98.98")


class SvcOuter_066(ServiceModel):
    infra = Infra066("asdfas")
    svc1 = SvcInner1_066("svc1")
    svc2 = SvcInner2_066("svc2")
    svc1.host1 = ctxt.nexus.parent.svc.infra.server
    svc2.host2 = ctxt.nexus.parent.svc.infra.server


def test066():
    """
    test066: checking properly running configs in two sub-services
    """
    eh = CountingTaskEventHandler()
    svc = SvcOuter_066("test066")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    ao.initiate_system()
    assert len(eh.starting) == 3, "{}".format(eh.starting)
    assert svc.svc1.namespace.role.host_ref.value() is svc.svc2.namespace.role.host_ref.value()
    assert svc.svc1.namespace.role.host_ref.value() is svc.infra.server.value()


class Infra067(InfraModel):
    pass


class Service067(ServiceModel):
    pass


def test067():
    """
    test067: raise an exception if we give a service and infra to an orchestrator
    """
    inf = Infra067("infra067")
    svc = Service067("service067")
    try:
        ao = ActuatorOrchestration(infra_model_inst=inf, service=svc)
        assert False, "this should have raised an exception"
    except ExecutionException as _:
        pass


class InfraInner068(InfraModel):
    server = StaticServer("inner_server", "94.04.48.43")


class InnerNS068(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("role068", host_ref=ctxt.model.host)
    host = channel()


class InnerConfig068(ConfigModel):
    task = NullTask("task068", task_role=ctxt.model.role)
    role = channel()


class SvcInner068(ServiceModel):
    infra = InfraInner068("asfd")
    namespace = InnerNS068("dfgb")
    config = InnerConfig068("avzxc")
    namespace.host = ctxt.nexus.inf.server
    config.role = ctxt.nexus.ns.role


class SvcOuter068(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.inner.namespace.v.HAYSTACK))
    inner = SvcInner068("inner")


def test068():
    """
    test068: check service nested in an empty service orchestrates right
    """
    eh = CountingTaskEventHandler()
    svc = SvcOuter068("test068")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert len(eh.starting) == 2, "starting is {}".format(eh.starting)
    assert (svc.inner.config.task.task_role.host_ref.value() is
            svc.inner.infra.server.value())
    assert svc.v.HAYSTACK() == "needle"


class InfraInner069(InfraModel):
    server = StaticServer("inner", "41.41.41.41")


class NSInner069(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("ns069", host_ref=ctxt.model.host)
    host = channel()


class SvcInner069(ServiceModel):
    infra = InfraInner069("inner")
    namespace = NSInner069("inner-ns")
    namespace.host = ctxt.nexus.inf.server


class ConfigOuter069(ConfigModel):
    task = NullTask("task069", task_role=ctxt.model.role)
    role = channel()


class Service069(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.inner.namespace.v.HAYSTACK))
    config = ConfigOuter069("outer069")
    inner = SvcInner069("inner069")
    config.role = ctxt.nexus.svc.inner.namespace.role


def test069():
    """
    test069: check we can link an outer config to an inner namespace
    """
    eh = CountingTaskEventHandler()
    svc = Service069("test069")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert len(eh.starting) == 2, "tasks: {}".format(eh.starting)
    assert (svc.config.task.task_role.host_ref.value() is svc.inner.infra.server.value())
    assert svc.v.HAYSTACK() == "needle"


class NSInner070(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("inner-070", host_ref=ctxt.model.host)
    host = channel()


class SvcInner070(ServiceModel):
    namespace = NSInner070("svc-inner-070")
    namespace.host = ctxt.nexus.svc.host
    host = channel()


class InfraOuter070(InfraModel):
    server = StaticServer("server070", "67.45.64.34")


class ConfigOuter070(ConfigModel):
    task = NullTask("task070", task_role=ctxt.model.role)
    role = channel()


class SvcOuter070(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.inner.namespace.v.HAYSTACK))
    inner = SvcInner070("inner")
    infra = InfraOuter070("outer070")
    config = ConfigOuter070("")
    inner.host = ctxt.nexus.parent.svc.infra.server
    config.role = ctxt.nexus.svc.inner.namespace.role


def test070():
    """
    test070: inner service with just the namespace, outer has config and infra
    """
    eh = CountingTaskEventHandler()
    svc = SvcOuter070("test070")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert svc.config.task.task_role.host_ref.value() is svc.infra.server.value()
    assert svc.v.HAYSTACK() == "needle"


class NSInner071(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("role071", host_ref=ctxt.model.host)
    host = channel()


class ConfigInner071(ConfigModel):
    task = NullTask("task071", task_role=ctxt.model.role)
    role = channel()


class SvcInner071(ServiceModel):
    namespace = NSInner071("ns071")
    config = ConfigInner071("cfg071")
    config.role = ctxt.nexus.svc.namespace.role
    namespace.host = ctxt.nexus.svc.host
    host = channel()


class InfraOuter071(InfraModel):
    server = StaticServer("svr017", "12.12.12.12")


class SvcOuter071(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.inner.namespace.v.HAYSTACK))
    inner = SvcInner071("inner")
    infra = InfraOuter071("infra071")
    inner.host = ctxt.nexus.parent.svc.infra.server


def test071():
    """
    test071: check inner ns/cfg works with outer inf
    """
    eh = CountingTaskEventHandler()
    svc = SvcOuter071("test071")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert svc.inner.config.task.task_role.host_ref.value() is svc.infra.server.value()
    assert svc.v.HAYSTACK() == "needle"


class InfraInner072(InfraModel):
    server = StaticServer("svr072", "13.13.13.13")


class ConfigInner072(ConfigModel):
    task = NullTask("task072", task_role=ctxt.model.role)
    role = channel()


class ServiceInner072(ServiceModel):
    infra = InfraInner072("infra072")
    config = ConfigInner072("config072")
    config.role = ctxt.nexus.svc.role
    role = channel()


class NSOuter072(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("role072", host_ref=ctxt.model.host)
    host = channel()


class ServiceOuter072(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.namespace.v.HAYSTACK))
    inner = ServiceInner072("inner072")
    namespace = NSOuter072("ns072")
    namespace.host = ctxt.nexus.svc.inner.infra.server
    inner.role = ctxt.nexus.parent.svc.namespace.role


def test072():
    """
    test072: infra/cfg in inner service, ns in outer
    """
    eh = CountingTaskEventHandler()
    svc = ServiceOuter072("test072")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert (svc.inner.config.task.task_role.host_ref.value() is svc.inner.infra.server.value())
    assert svc.v.HAYSTACK() == "needle"


class InfraInner073(InfraModel):
    server = StaticServer("server073", "13.13.13.13")


class ServiceInner073(ServiceModel):
    infra = InfraInner073("infra073")
    server = channel(ctxt.model.infra.server)


class NSOuter073(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("role073", host_ref=ctxt.model.host)
    host = channel()


class ConfigOuter073(ConfigModel):
    task = NullTask("task073", task_role=ctxt.nexus.ns.role)


class ServiceOuter073(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.namespace.v.HAYSTACK))
    inner = ServiceInner073("inner073")
    namespace = NSOuter073("ns073")
    config = ConfigOuter073("cfg073")
    namespace.host = ctxt.nexus.svc.inner.infra.server


def test073():
    """
    test073: check that inner inf can be found by outer ns
    """
    eh = CountingTaskEventHandler()
    svc = ServiceOuter073("test073")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert svc.inner.server.value() is svc.config.task.task_role.host_ref.value()
    assert svc.v.HAYSTACK() == "needle"


class ConfigInner074(ConfigModel):
    task = NullTask("task074", task_role=ctxt.model.role)
    role = channel()


class ServiceInner074(ServiceModel):
    config = ConfigInner074("cfg074")
    config.role = ctxt.nexus.svc.role
    role = channel()


class InfraOuter074(InfraModel):
    server = StaticServer("server074", "35.35.35.35")


class NSOuter074(NamespaceModel):
    with_variables(Var("HAYSTACK", "needle"))
    role = Role("role074", host_ref=ctxt.nexus.inf.server)


class ServiceOuter074(ServiceModel):
    with_variables(Var("HAYSTACK", ctxt.model.namespace.v.HAYSTACK))
    inner = ServiceInner074("inner074")
    infra = InfraOuter074("infra074")
    namespace = NSOuter074("ns074")
    inner.role = ctxt.nexus.parent.ns.role


def test074():
    """
    test074: check inner cfg, outer ns/infra
    """
    eh = CountingTaskEventHandler()
    svc = ServiceOuter074("test074")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    assert svc.infra.server.value() is svc.inner.config.task.task_role.host_ref.value()
    assert svc.v.HAYSTACK() == "needle"


class ConfigInner075(ConfigModel):
    task = NullTask("task-inner-075", task_role=ctxt.model.role)
    role = channel()


class InfraInner075(InfraModel):
    server = StaticServer("server075", "127.0.0.1")


class NSInner075(NamespaceModel):
    role = Role("role-inner-075", host_ref=ctxt.model.host)
    host = channel()


class ServiceInner075(ServiceModel):
    infra = InfraInner075("infra075")
    config = ConfigInner075("config-inner-075")
    namespace = NSInner075("ns-inner-075")
    namespace.host = ctxt.nexus.svc.infra.server
    config.role = ctxt.nexus.svc.namespace.role


class ConfigOuter075(ConfigModel):
    task = WaitForTaskTask("task-outer-075", ctxt.model.related)
    related = channel()


class ServiceOuter075(ServiceModel):
    inner = ServiceInner075("inner075")
    config = ConfigOuter075("config075")
    config.related = ctxt.nexus.svc.inner.config.task


def test075():
    """
    test075: wait in one config for a task in another to complete
    """
    eh = CountingTaskEventHandler()
    svc = ServiceOuter075("test075")
    ao = ActuatorOrchestration(service=svc, post_prov_pause=0)
    ao.set_event_handler(eh)
    result = ao.initiate_system()
    assert result
    _ = svc.inner.config.get_dependencies()
    _ = 1


def test076():
    """
    test076: derive a config model from another model
    """
    class BaseConfig(ConfigModel):
        t1 = NullTask("task1")
        t2 = NullTask("task2")
        with_dependencies(t1 | t2)

    class DerivedConfig(BaseConfig):
        pass


##############
# FIXME: INHERITANCE NOT WORKING FOR NAMESPACES OR CONFIGS
##############


def do_all():
    setup_module()
    for k, v in globals().items():
        if callable(v) and k.startswith("test"):
            try:
                v()
            except Exception as e:
                six.print_(">>>>>>>>>> {} failed with {}".format(k, str(e)))


if __name__ == "__main__":
    do_all()
