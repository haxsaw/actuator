import sys
from actuator import ActuatorOrchestration, ctxt
from actuator.provisioners.vsphere.resources import *
from actuator.infra import (InfraModel, MultiResourceGroup, with_infra_options)
from actuator.provisioners.vsphere.resource_tasks import VSphereProvisioner
from actuator.namespace import Var
from hevent import TaskEventManager
from hsimple import do_it


class VSHadoopInfra(InfraModel):
    with_infra_options(long_names=True)

    name_node_ds = Datastore("namenode_ds", dspath="datastore1 (7)")
    name_node_rp = ResourcePool("namenode_rp", pool_name="new dell")
    name_node_fip = TemplatedServer("namenode", template_name="ActuatorBase",
                                    data_store=ctxt.model.name_node_ds,
                                    resource_pool=ctxt.model.name_node_rp)

    slaves = MultiResourceGroup("slaves",
                                slave_ds=Datastore("slave_ds", dspath="datastore1 (7)"),
                                slave_rp=ResourcePool("slave_rp", pool_name="new dell"),
                                slave_fip=TemplatedServer("slave", template_name="ActuatorBase",
                                                          data_store=ctxt.comp.container.slave_ds,
                                                          resource_pool=ctxt.comp.container.slave_rp))

    def make_slaves(self, num):
        for i in range(num):
            _ = self.slaves[0]


if __name__ == "__main__":
    line = open("vscreds.txt", "r").readline().strip()
    h, u, p = line.split(",")
    prov = VSphereProvisioner(host=h, username=u, pwd=p)
    success, inf, ns, conf, orch = do_it(1, handler=TaskEventManager(), pkf=None,
                                         rempass="tarnished99", infra_class=VSHadoopInfra,
                                         provisioner=prov,
                                         overrides=[Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                                                    Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)])
    assert isinstance(orch, ActuatorOrchestration)
    print("hit ctrl-d to deprovision")
    sys.stdin.read()
    orch.teardown_system()
