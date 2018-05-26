import sys
import traceback
from actuator.provisioners.azure.resources import (AzResourceGroup, AzNetwork, AzSubnet,
                                                   AzNIC, AzServer, AzPublicIP, AzSecurityRule,
                                                   AzSecurityGroup)
from actuator.infra import InfraModel, with_infra_options, MultiResourceGroup
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator import ActuatorOrchestration, ctxt, Var
from hadoop import HadoopNamespace, HadoopConfig

# keydata = open("azuretestkey.pub", "r").read()

parent = ctxt.comp.container

rempass = "C0rnD0ggi3"


class AzureExample(InfraModel):
    with_infra_options(long_names=True)

    arg = AzResourceGroup("azure_example", "westus")
    network = AzNetwork("ex_net", ctxt.model.arg, ["10.0.0.0/16"])
    subnet = AzSubnet("sn",
                      ctxt.model.arg,
                      ctxt.model.network,
                      "10.0.0.0/24")
    sshrule = AzSecurityRule("sshrule", "tcp", "inbound", "22", "allow", 101, description="fingie")
    sg = AzSecurityGroup("ex-seggroup", ctxt.model.arg, [ctxt.model.sshrule])

    slaves = MultiResourceGroup(
        "slave",
        slave_fip=AzPublicIP("pub-server", ctxt.model.arg),
        nic=AzNIC("ex_nic", ctxt.model.arg, ctxt.model.network, [ctxt.model.subnet],
                  public_ip=parent.slave_fip),
        slave=AzServer("ex-server", ctxt.model.arg, [parent.nic],
                       publisher="Canonical",
                       offer="UbuntuServer",
                       sku="16.04.0-LTS",
                       version="latest",
                       vm_size='Standard_DS1_v2',
                       admin_user="ubuntu",
                       admin_password=rempass)
    )

    nn_nic = AzNIC("nn_nic", ctxt.model.arg, ctxt.model.network, [ctxt.model.subnet],
                   public_ip=ctxt.model.name_node_fip)
    name_node_fip = AzPublicIP("name-node-fip", ctxt.model.arg)
    name_node = AzServer("name-node", ctxt.model.arg, [ctxt.model.nn_nic],
                         publisher="Canonical",
                         offer="UbuntuServer",
                         sku="16.04.0-LTS",
                         version="latest",
                         vm_size='Standard_DS1_v2',
                         admin_user="ubuntu",
                         admin_password=rempass)


if __name__ == "__main__":
    from hevent import TaskEventManager
    ehandler = TaskEventManager()

    with open("azurecreds.txt", "r") as f:
        subid, cliid, sec, ten = f.readline().strip().split(",")
    app = AzureProvisionerProxy("azure",
                                subscription_id=subid,
                                client_id=cliid,
                                secret=sec,
                                tenant=ten)

    inf = AzureExample("azample", event_handler=ehandler)

    ns = HadoopNamespace("azure-ns")
    ns.add_override(Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                    Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False))
    ns.create_slaves(2)

    cfg = HadoopConfig("azure-config", remote_pass=rempass, remote_user="ubuntu", event_handler=ehandler)

    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 namespace_model_inst=ns,
                                 config_model_inst=cfg,
                                 provisioner_proxies=[app],
                                 post_prov_pause=10,
                                 num_threads=10)
    try:
        orch.initiate_system()
    except Exception as e:
        print("init failed with %s" % str(e))
        traceback.print_exception(*sys.exc_info())

    print("Hit return to deprovision...")
    sys.stdin.readline()
    try:
        orch.teardown_system()
    except Exception as e:
        print("traceback failed with %s")
        traceback.print_exception(*sys.exc_info())

    print("all done")
