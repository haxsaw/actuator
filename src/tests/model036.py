from actuator import InfraModel, NamespaceModel, StaticServer, Role, MultiRole, Var, ctxt


class Infra036(InfraModel):
    s = StaticServer("server", "127.0.0.1")


class Namespace036(NamespaceModel):
    dudes = MultiRole(Role("dude", host_ref=ctxt.nexus.inf.s,
                           variables=[Var("WHOMP", "dere it is")]
                           )
                      )
    non_multi_role = Role("don't index me bro", host_ref=ctxt.nexus.inf.s)

    def __init__(self, *args, **kwargs):
        super(Namespace036, self).__init__(*args, **kwargs)

    def make_dudes(self, num_dudes):
        for i in range(int(num_dudes)):
            _ = self.dudes[i]
