import json
import six
from nose import SkipTest
from errator import reset_all_narrations, set_default_options
from actuator import Service, ctxt, MultiResource, ActuatorException, ActuatorOrchestration
from actuator.namespace import with_variables, Var, NamespaceModel, Role
from actuator.infra import InfraModel, StaticServer
from actuator.config import ConfigModel, NullTask
from actuator.modeling import ModelReference, ModelInstanceReference, channel, CallContext
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.provisioners.openstack.resources import (SecGroup, SecGroupRule)
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.provisioners.core import ProvisioningTaskEngine


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


class TestSvc(Service):
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
        class T19a(Service):
            infra = 1
        assert False, "this should have raised with infra = 1"
    except Exception as e:
        assert "'infra' attribute" in str(e)
    try:
        class T19b(Service):
            infra = TestNamespace
        assert False, "this should have raised with infra = TestNamespace"
    except Exception as e:
        assert "'infra' attribute" in str(e)


def test20():
    """
    test20: check we can tell when we have the wrong kind of value for the namespace class attr
    """
    try:
        class T20a(Service):
            namespace = 1
        assert False, "this should have raised with namespace = 1"
    except Exception as e:
        assert "'namespace' attribute" in str(e)
    try:
        class T20b(Service):
            namespace = TestInfra
        assert False, "this should have raised with namespace = TestNamespace"
    except Exception as e:
        assert "'namespace' attribute" in str(e)


def test21():
    """
    test21: check we can tell when we have the wrong kind of value for the config class attr
    """
    try:
        class T21a(Service):
            config = 1
        assert False, "this should have raised with config = 1"
    except Exception as e:
        assert "'config' attribute" in str(e)
    try:
        class T21b(Service):
            config = TestInfra
        assert False, "this should have raised with config = TestNamespace"
    except Exception as e:
        assert "'config' attribute" in str(e)
    try:
        class T21c(Service):
            config = TestNamespace("wibble")
        assert False, "this should have raised with config = TestInfra('wibble')"
    except Exception as e:
        assert "'config' attribute" in str(e)


def test022():
    """
    test022: Nest a service inside another service, connect them using Vars and context exprs
    """
    class T22(Service):
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
    class T23(Service):
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
    class T24(Service):
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
    class T25(Service):
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


class T26(Service):
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


class BaseService(Service):
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


class BaseService32(Service):
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


class BaseService33(Service):
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


class BaseService34(Service):
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


class ExposeViaVar(Service):
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


class IPSupplierSvc(Service):
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


class Service37(Service):
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


class Outer42(Service):
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


class SubSvc1(Service):
    infra = SubInfra1("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2(Service):
    infra = SubInfra2("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc43(Service):
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


class SubSvc1_046(Service):
    infra = SubInfra1_046("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2_046(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2_046(Service):
    infra = SubInfra2_046("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc046(Service):
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
    # of the Rule and the Service. Since the Service is dependent on the Server, the net effect
    # is the same. An open question is whether we should make argument resolution also
    # chain through
    sgr = SecGroupRule("rest", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_ip)
    allowed_ip = channel()
    svr = StaticServer("server047", ctxt.model.allowed_ip)


class Svc047(Service):
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


class Svc048(Service):
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


class Svc049(Service):
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


class Svc050(Service):
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


class SubSvc1_051(Service):
    infra = SubInfra1_051("sub1")
    the_cidr = channel(ctxt.model.infra.my_cidr)


class SubInfra2_051(InfraModel):
    sg = SecGroup("wibble")
    sgr = SecGroupRule("restriction", ctxt.model.sg,
                       from_port=5000, to_port=5000,
                       cidr=ctxt.model.allowed_peer)
    allowed_peer = channel()


class SubSvc2_051(Service):
    infra = SubInfra2_051("sub2")
    infra.allowed_peer = ctxt.nexus.svc.conn_pt
    conn_pt = channel()


class Svc051(Service):
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


class DeepBaseSvc_052(Service):
    infra = BaseInfra052("deepinfra")


class BaseSvc1_052(Service):
    dbs = DeepBaseSvc_052("dbs1")


class BaseSvc2_052(Service):
    infra = BaseInfra052("annuder")


class FinalSvc_052(Service):
    svc1 = BaseSvc1_052("svc1")
    svc2 = BaseSvc2_052("svc2")


def test052():
    """
    test052: check that we can find all the services in a nested collection of services
    """
    s = FinalSvc_052("final")

    def all_svcs(i):
        assert isinstance(i, Service)
        svcs = [i]
        for c in i.contained_services():
            svcs.extend(all_svcs(c))
        return svcs

    thesvcs = all_svcs(s)
    assert len(thesvcs) == 4, "the services are: {}".format(thesvcs)


class SvcInfra1_053(InfraModel):
    sg = SecGroup("sg053")


class Svc1_053(Service):
    infra = SvcInfra1_053("sg")


class SvcInfra2_053(InfraModel):
    sgr = SecGroupRule("sgr053", ctxt.nexus.svc.thesg, ip_protocol="tcp",
                       from_port=5000, to_port=5000,
                       cidr="127.0.0.1/32")


class Svc2_053(Service):
    infra = SvcInfra2_053("sgr053")
    thesg = channel()


class TopSvc_053(Service):
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


def do_all():
    setup_module()
    test052()
    for k, v in globals().items():
        if callable(v) and k.startswith("test"):
            try:
                v()
            except Exception as e:
                six.print_(">>>>>>>>>> {} failed with {}".format(k, str(e)))


if __name__ == "__main__":
    do_all()
