from actuator import ctxt
from actuator.infra import InfraModel, ResourceGroup, MultiResourceGroup, with_infra_options
from actuator.provisioners.openstack.resources import *  # @UnusedWildImport
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.utils import find_file
from prices import (CORES1_MEM0_5_STO20, CORES2_MEM2_STO50, CITYCLOUD)
from hcommon import pkn, DemoPlatform

# This ResourceGroup is boilerplate for making Openstack resources available
# externally. They are created outside an infra model to illustrate that they
# can be factored out into a shared module of reusable components.
external_connection = ResourceGroup("route_out",
                                    net=Network("ro_net"),
                                    subnet=Subnet("ro_subnet",
                                                  ctxt.comp.container.net,
                                                  u"192.168.23.0/24",
                                                  dns_nameservers=[u'8.8.8.8']),
                                    router=Router("ro_router"),
                                    gateway=RouterGateway("ro_gateway",
                                                          ctxt.comp.container.router,
                                                          ctxt.nexus.ns.v.EXTNET),
                                    interface=RouterInterface("ro_inter",
                                                              ctxt.comp.container.router,
                                                              ctxt.comp.container.subnet))


zabbix_agent_secgroup = ResourceGroup("zabbix_rsrcs",
                                      zabbix_group=SecGroup("zabbix", "ZabbixGroup"),
                                      zabbix_tcp_rule=SecGroupRule("zabbix_tcp_rule",
                                                                   ctxt.comp.container.zabbix_group,
                                                                   ip_protocol="tcp",
                                                                   from_port=10050,
                                                                   to_port=10050)
                                      )


def make_std_secgroup(name, desc="standard security group", cloud=None):
    """
    Returns a standarised resource group with rules for ping and ssh access.
    The returned resource can be further configured with additional rules by the
    caller.

    The name parameter is used to form the name of the ResourceGroup, and also
    provides the name of the SecGroup that is created in the ResourceGroup.
    """
    return ResourceGroup("%s_std_secgroup" % name,
                         group=SecGroup(name, desc, cloud=cloud),
                         ping_rule=SecGroupRule("ping_rule",
                                                ctxt.comp.container.group,
                                                ip_protocol="icmp",
                                                from_port=-1, to_port=-1,
                                                cloud=cloud),
                         ssh_rule=SecGroupRule("ssh_rule",
                                               ctxt.comp.container.group,
                                               ip_protocol="tcp",
                                               from_port=22, to_port=22,
                                               cloud=cloud),
                         )


# name of the image we want to use
# ubuntu_img = "ubuntu14.04-LTS"


# common keyword args used for servers
common_kwargs = {"key_name": ctxt.model.kp}


def get_flavor(cc):
    """
    This function illustrates how any arbitrary callable can be used to acquire
    values for a Var. The callable will be invoked when the value for a variable is
    required, and is passed an instance of actuator.modeling.CallContext which describes
    the context from which the Var is being evaluated. For Vars, the callable should return
    a string.

    This example simply returns a hard-coded value, but it could alternatively consult an
    external data source for the value to return.

    :param cc: an instance of actuator.modeling.CallContext
    :return: string; the flavor to use
    """
    if cc.nexus.inf.cloud == "citycloud":
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


class HadoopInfra(InfraModel):
    with_infra_options(long_names=True)
    fip_pool = "public"  # attributes that aren't resources are ignored
    # add the standard slave_secgroup and connectivity components
    slave_secgroup = make_std_secgroup("slave_sg", desc="For Hadoop slaves")
    zabbix_sg = zabbix_agent_secgroup
    gateway = external_connection

    kp = KeyPair(pkn, pkn, pub_key_file=find_file("%s.pub" % pkn))

    # create an additional secgroup for the namenode
    namenode_secgroup = make_std_secgroup("namenode_sg", desc="For Hadoop namenode")
    # add additional rules specific to the Hadoop namenode secgroup
    # note that we pick up the port numbers from the namespace model via a context expression;
    # they could be hard-coded here, but by taking them from the namespace they can be changed on
    # an instance by instance basis
    jobtracker_webui_rule = SecGroupRule("jobtracker_webui_rule",
                                         ctxt.model.namenode_secgroup.group,
                                         ip_protocol="tcp",
                                         from_port=ctxt.nexus.ns.v.JOBTRACKER_WEBUI_PORT,
                                         to_port=ctxt.nexus.ns.v.JOBTRACKER_WEBUI_PORT)
    namenode_webui_rule = SecGroupRule("namenode_webui_rule",
                                       ctxt.model.namenode_secgroup.group,
                                       ip_protocol="tcp",
                                       from_port=ctxt.nexus.ns.v.NAMENODE_WEBUI_PORT,
                                       to_port=ctxt.nexus.ns.v.NAMENODE_WEBUI_PORT)
    jobtracker_rule = SecGroupRule("jobtracker_rule",
                                   ctxt.model.namenode_secgroup.group,
                                   ip_protocol="tcp",
                                   from_port=ctxt.nexus.ns.v.JOBTRACKER_PORT,
                                   to_port=ctxt.nexus.ns.v.JOBTRACKER_PORT)
    namenode_rule = SecGroupRule("namenode_rule",
                                 ctxt.model.namenode_secgroup.group,
                                 ip_protocol="tcp",
                                 from_port=ctxt.nexus.ns.v.NAMENODE_PORT,
                                 to_port=ctxt.nexus.ns.v.NAMENODE_PORT)

    # HADOOP name node
    name_node = Server("name_node", ctxt.nexus.ns.v.IMAGE,
                       get_flavor,
                       security_groups=[ctxt.model.namenode_secgroup.group,
                                        ctxt.model.zabbix_sg.zabbix_group],
                       nics=[ctxt.model.gateway.net],
                       **common_kwargs)
    name_node_fip = FloatingIP("name_node_fip", ctxt.model.name_node,
                               ctxt.model.name_node.iface0.addr0,
                               pool=ctxt.nexus.ns.v.EXTNET)
    # HADOOP slaves
    slaves = MultiResourceGroup("slaves",
                                slave=Server("slave", ctxt.nexus.ns.v.IMAGE,
                                             get_flavor,
                                             nics=[ctxt.model.gateway.net],
                                             security_groups=[ctxt.model.slave_secgroup.group,
                                                              ctxt.model.zabbix_sg.zabbix_group],
                                             **common_kwargs),
                                slave_fip=FloatingIP("sn_fip",
                                                     ctxt.comp.container.slave,
                                                     ctxt.comp.container.slave.iface0.addr0,
                                                     pool=ctxt.nexus.ns.v.EXTNET))

    def __init__(self, name, cloud="citycloud", **kwargs):
        super(HadoopInfra, self).__init__(name, **kwargs)
        self.cloud = cloud


class OpenstackDemo(DemoPlatform):
    def get_infra_instance(self, inst_name):
        return HadoopInfra(inst_name)

    def get_platform_proxy(self):
        return OpenStackProvisionerProxy(cloud_name="citycloud")

    def get_supplemental_vars(self):
        return []

    def get_infra_class(self):
        return HadoopInfra

    def platform_name(self):
        return CITYCLOUD
