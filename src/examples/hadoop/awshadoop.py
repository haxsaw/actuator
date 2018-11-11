import sys
from actuator import ActuatorOrchestration, ctxt, Var
from actuator.infra import InfraModel, MultiResourceGroup, with_infra_options
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.provisioners.aws.resources import *
from actuator.utils import find_file
from hevent import TaskEventManager
from hadoop import HadoopNamespace, HadoopConfig


class AWSBase(InfraModel):
    vpc = VPC("base-vpc",
              "192.168.1.0/24")
    sg = SecurityGroup("base-sg",
                       "a common sg to build on",
                       ctxt.model.vpc)
    ping_rule = SecurityGroupRule("test rule",
                                  ctxt.model.sg,
                                  "ingress",
                                  "0.0.0.0/0",
                                  -1,
                                  -1,
                                  "icmp")
    ssh_rule = SecurityGroupRule("sshrule",
                                 ctxt.model.sg,
                                 "ingress",
                                 "0.0.0.0/0",
                                 22, 22,
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
    slaves = MultiResourceGroup("slaves",
                                ni=NetworkInterface("slave-ni",
                                                    ctxt.model.sn,
                                                    description="something pith",
                                                    sec_groups=[ctxt.model.sg]),
                                slave=AWSInstance("slave",
                                                  "ami-0f27df5f159bccfba",
                                                  instance_type='t2.nano',
                                                  key_pair=ctxt.model.kp,
                                                  network_interfaces=[ctxt.comp.container.ni]),
                                slave_fip=PublicIP("slave-eip",
                                                   domain="vpc",
                                                   network_interface=ctxt.comp.container.ni)
                                )
    ni = NetworkInterface("name_node-ni",
                          ctxt.model.sn,
                          description="something pith",
                          sec_groups=[ctxt.model.sg])
    name_node = AWSInstance("name_node",
                            "ami-0f27df5f159bccfba",
                            instance_type='t2.nano',
                            key_pair=ctxt.model.kp,
                            network_interfaces=[ctxt.comp.container.ni])
    name_node_fip = PublicIP("name_node_fip",
                             domain="vpc",
                             network_interface=ctxt.comp.container.ni)


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


if __name__ == "__main__":
    doit()
