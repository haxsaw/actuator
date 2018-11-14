import sys
from pprint import pprint
from actuator import ActuatorOrchestration, ctxt, Var
from actuator.infra import InfraModel, MultiResourceGroup, with_infra_options
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.provisioners.aws.resources import *
from actuator.utils import find_file
from hevent import TaskEventManager
from hcommon import HadoopNamespace, HadoopConfig
from actuator.reporting import security_check
from hcommon import DemoPlatform
from prices import AWS


class AWSBase(InfraModel):
    vpc = VPC("base-vpc",
              "192.168.1.0/24")
    base_sg = SecurityGroup("base-sg",
                            "a common sg to build on",
                            ctxt.model.vpc)
    ping_rule = SecurityGroupRule("test rule",
                                  ctxt.model.base_sg,
                                  "ingress",
                                  "0.0.0.0/0",
                                  -1,
                                  -1,
                                  "icmp")
    ssh_rule = SecurityGroupRule("sshrule",
                                 ctxt.model.base_sg,
                                 "ingress",
                                 "0.0.0.0/0",
                                 22, 22,
                                 "tcp")
    zabbix_rule = SecurityGroupRule("zabbix-rule",
                                    ctxt.model.base_sg,
                                    "ingress",
                                    "0.0.0.0/0",
                                    10050,
                                    10050,
                                    "tcp")
    sn = Subnet("base subnet",
                "192.168.1.0/24",
                ctxt.model.vpc)
    igw = InternetGateway("base gw",
                          ctxt.model.vpc)
    rt = RouteTable("base rt",
                    ctxt.model.vpc,
                    ctxt.model.sn)
    r = Route("base route",
              ctxt.model.rt,
              dest_cidr_block="0.0.0.0/0",
              gateway=ctxt.model.igw)


class AWSTrialInfra(AWSBase):
    with_infra_options(long_names=True)

    kp = KeyPair("wibble", public_key_file="actuator-dev-key.pub")
    # custom security groups and rules
    namenode_sg = SecurityGroup("namenode-sg", "special rules to contact the name node", ctxt.model.vpc)
    jobtrkr_webui_rule = SecurityGroupRule("jobtracker-webui",
                                           ctxt.model.namenode_sg,
                                           "ingress",
                                           "0.0.0.0/0",
                                           50030, 50030,
                                           "tcp")
    namenode_webui_rule = SecurityGroupRule("namenode-webui",
                                            ctxt.model.namenode_sg,
                                            "ingress",
                                            "0.0.0.0/0",
                                            50070, 50070,
                                            "tcp")
    jobtrkr_rule = SecurityGroupRule("jobtracker",
                                     ctxt.model.namenode_sg,
                                     "ingress",
                                     "0.0.0.0/0",
                                     50031, 50031,
                                     "tcp")
    namenode_rule = SecurityGroupRule("namenode",
                                      ctxt.model.namenode_sg,
                                      "ingress",
                                      "0.0.0.0/0",
                                      50071, 50071,
                                      "tcp")

    # add some rules to the base SG

    slaves = MultiResourceGroup("slaves",
                                ni=NetworkInterface("slave-ni",
                                                    ctxt.model.sn,
                                                    description="something pith",
                                                    sec_groups=[ctxt.model.base_sg,
                                                                ctxt.model.namenode_sg]),
                                slave=AWSInstance("slave",
                                                  "ami-0f27df5f159bccfba",
                                                  instance_type='t3.nano',
                                                  key_pair=ctxt.model.kp,
                                                  network_interfaces=[ctxt.comp.container.ni]),
                                slave_fip=PublicIP("slave-eip",
                                                   domain="vpc",
                                                   network_interface=ctxt.comp.container.ni)
                                )
    ni = NetworkInterface("name_node-ni",
                          ctxt.model.sn,
                          description="something pith",
                          sec_groups=[ctxt.model.base_sg,
                                      ctxt.model.namenode_sg])
    name_node = AWSInstance("name_node",
                            "ami-0f27df5f159bccfba",
                            instance_type='t3.nano',
                            key_pair=ctxt.model.kp,
                            network_interfaces=[ctxt.model.ni])
    name_node_fip = PublicIP("name_node_fip",
                             domain="vpc",
                             network_interface=ctxt.model.ni)


class AWSDemo(DemoPlatform):
    def get_infra_instance(self, inst_name):
        return AWSTrialInfra(inst_name)

    def get_platform_proxy(self):
        key, secret = open("awscreds.txt", "r").read().strip().split("|")
        aws_proxy = AWSProvisionerProxy("hadoopproxy", default_region="eu-west-2",
                                        aws_access_key=key, aws_secret_access_key=secret)
        return aws_proxy

    def get_supplemental_vars(self):
        return [Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)]

    def get_infra_class(self):
        return AWSTrialInfra

    def platform_name(self):
        return AWS


def doit():
    key, secret = open("awscreds.txt", "r").read().strip().split("|")
    aws_proxy = AWSProvisionerProxy("hadoopproxy", default_region="eu-west-2",
                                    aws_access_key=key, aws_secret_access_key=secret)
    i = AWSTrialInfra("trial")

    ns = HadoopNamespace("aws-ns")
    ns.add_override(Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                    Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False))
    ns.create_slaves(3)

    cfg = HadoopConfig("aws-config", remote_user="ubuntu",
                       private_key_file=find_file("actuator-dev-key"))

    ao = ActuatorOrchestration(infra_model_inst=i,
                               namespace_model_inst=ns,
                               config_model_inst=cfg,
                               provisioner_proxies=[aws_proxy],
                               event_handler=TaskEventManager(),
                               num_threads=10,
                               post_prov_pause=10)
    try:
        ao.initiate_system()
    except Exception as e:
        print("init failed with {}".format(str(e)))

    print("running; hit return to tear down:")
    sys.stdin.readline()

    try:
        ao.teardown_system()
    except Exception as e:
        print("teardown failed with {}".format(str(e)))

    result = security_check(i)
    pprint(result)


if __name__ == "__main__":
    doit()
