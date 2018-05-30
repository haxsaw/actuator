import sys
from actuator.modeling import ctxt
from actuator.infra import InfraModel, ResourceGroup, MultiResourceGroup, with_infra_options
from actuator.namespace import NamespaceModel, with_variables, Var, Role, MultiRole, MultiRoleGroup
from actuator.config import ConfigModel, with_dependencies
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.vsphere.resources import *
from actuator.provisioners.vsphere import VSphereProvisionerProxy
from actuator.utils import find_file
from hadoop import (make_std_secgroup, CORES2_MEM2_STO50, CORES1_MEM0_5_STO20)
from hadoop_node import (common_vars, pkn, HadoopNodeConfig, CommandTask, ShellTask,
                         MultiTask, ConfigClassTask)
from actuator import ActuatorOrchestration

double_cont_name = ctxt.comp.container.container.name

triple_cont_name = ctxt.comp.container.container.container.name


def get_flavor(cc):
    if cc.comp.container.container.container.name.value() == "citycloud":
        if cc.comp is not None and isinstance(cc.comp.value(), Provisionable):
            if "name" in cc.comp.get_display_name():
                result = CORES1_MEM0_5_STO20
            else:
                result = CORES2_MEM2_STO50
        else:
            result = ""
    else:  # assume Auro
        result = "standard.2"
    return result


# names of gateway networks at various providers
netnames = {"citycloud": "ext-net",
            "auro": "provider"}


def getnet(cex):
    def gn(c):
        name = cex.name
        return netnames[name(c).value()]
    return gn


# names of the images to use at various providers
images = {"citycloud": "Ubuntu 14.04 - LTS - Trusty Tahr",
          "auro": "Ubuntu16.04-x86_64-20180223"}


def getimage(c):
    pre = c.comp.container.container.container
    name = pre.name
    return images[name.value()]


class MultiCloudInfra(InfraModel):
    """
    This infrastructure will spread Hadoop slaves over an arbitrary set of Openstack clouds,
    with a namenode on VSphere
    """
    datastore1 = "VMDATA1"
    datastore2 = "DATA"
    all_datastores = [datastore1, datastore2]
    with_infra_options(long_names=True)

    slave_cloud = MultiResourceGroup("",
                         slave_secgroup=make_std_secgroup("slave_sg",
                                                          desc="For Hadoop slaves",
                                                          cloud=double_cont_name),
                         jt_sgr=SecGroupRule("jt_sgr",
                                             secgroup=ctxt.comp.container.slave_secgroup.group,
                                             ip_protocol="tcp", from_port=50031, to_port=50031,
                                             cidr=ctxt.model.name_node_fip.get_cidr4,
                                             cloud=ctxt.comp.container.name),
                         kp=KeyPair(pkn, pkn, pub_key_file=find_file("%s.pub" % pkn), cloud=ctxt.comp.container.name),
                         gateway=ResourceGroup("route_out",
                                               net=Network("ro_net", cloud=double_cont_name),
                                               subnet=Subnet("ro_subnet",
                                                             ctxt.comp.container.net,
                                                             u"192.168.23.0/24",
                                                             dns_nameservers=[u'8.8.8.8'],
                                                             cloud=double_cont_name),
                                               router=Router("ro_router", cloud=double_cont_name),
                                               gateway=RouterGateway("ro_gateway",
                                                                     ctxt.comp.container.router,
                                                                     getnet(ctxt.comp.container.container),
                                                                     cloud=double_cont_name),
                                               interface=RouterInterface("ro_inter",
                                                                         ctxt.comp.container.router,
                                                                         ctxt.comp.container.subnet,
                                                                         cloud=double_cont_name)
                                               ),
                         slaves=MultiResourceGroup("slaves",
                                                   slave=Server("slave",
                                                                getimage,
                                                                get_flavor,
                                                                nics=[ctxt.comp.container.container.container.gateway
                                                                      .net],
                                                                security_groups=[ctxt.comp.container.container
                                                                                 .container.slave_secgroup.group],
                                                                cloud=triple_cont_name,
                                                                key_name=ctxt.comp.container.container.container.kp
                                                                ),
                                                   slave_fip=FloatingIP("sn_fip",
                                                                        ctxt.comp.container.slave,
                                                                        ctxt.comp.container.slave.iface0.addr0,
                                                                        pool=getnet(ctxt.comp.container.container
                                                                                    .container),
                                                                        cloud=triple_cont_name)
                                                   ),
                         namesep="")

    name_node_ds = Datastore("namenode_ds", dspath=datastore1, cloud="vsphere")
    name_node_rp = ResourcePool("namenode_rp", pool_name="new dell", cloud="vsphere")
    name_node_fip = TemplatedServer("namenode", template_name="ActuatorBase6",
                                    data_store=ctxt.model.name_node_ds,
                                    resource_pool=ctxt.model.name_node_rp, cloud="vsphere")

    def make_slaves(self, cloudname, num):
        # this is only needed for isolation testing; normally driven from namespace
        for i in range(num):
            _ = self.slave_cloud[cloudname].slaves[i]


