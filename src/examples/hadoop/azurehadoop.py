import sys
import traceback
from actuator.provisioners.azure.resources import (AzResourceGroup, AzNetwork, AzSubnet,
                                                   AzNIC, AzServer, AzPublicIP, AzSecurityRule,
                                                   AzSecurityGroup)
from actuator.infra import InfraModel, with_infra_options, MultiResourceGroup
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator import ActuatorOrchestration, ctxt, Var
from hcommon import HadoopNamespace, HadoopConfig
from prices import AZURE
from hcommon import DemoPlatform


parent = ctxt.comp.container

rempass = "C0rnD0ggi3"

common_server_args = dict(publisher="Canonical",
                          offer="UbuntuServer",
                          sku="16.04.0-LTS",
                          version="latest",
                          # vm_size='Standard_DS1_v2',
                          vm_size='Standard_B1S',
                          admin_user="ubuntu",
                          admin_password=rempass)


class AzureExample(InfraModel):
    with_infra_options(long_names=True)

    # resource groups
    net_rsrc = AzResourceGroup("hadoop_network", "westus")
    slave_rsrc = AzResourceGroup("hadoop_slaves", "westus")
    nn_rsrc = AzResourceGroup("hadoop_namenode", "westus")
    # network
    network = AzNetwork("ex_net", ctxt.model.net_rsrc, ["10.0.0.0/16"])
    subnet = AzSubnet("sn", ctxt.model.net_rsrc, ctxt.model.network, "10.0.0.0/24")
    # security
    sshrule = AzSecurityRule("sshrule", "tcp", "inbound", "22", "allow", 101, description="thingie")
    zabbix = AzSecurityRule("zabbix-host", "tcp", "inbound", "10050", "allow", 102, description="Zabbix access")
    nn_webui_rule = AzSecurityRule("nn_webui", "tcp", "inbound", "50070", "allow", 103, description="nn webui")
    nn_rule = AzSecurityRule("nn", "tcp", "inbound", "50071", "allow", 104, description="namenode")
    jt_webui_rule = AzSecurityRule("jobtracker_webui", "tcp", "inbound", "50030", "allow", 105, description="jt webui")
    jt_rule = AzSecurityRule("jobtracker", "tcp", "inbound", "50031", "allow", 106, description="job tracker")
    nn_to_slave_rule = AzSecurityRule("nnToSlave", "tcp", "inbound", "50031", "allow", 107,
                                      description="nn command rule",
                                      source_address_prefix=ctxt.model.name_node.get_cidr4)
    sl_sg = AzSecurityGroup("slave-seggroup", ctxt.model.slave_rsrc, [ctxt.model.sshrule,
                                                                      ctxt.model.zabbix,
                                                                      ctxt.model.nn_to_slave_rule])
    nn_sg = AzSecurityGroup("namenode-seggroup", ctxt.model.nn_rsrc, [ctxt.model.sshrule,
                                                                      ctxt.model.zabbix,
                                                                      ctxt.model.nn_webui_rule,
                                                                      ctxt.model.nn_rule,
                                                                      ctxt.model.jt_webui_rule,
                                                                      ctxt.model.jt_rule])
    # slaves
    slaves = MultiResourceGroup(
        "slave",
        slave_fip=AzPublicIP("pub-server", ctxt.model.slave_rsrc),
        nic=AzNIC("ex_nic", ctxt.model.slave_rsrc, ctxt.model.network, [ctxt.model.subnet],
                  public_ip=parent.slave_fip),
        slave=AzServer("ex-server", ctxt.model.slave_rsrc, [parent.nic], **common_server_args)
    )
    # name node
    nn_nic = AzNIC("nn_nic", ctxt.model.nn_rsrc, ctxt.model.network, [ctxt.model.subnet],
                   public_ip=ctxt.model.name_node_fip)
    name_node_fip = AzPublicIP("name-node-fip", ctxt.model.nn_rsrc)
    name_node = AzServer("name-node", ctxt.model.nn_rsrc, [ctxt.model.nn_nic], **common_server_args)


class AzureDemo(DemoPlatform):
    def get_infra_instance(self, inst_name):
        return AzureExample(inst_name)

    def get_platform_proxy(self):
        with open("azurecreds.txt", "r") as f:
            subid, cliid, sec, ten = f.readline().strip().split(",")
        app = AzureProvisionerProxy("azure",
                                    subscription_id=subid,
                                    client_id=cliid,
                                    secret=sec,
                                    tenant=ten)
        return app

    def get_supplemental_vars(self):
        return [Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)]

    def get_infra_class(self):
        return AzureExample

    def platform_name(self):
        return AZURE

    def get_config_kwargs(self):
        return dict(pkf=None, rempass=rempass)


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

    inf = AzureExample("azample")

    ns = HadoopNamespace("azure-ns")
    ns.add_override(Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                    Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False))
    num_slaves = 0
    ns.create_slaves(num_slaves)
    #
    ns.set_infra_model(inf)

    cfg = HadoopConfig("azure-config", remote_pass=rempass, remote_user="ubuntu")

    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 namespace_model_inst=ns,
                                 # config_model_inst=cfg,
                                 provisioner_proxies=[app],
                                 post_prov_pause=10,
                                 num_threads=num_slaves*3+3,
                                 no_delay=True,
                                 event_handler=ehandler)
    try:
        orch.initiate_system()
    except Exception as e:
        print("init failed with %s" % str(e))
        traceback.print_exception(*sys.exc_info())

    from actuator.utils import persist_to_dict
    import json
    import traceback
    import sys
    try:
        d = persist_to_dict(orch)
        dp = json.loads(json.dumps(d))
    except:
        traceback.print_exception(*sys.exc_info())

    print("Hit return to deprovision...")
    sys.stdin.readline()
    try:
        orch.teardown_system()
    except Exception as e:
        print("traceback failed with %s")
        traceback.print_exception(*sys.exc_info())

    print("all done")
