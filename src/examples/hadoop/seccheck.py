from pprint import pprint as pp
from actuator.reporting import security_check


if __name__ == "__main__":
    # OpenStack trial
    from hadoop import HadoopInfra, HadoopNamespace
    inf = HadoopInfra("Trial")
    ns = HadoopNamespace("ns")
    ns.set_infra_model(inf)
    for i in range(5):
        _ = inf.slaves[i]
    rep = security_check(inf)
    print("OpenStack:")
    pp(rep)

    # Azure trial
    from azurehadoop import AzureExample
    ae = AzureExample("azure")
    for i in range(5):
        _ = ae.slaves[i]
    rep = security_check(ae)
    print("\nAzure")
    pp(rep)
