import json
import six
from nose import SkipTest
from errator import reset_all_narrations, set_default_options
from actuator import Service, ctxt, expose
from actuator.namespace import with_variables, Var, NamespaceModel, Role
from actuator.infra import InfraModel, StaticServer
from actuator.config import ConfigModel, NullTask
from actuator.modeling import ModelReference, ModelInstanceReference
from actuator.utils import persist_to_dict, reanimate_from_dict


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
    # @FIXME
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
    theip = expose(ctxt.nexus.svc.infra.server.hostname_or_ip)
    namespace = NamespaceModel


def test031():
    """
    test031: try deriving one service from another
    """
    fs = FinalService("fs", infra_args=(('baseinfra',), {}))
    fs.fix_arguments()
    # assert isinstance(fs.server, ModelInstanceReference), "fs.server isn't a ref: {}".format(fs.server)
    assert fs.theip == "127.0.0.1", "theip is {}".format(fs.theip)


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