def host_list(ctxexp, sep_char=" "):
    def host_list_inner(ctx):
        ips = []
        for k in ctxexp(ctx).keys():
            for role in ctxexp(ctx)[k].slaves.values():
                if role:
                    ips.append(role.host_ref.get_ip())
        return sep_char.join([ip for ip in ips if ip])
    return host_list_inner

# we need to replace some of the common vars we imported
common_vars = [cv for cv in common_vars if cv.name not in {"JAVA_HOME", "JAVA_VER"}]


def pick_java_home(c):
    if c.comp.name.value() == "name_node":
        cloud = "vsphere"
    else:
        cloud = double_cont_name(c).value()
    jh = "/usr/lib/jvm/java-7-openjdk-amd64" if cloud == "citycloud" else "/usr/lib/jvm/java-8-openjdk-amd64"
    return jh


def pick_java_ver(c):
    if c.comp.name.value() == "name_node":
        cloud = "vsphere"
    else:
        cloud = double_cont_name(c).value()
    jv = "openjdk-7-jre-headless" if cloud == "citycloud" else "openjdk-8-jre-headless"
    return jv

common_vars.append(Var("JAVA_HOME", pick_java_home))
common_vars.append(Var("JAVA_VER", pick_java_ver))


class MultiCloudNS(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.slave_clouds)),
                   Var("NAMENODE_IP", ctxt.nexus.inf.name_node_fip.get_ip))

    name_node = Role("name_node", host_ref=ctxt.nexus.inf.name_node_fip)
    slave_clouds = MultiRoleGroup("",
                         slaves=MultiRole(
                             Role("slave",
                                  host_ref=ctxt.nexus.inf.slave_cloud[double_cont_name].slaves[ctxt.name].slave_fip,
                                  variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                             Var("COMP_KEY", ctxt.name)])
                         ),
                         namesep=""
    )

    def make_slaves(self, cloudname, num):
        for i in range(num):
            _ = self.slave_clouds[cloudname].slaves[i]


class MultiCloudConfig(ConfigModel):
    select_all = MultiCloudNS.q.union(MultiCloudNS.q.name_node,
                                      MultiCloudNS.q.slave_clouds.all().slaves.all())

    node_setup = MultiTask("node_setup",
                           ConfigClassTask("setup_suite", HadoopNodeConfig,
                                           init_args=("node-setup",)),
                           select_all)
    slave_ip = ShellTask("slave_ips",
                         "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                         " > !{HADOOP_CONF_DIR}/slaves",
                         task_role=MultiCloudNS.name_node)
    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=MultiCloudNS.name_node)
    with_dependencies(node_setup | (slave_ip & format_hdfs))


if __name__ == "__main__":
    from hevent import TaskEventManager

    # make cloud provisioner proxies
    auro = OpenStackProvisionerProxy("auro")
    city = OpenStackProvisionerProxy("citycloud")
    line = open("vscreds.txt", "r").readline().strip()
    h, u, p = line.split(",")
    vs = VSphereProvisionerProxy("vsphere", host=h, username=u, pwd=p)

    # make the visualisation event manager
    handler = TaskEventManager()

    # make the infrastructure model instance
    infra = MultiCloudInfra("multi", event_handler=handler)

    # make the namespace model instance, create some slaves in different clouds
    ns = MultiCloudNS("multi-ns")
    ns.make_slaves("citycloud", 10)
    # ns.make_slaves("auro", 2)

    # make the config model instance
    cloud_creds = {"vsphere": {"remote_pass": "tarnished99"},
                   "auro": {"private_key_file": find_file("actuator-dev-key")},
                   "citycloud": {"private_key_file": find_file("actuator-dev-key")}}
    config = MultiCloudConfig("multi-config",
                              event_handler=handler,
                              remote_user="ubuntu",
                              cloud_creds=cloud_creds)

    # build the orchestrator and go
    ao = ActuatorOrchestration(infra_model_inst=infra,
                               namespace_model_inst=ns,
                               config_model_inst=config,
                               provisioner_proxies=[auro, city, vs],
                               num_threads=30,
                               post_prov_pause=10,
                               no_delay=True)
    try:
        success = ao.initiate_system()
    except KeyboardInterrupt:
        ao.teardown_system()
    except Exception as e:
        import traceback, sys
        print("Faild with %s" % str(e))
        print(">>>>Traceback:")
        traceback.print_exception(*sys.exc_info())
    else:
        print("slaves at:", ns.var_value("SLAVE_IPS"))
        print("type ctrl-d to tear down: ",)
        sys.stdin.read()
        ao.teardown_system()
