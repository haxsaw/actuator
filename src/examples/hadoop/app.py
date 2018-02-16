
from actuator import Service, ctxt
from actuator.namespace import with_variables, Var

from hadoop import HadoopInfra, HadoopNamespace, HadoopConfig


class HadoopApp(Service):
    with_variables(Var("WIBBLE", "hiya"))
    infra = HadoopInfra
    namespace = HadoopNamespace
    config = HadoopConfig
    summat = 1


class OuterService(Service):
    with_services(hadoop=HadoopApp,
                  db=DBService,
                  db_backup=DBService)
    infra = SummatElseInfra
    namespace = SummatElseNamespace
    config = SummatElseConfig


class DatabaseService(Service):
    infra = DBInfra(...)
    namespace = DBNamespace(...)
    config = DBConfig(...)


class MsgAreaService(Service):
    with_variables(Var("DBHOST", None),
                   Var("DBADMINUSER", None),
                   Var("DBADMINPWD", None),
                   Var("DBMSGUSER", "msguser"),
                   Var("DBMSGPWD", "msgpwd"))
    infra = MAInfra(...)
    namespace = MANamespace()
    config = MAConfig(...)


class OSRMService(Service):
    with_variables(Var("DBHOST", None),
                   Var("DBADMINUSER", None),
                   Var("DBADMINPWD", None),
                   Var("DBOSRMUSER", "msguser"),
                   Var("DBOSRMPWD", "msgpwd"))
    infra = OSRMInfra(...)
    namespace = OSRMNamespace(...)
    config = OSRMConfig(...)


class MatrixApp(Application):
    with_variables(Var("DBHOST", ctxt.nexus.app.db.infra.server.hostname_or_ip),
                   Var("DBADMINUSER", "bigshot"),
                   Var("DBADMINPWD", "wibble"))
    db = DatabaseService
    msg = MsgAreaService
    osrm = OSRMService

    db_config = ctxt.nexus.app.db.config
    msg_config = ctxt.nexus.app.msg.config
    osrm_config = ctxt.nexus.app.osrm.config




if __name__ == "__main__":
    ha = HadoopApp("hadoop", infra_args=[("h-infra",), {}],
                   namespace_args=[("h-namespace",), {}],
                   config_args=[("h-config",), {}])
    # ha.infra
    # ha.namespace
    # ha.config
    HadoopApp.infra.name_node
    ha.find_variable("WIBBLE")
    ha.namespace.find_variable("WIBBLE")
    x1 = ha.namespace.name_node
    x2 = HadoopApp.namespace.name_node
    _ = 1
