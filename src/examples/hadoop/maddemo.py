from pprint import pprint
from traceback import print_exception
import sys
from actuator import ctxt, ActuatorOrchestration
from actuator.infra import MultiResourceGroup, with_infra_options
from actuator.namespace import Role, MultiRole, NamespaceModel, with_variables, Var
from actuator.config import ConfigModel, ConfigClassTask, MultiTask, with_dependencies
from actuator.config_tasks import ShellTask, CommandTask
from actuator.provisioners.vsphere.resources import Datastore, ResourcePool, TemplatedServer
from actuator.provisioners.vsphere import VSphereProvisionerProxy
from actuator.provisioners.aws.resources import (KeyPair, SecurityGroup, SecurityGroupRule,
                                                 NetworkInterface, AWSInstance, PublicIP)
from actuator.provisioners.aws import AWSProvisionerProxy
from awshadoop import AWSBase
from actuator.provisioners.azure.resources import (AzNetwork, AzPublicIP, AzSubnet,
                                                   AzResourceGroup, AzSecurityGroup, AzSecurityRule,
                                                   AzServer, AzNIC)
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.utils import find_file
from actuator.reporting import security_check
from hcommon import common_vars, HadoopNodeConfig, host_list
from prices import create_price_table, AZURE, AWS, VSPHERE

# some shortcuts for Azure
rempass = "C0rnD0ggi3"
parent = ctxt.comp.container
common_server_args = dict(publisher="Canonical",
                          offer="UbuntuServer",
                          sku="16.04.0-LTS",
                          version="latest",
                          # vm_size='Standard_DS1_v2',
                          vm_size='Standard_B1S',
                          admin_user="ubuntu",
                          admin_password=rempass,
                          pub_key_file=find_file("actuator-dev-key.pub"))


class KitchenSinkInfra(AWSBase):
    with_infra_options(long_names=True)

    #
    # AWS bits
    kp = KeyPair("wibble", public_key_file="actuator-dev-key.pub")
    # custom security groups and rules
    nn_access_sg = SecurityGroup("namenode-access",
                                 "rules that allow the namenode to contact these slaves",
                                 ctxt.model.vpc)
    jobtrkr_rule = SecurityGroupRule("jobtracker",
                                     ctxt.model.nn_access_sg,
                                     "ingress",
                                     ctxt.model.name_node_fip.get_cidr4,
                                     50031, 50031,
                                     "tcp")

    slaves = MultiResourceGroup("slaves",
                                ni=NetworkInterface("slave-ni",
                                                    ctxt.model.sn,
                                                    description="something pith",
                                                    sec_groups=[ctxt.model.base_sg,
                                                                ctxt.model.nn_access_sg]),
                                slave=AWSInstance("slave",
                                                  "ami-0f27df5f159bccfba",
                                                  instance_type='t3.nano',
                                                  key_pair=ctxt.model.kp,
                                                  network_interfaces=[ctxt.comp.container.ni]),
                                slave_fip=PublicIP("slave-eip",
                                                   domain="vpc",
                                                   network_interface=ctxt.comp.container.ni)
                                )

    #
    # VSphere bits
    name_node_ds = Datastore("namenode_ds", dspath="VMDATA1")
    name_node_rp = ResourcePool("namenode_rp", pool_name="new dell")
    name_node_fip = TemplatedServer("namenode", template_name="ActuatorBase8",
                                    data_store=ctxt.model.name_node_ds,
                                    resource_pool=ctxt.model.name_node_rp)

    #
    # Azure bits
    # resource groups
    slave_rsrc = AzResourceGroup("hadoop_slaves", "westus")
    # network
    network = AzNetwork("ex_net", ctxt.model.slave_rsrc, ["10.0.0.0/16"])
    subnet = AzSubnet("sn", ctxt.model.slave_rsrc, ctxt.model.network, "10.0.0.0/24")
    # security
    sshrule = AzSecurityRule("sshrule", "tcp", "inbound", "22", "allow", 101, description="thingie")
    zabbix = AzSecurityRule("zabbix-host", "tcp", "inbound", "10050", "allow", 102, description="Zabbix access")
    jt_webui_rule = AzSecurityRule("jobtracker_webui", "tcp", "inbound", "50030", "allow", 105, description="jt webui")
    nn_to_slave_rule = AzSecurityRule("nnToSlave", "tcp", "inbound", "50031", "allow", 107,
                                      description="nn command rule",
                                      source_address_prefix=ctxt.model.name_node_fip.get_cidr4)
    sl_sg = AzSecurityGroup("slave-seggroup", ctxt.model.slave_rsrc, [ctxt.model.sshrule,
                                                                      ctxt.model.zabbix,
                                                                      ctxt.model.nn_to_slave_rule,
                                                                      ctxt.model.jt_webui_rule])

    # slaves
    az_slaves = MultiResourceGroup(
        "slave",
        slave_fip=AzPublicIP("pub-server", ctxt.model.slave_rsrc),
        nic=AzNIC("ex_nic", ctxt.model.slave_rsrc, ctxt.model.network, [ctxt.model.subnet],
                  public_ip=parent.slave_fip),
        slave=AzServer("ex-server", ctxt.model.slave_rsrc, [parent.nic], **common_server_args)
    )


