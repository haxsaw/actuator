#
# Copyright (c) 2018 Tom Carroll
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
import sys
import traceback
from actuator import *
from actuator.provisioners.azure.resources import *
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.infra import *
from actuator.utils import find_file
from hcommon import HadoopNamespace, HadoopNodeConfig, common_vars, host_list
from awshadoop import AWSTrialInfra


model = ctxt.model
parent = ctxt.comp.container

common_server_args = dict(publisher="Canonical",
                          offer="UbuntuServer",
                          sku="16.04.0-LTS",
                          version="latest",
                          vm_size='Standard_DS1_v2',
                          admin_user="ubuntu",
                          pub_key_file=find_file("actuator-dev-key.pub"))


class AzureAWSInfra(AWSTrialInfra):
    with_infra_options(long_names=True)
    rg = AzResourceGroup("hm3-rg", "westus")
    network = AzNetwork("hm3-network", model.rg, ["10.0.0.0/16"])
    subnet = AzSubnet("hm3-subnet", model.rg, model.network, "10.0.0.0/24")
    az_slaves = MultiResourceGroup(
        "slave",
        slave_fip=AzPublicIP("pub-server", model.rg),
        nic=AzNIC("slave-nic", model.rg, model.network, [model.subnet],
                  public_ip=parent.slave_fip),
        slave=AzServer("slave-server", model.rg, [parent.nic], **common_server_args)
    )
    sshrule = AzSecurityRule("sshrule", "tcp", "inbound", "22", "allow", 101, description="thingie")
    nn_rule = AzSecurityRule("nnrule", "tcp", "inbound", "50031", "allow", 102,
                             description="wibble",
                             source_address_prefix=model.name_node_fip.get_cidr4)
    azsg = AzSecurityGroup("secgroup", model.rg, [model.sshrule, model.nn_rule])


class AzureAWSNamespace(HadoopNamespace):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.az_slaves, ctxt.model.slaves)),
                   Var("NAMENODE_IP", ctxt.nexus.inf.name_node_fip.get_ip))
    with_variables(Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                   Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False))

    az_slaves = MultiRole(Role("az-slave",
                               host_ref=ctxt.nexus.inf.az_slaves[ctxt.name].slave_fip,
                               variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                          Var("COMP_KEY", ctxt.name)]))

    def create_az_slaves(self, count):
        return [self.az_slaves[i] for i in range(count)]


class AzureAWSHadoopConfig(ConfigModel):
    namenode_setup = ConfigClassTask("nn_suite", HadoopNodeConfig, init_args=("namenode-setup",),
                                     task_role=AzureAWSNamespace.name_node)

    az_slaves_setup = MultiTask("az_slaves_setup",
                                ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("az-slave-setup",)),
                                AzureAWSNamespace.q.az_slaves.all())

    aws_slaves_setup = MultiTask("aws_slaves_setup",
                                 ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("slave-setup",)),
                                 AzureAWSNamespace.q.slaves.all())

    slave_ips = ShellTask("slave_ips",
                          "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                          " > !{HADOOP_CONF_DIR}/slaves",
                          task_role=AzureAWSNamespace.name_node)

    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=AzureAWSNamespace.name_node)

    with_dependencies(namenode_setup | format_hdfs)
    with_dependencies((namenode_setup & az_slaves_setup & aws_slaves_setup) | slave_ips)


if __name__ == "__main__":
    from hevent import TaskEventManager
    ehandler = TaskEventManager()

    with open("azurecreds.txt", "r") as f:
        subid, cliid, sec, ten = f.readline().strip().split(",")
    azure = AzureProvisionerProxy("azure",
                                  subscription_id=subid,
                                  client_id=cliid,
                                  secret=sec,
                                  tenant=ten)

    key, secret = open("awscreds.txt", "r").read().strip().split("|")
    aws_proxy = AWSProvisionerProxy("hadoopproxy", default_region="eu-west-2",
                                    aws_access_key=key, aws_secret_access_key=secret)

    inf = AzureAWSInfra("multi3")
    numslaves = 4
    ns = AzureAWSNamespace("az-aws-ns")
    ns.create_slaves(numslaves)
    ns.create_az_slaves(numslaves+1)
    cfg = AzureAWSHadoopConfig("az-aws-cfg", remote_user="ubuntu",
                               private_key_file=find_file("actuator-dev-key"))

    ao = ActuatorOrchestration(infra_model_inst=inf,
                               namespace_model_inst=ns,
                               config_model_inst=cfg,
                               provisioner_proxies=[aws_proxy, azure],
                               num_threads=2*numslaves*3 + 3,
                               post_prov_pause=10,
                               no_delay=True,
                               event_handler=ehandler)
    try:
        ao.initiate_system()
    except Exception as e:
        print("init failed with %s" % str(e))
        traceback.print_exception(*sys.exc_info())

    print("Hit return to deprovision...")
    sys.stdin.readline()

    try:
        ao.teardown_system()
    except Exception as e:
        print("teardown failed with %s" % str(e))
        traceback.print_exception(*sys.exc_info())
