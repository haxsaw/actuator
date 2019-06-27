from actuator import InfraModel, NamespaceModel, StaticServer, Role, MultiRole, Var, ctxt
from support018saved import x


class Infra018(InfraModel):
    s = StaticServer("server", "127.0.0.1")


class Namespace018(NamespaceModel):
    dudes = MultiRole(Role("dude", host_ref=ctxt.nexus.inf.s,
                           variables=[Var("WHOMP", "dere it is")]
                           )
                      )

    def make_dudes(self, num_dudes):
        for i in range(int(num_dudes)):
            _ = self.dudes[i]


