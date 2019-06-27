from actuator import InfraModel, NamespaceModel, StaticServer, Role, MultiRole, Var, ctxt


class Infra035(InfraModel):
    s = StaticServer("server", "127.0.0.1")


class Namespace035(NamespaceModel):
    dudes = MultiRole(Role("dude", host_ref=ctxt.nexus.inf.s,
                           variables=[Var("WHOMP", "dere it is")]
                           )
                      )

    def __init__(self, *args, **kwargs):
        super(Namespace035, self).__init__(*args, **kwargs)

    def make_dudes(self, num_dudes):
        for i in range(int(num_dudes)):
            _ = self.dudes[i]
        self.invoke_undefined_method()