class KitchenSinkNamespace(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.az_slaves, ctxt.model.aws_slaves)),
                   Var("NAMENODE_IP", ctxt.nexus.inf.name_node_fip.get_ip))
    with_variables(Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                   Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False))

    name_node = Role("name_node",
                     host_ref=ctxt.nexus.inf.name_node_fip)
    aws_slaves = MultiRole(Role("aws_slave",
                                host_ref=ctxt.nexus.inf.slaves[ctxt.name].slave_fip,
                                variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                           Var("COMP_KEY", ctxt.name)]
                                )
                           )
    az_slaves = MultiRole(Role("az_slave",
                               host_ref=ctxt.nexus.inf.az_slaves[ctxt.name].slave_fip,
                               variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                          Var("COMP_KEY", ctxt.name)]
                               )
                          )

    def create_slaves(self, count):
        """
        creates an equal number of slaves across both clouds
        :param count: int; 1/2 the number of the total slaves to create
        :return: list of refs to the slaves
        """
        return [self.aws_slaves[i] for i in range(count)] + [self.az_slaves[i] for i in range(count)]


class KitchenSinkConfig(ConfigModel):
    namenode_setup = ConfigClassTask("nn_suite", HadoopNodeConfig, init_args=("namenode-setup",),
                                     task_role=ctxt.nexus.ns.name_node)
    az_slaves_setup = MultiTask("az_slaves_setup",
                                ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("az-slave-setup",)),
                                KitchenSinkNamespace.q.az_slaves.all())
    aws_slaves_setup = MultiTask("aws_slaves_setup",
                                 ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("aws-slave-setup",)),
                                 KitchenSinkNamespace.q.aws_slaves.all())
    slave_ips = ShellTask("slave_ips",
                          "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                          " > !{HADOOP_CONF_DIR}/slaves",
                          task_role=ctxt.nexus.ns.name_node)
    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=ctxt.nexus.ns.name_node)
    with_dependencies(namenode_setup | format_hdfs)
    with_dependencies((namenode_setup & az_slaves_setup & aws_slaves_setup) | slave_ips)


def do_it():
    from hevent import TaskEventManager
    ehandler = TaskEventManager()
    slave_count = 1

    # azure creds
    with open("azurecreds.txt", "r") as f:
        subid, cliid, sec, ten = f.readline().strip().split(",")
    azure_proxy = AzureProvisionerProxy("azure",
                                        subscription_id=subid,
                                        client_id=cliid,
                                        secret=sec,
                                        tenant=ten)

    # aws creds
    key, secret = open("awscreds.txt", "r").read().strip().split("|")
    aws_proxy = AWSProvisionerProxy("hadoopproxy", default_region="eu-west-2",
                                    aws_access_key=key, aws_secret_access_key=secret)

    # vsphere creds
    line = open("vscreds.txt", "r").readline().strip()
    h, u, p = line.split(",")
    vs_proxy = VSphereProvisionerProxy("vsphere", host=h, username=u, pwd=p)

    # build the models and orchestrator
    inf = KitchenSinkInfra("one-with-everything")
    ns = KitchenSinkNamespace("whats-in-a-name")
    _ = ns.create_slaves(slave_count)
    cfg = KitchenSinkConfig("where-do-you-want-it-lady", remote_user="ubuntu",
                            private_key_file=find_file("actuator-dev-key"))

    ao = ActuatorOrchestration(infra_model_inst=inf,
                               namespace_model_inst=ns,
                               config_model_inst=cfg,
                               provisioner_proxies=[azure_proxy,
                                                    aws_proxy,
                                                    vs_proxy],
                               event_handler=ehandler,
                               num_threads=3*slave_count+3,
                               post_prov_pause=10
                               )

    # orchestrate!
    try:
        ao.initiate_system()
    except Exception as e:
        print("init failed with {}".format(str(e)))
    else:
        try:
            print(">>>> SECURITY ANALYSIS:")
            pprint(security_check(inf))
        except Exception as e:
            print("...sec check printout failed with:")
            print_exception(*sys.exc_info())
        try:
            price_tables = [(cloud, create_price_table(inf, cloud)) for cloud in (VSPHERE, AZURE, AWS)]
            print("\n>>>> PRICING:")
            for cloud, pt in price_tables:
                print(cloud)
                print(pt)
                print()
        except Exception as e:
            print("...price table computation failed with:")
            print_exception(*sys.exc_info())

    print("running; hit return to tear down")
    sys.stdin.readline()

    try:
        ao.teardown_system()
    except Exception as e:
        print("teardown failed with {}".format(str(e)))


if __name__ == "__main__":
    do_it()
