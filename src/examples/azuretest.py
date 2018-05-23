import sys
import traceback
from actuator.provisioners.azure.resources import (AzResourceGroup, AzNetwork, AzSubnet,
                                                   AzNIC)
from actuator.infra import InfraModel
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator import ActuatorOrchestration, ctxt


class AzureExample(InfraModel):
    arg = AzResourceGroup("azure_example", "westus")
    network = AzNetwork("ex_net", ctxt.model.arg, ["10.0.0.0/16"])
    subnet = AzSubnet("sn",
                      ctxt.model.arg,
                      ctxt.model.network,
                      "10.0.0.0/24")
    nic = AzNIC("ex_nic", ctxt.model.arg, ctxt.model.network, [ctxt.model.subnet])


if __name__ == "__main__":
    with open("azurecreds.txt", "r") as f:
        subid, cliid, sec, ten = f.readline().strip().split(",")
    app = AzureProvisionerProxy("azure",
                                subscription_id=subid,
                                client_id=cliid,
                                secret=sec,
                                tenant=ten)
    inf = AzureExample("azample")
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
