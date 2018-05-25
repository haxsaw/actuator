import sys
import traceback
from actuator.provisioners.azure.resources import (AzResourceGroup, AzNetwork, AzSubnet,
                                                   AzNIC, AzServer, AzPublicIP, AzSecurityRule,
                                                   AzSecurityGroup)
from actuator.infra import InfraModel, with_infra_options, MultiResourceGroup
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator import ActuatorOrchestration, ctxt

# keydata = open("azuretestkey.pub", "r").read()


class AzureExample(InfraModel):
    with_infra_options(long_names=True)
    arg = AzResourceGroup("azure_example", "westus")
    network = AzNetwork("ex_net", ctxt.model.arg, ["10.0.0.0/16"])
    subnet = AzSubnet("sn",
                      ctxt.model.arg,
                      ctxt.model.network,
                      "10.0.0.0/24")
    slaves = MultiResourceGroup(
        "slave",
        pub_server=AzPublicIP("pub-server", ctxt.model.arg),
        nic=AzNIC("ex_nic", ctxt.model.arg, ctxt.model.network, [ctxt.model.subnet],
                  public_ip=ctxt.comp.container.pub_server),
        server=AzServer("ex-server", ctxt.model.arg, [ctxt.comp.container.nic],
                        publisher="Canonical",
                        offer="UbuntuServer",
                        sku="16.04.0-LTS",
                        version="latest",
                        vm_size='Standard_DS1_v2',
                        admin_user="ubuntu",
                        admin_password="C0rnD0ggi3")
    )

    sshrule = AzSecurityRule("sshrule", "tcp", "inbound", "22", "allow", 101, description="fingie")
    sg = AzSecurityGroup("ex-seggroup", ctxt.model.arg, [ctxt.model.sshrule])


if __name__ == "__main__":
    with open("azurecreds.txt", "r") as f:
        subid, cliid, sec, ten = f.readline().strip().split(",")
    app = AzureProvisionerProxy("azure",
                                subscription_id=subid,
                                client_id=cliid,
                                secret=sec,
                                tenant=ten)
    inf = AzureExample("azample")
    for i in range(2):
        _ = inf.slaves[i]
    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 provisioner_proxies=[app],)
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
