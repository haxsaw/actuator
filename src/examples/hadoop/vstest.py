#
# Copyright (c) 2017 Tom Carroll
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from actuator.provisioners.vsphere.resources import (Datastore,
                                                     ResourcePool,
                                                     TemplatedServer)
from actuator.infra import (InfraModel, MultiResourceGroup, with_infra_options)
from actuator import ctxt


class VSHadoopInfra(InfraModel):
    datastore1 = "VMDATA1"
    datastore2 = "DATA"
    # datastore1 = datastore2 = "datastore1 (6)"
    with_infra_options(long_names=True)

    name_node_ds = Datastore("namenode_ds0", dspath=datastore1)
    name_node_rp = ResourcePool("namenode_rp0", pool_name="new dell")
    name_node_fip = TemplatedServer("namenode0", template_name="ActuatorBase3",
                                    data_store=ctxt.model.name_node_ds,
                                    resource_pool=ctxt.model.name_node_rp)

    slaves = MultiResourceGroup("slaves",
                                slave_ds=Datastore("slave_ds", dspath=datastore2),
                                slave_rp=ResourcePool("slave_rp", pool_name="new dell"),
                                slave_fip=TemplatedServer("slave", template_name="ActuatorBase3",
                                                          data_store=ctxt.comp.container.slave_ds,
                                                          resource_pool=ctxt.comp.container.slave_rp))

    def make_slaves(self, num):
        for i in range(num):
            _ = self.slaves[0]


if __name__ == "__main__":
    import sys
    from actuator import ActuatorOrchestration
    from actuator.provisioners.vsphere.resource_tasks import VSphereProvisioner
    from actuator.namespace import Var
    from hevent import TaskEventManager
    from hsimple import do_it

    line = open("vscreds.txt", "r").readline().strip()
    h, u, p = line.split(",")
    prov = VSphereProvisioner(host=h, username=u, pwd=p)
    success, inf, ns, conf, orch = do_it(2, handler=TaskEventManager(), pkf=None,
                                         rempass="tarnished99", infra_class=VSHadoopInfra,
                                         provisioner=prov,
                                         overrides=[Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                                                    Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)])
    assert isinstance(orch, ActuatorOrchestration)
    print("hit ctrl-d to deprovision")
    sys.stdin.read()
    orch.teardown_system()
