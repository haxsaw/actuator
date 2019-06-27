from actuator import InfraModel, NamespaceModel, StaticServer, Role, MultiRole, Var, ctxt


class Infra034(InfraModel):
    s = StaticServer("server", "127.0.0.1")


class Namespace034(NamespaceModel):
    dudes = MultiRole(Role("dude", host_ref=ctxt.nexus.inf.s,
                           variables=[Var("WHOMP", "dere it is")]
                           )
                      )

    def __init__(self, *args, **kwargs):
        super(Namespace034, self).__init__(*args, **kwargs)
        self.invoke_undefined_method()

    def make_dudes(self, num_dudes):
        for i in range(int(num_dudes)):
            _ = self.dudes[i]
        # self.invoke_undefined_method()


