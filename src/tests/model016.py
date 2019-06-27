from actuator import InfraModel, NamespaceModel, StaticServer, Role, MultiRole, Var, ctxt


class Infra016(InfraModel):
    s = StaticServer("server", "127.0.0.1")


class Namespace016(NamespaceModel):
    dudes = MultiRole(Role("dude", host_ref=ctxt.nexus.inf.s,
                           variables=[Var("WHOMP", "dere it is")]
                           )
                      )

