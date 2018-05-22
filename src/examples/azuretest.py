import sys
import traceback
from actuator.provisioners.azure.resources import AzResourceGroup
from actuator.infra import InfraModel
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator import ActuatorOrchestration


class AzureExample(InfraModel):
    arg = AzResourceGroup("azure_example", "westus")


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
