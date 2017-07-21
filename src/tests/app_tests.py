import json
from actuator import Service, ctxt
from actuator.namespace import with_variables, Var, NamespaceModel, Role
from actuator.infra import InfraModel, StaticServer
from actuator.config import ConfigModel, NullTask
from actuator.modeling import ModelReference, ModelInstanceReference
from actuator.utils import persist_to_dict, reanimate_from_dict


class AppInfra(InfraModel):
    server = StaticServer("server", ctxt.nexus.app.v.SERVER_IP)


class AppNamespace(NamespaceModel):
    with_variables(Var("NS-GLOBAL", "global"))

    role = Role("role", host_ref=ctxt.nexus.inf.server,
                variables=[Var("NS_LOCAL", "local"),
                           Var("buried2", None)])


class AppConfig(ConfigModel):
    task = NullTask("task", task_role=ctxt.nexus.ns.role)


class AppApp(Service):
    server_ip = ctxt.nexus.app.infra.server.hostname_or_ip
    with_variables(Var("WIBBLE", "hiya"),
                   Var("buried", server_ip),
                   Var("SERVER_IP", "127.0.0.1"))
    infra = AppInfra
    namespace = AppNamespace
    config = AppConfig
    non_model = 1


def get_simple_instance():
    return AppApp("appapp", infra=[["infra"], {}],
                  namespace=[["namespace"], {}],
                  config=[["config"], {}])


def test001():
    """
    test001: check that we get proper refs for app class attributes
    """
    assert isinstance(AppApp.infra, ModelReference), "infra isn't a model reference"
    assert isinstance(AppApp.namespace, ModelReference), "namespace isn't a model reference"
    assert isinstance(AppApp.config, ModelReference), "config isn't a model reference"
    assert isinstance(AppApp.non_model, int), "non_model isn't a plain value"


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
    test004: check being able to express a path to a component as a context expr on the app
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
    assert pargs == ("appapp",)


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


def test17():
    """
    test017: basic persistence check
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    d = persist_to_dict(a)
    a_clone = reanimate_from_dict(d)
    assert a.name == a_clone.name
    assert a._infra == a_clone._infra
    assert a._namespace == a_clone._namespace
    assert a._config == a_clone._config
    assert a.namespace.role.name.value() == a_clone.namespace.role.name.value()
    assert a.infra.server.name.value() == a_clone.infra.server.name.value()
    assert a.config.task.name.value() == a_clone.config.task.name.value()
    assert a.infra.server.hostname_or_ip.value() == a_clone.infra.server.hostname_or_ip.value()


def test18():
    """
    test018: checking persisted form goes to json and back
    """
    a = get_simple_instance()
    a.infra.server.fix_arguments()
    d = persist_to_dict(a)
    d_prime = json.loads(json.dumps(d))
    a_clone = reanimate_from_dict(d_prime)
    assert a.name == a_clone.name
    assert a._infra == a_clone._infra
    assert a._namespace == a_clone._namespace
    assert a._config == a_clone._config
    assert a.namespace.role.name.value() == a_clone.namespace.role.name.value()
    assert a.infra.server.name.value() == a_clone.infra.server.name.value()
    assert a.config.task.name.value() == a_clone.config.task.name.value()
    assert a.infra.server.hostname_or_ip.value() == a_clone.infra.server.hostname_or_ip.value()


def do_all():
    for k, v in globals().items():
        if callable(v) and k.startswith("test"):
            try:
                v()
            except Exception as e:
                print ">>>>>>>>>> {} failed with {}".format(k, str(e))


if __name__ == "__main__":
    do_all()
