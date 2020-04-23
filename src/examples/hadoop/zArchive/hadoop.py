# 
# Copyright (c) 2014 Tom Carroll
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

from actuator import *  # @UnusedWildImport
from actuator.provisioners.openstack.resources import *  # @UnusedWildImport
from hcommon import common_vars, HadoopNodeConfig, pkn
from zArchive.zabbix_agent import zabbix_agent_secgroup
from actuator.utils import find_file
from prices import (CORES1_MEM0_5_STO20, CORES2_MEM2_STO50)

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


def make_std_secgroup(name, desc="standard security group", cloud=None):
    """
    Returns a standarized resource group with rules for ping and ssh access.
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
    

def host_list(ctx_exp, sep_char=" "):
    """
    This returns a callable that computes a list of ip addresses separated by
    the indicated character. This is one approach to constructing
    callable arguments that Actuator will invoke when it is needed.
    
    In this case, the ctx_exp is expected to return a dict-like object when
    "called" with the Actuator-supplied CallContext (the 'ctx' argument to
    host_list_inner()), in this case a MultiRole. We ask for the values() of
    that object to get the list of roles in the dict.
    """
    def host_list_inner(ctx):
        return sep_char.join([role.host_ref.get_ip()
                              for role in ctx_exp(ctx).values()
                              if role is not None])
    return host_list_inner


class HadoopNamespace(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.slaves)),
                   Var("NAMENODE_IP", ctxt.nexus.inf.name_node_fip.get_ip))
    # set up cloud parameters
    with_variables(Var("IMAGE", "Ubuntu 14.04 - LTS - Trusty Tahr"),
                   Var("EXTNET", "ext-net"),
                   Var("AZ", "Lon1"))
    
    name_node = Role("name_node",
                     host_ref=ctxt.nexus.inf.name_node_fip)
    slaves = MultiRole(Role("slave",
                            host_ref=ctxt.nexus.inf.slaves[ctxt.name].slave_fip,
                            variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                       Var("COMP_KEY", ctxt.name)]))
    
    def create_slaves(self, count):
        """
        This method takes care of the creating the references to additional
        slave Roles, which in turn creates more slave infra resources.
        """
        return [self.slaves[i] for i in range(count)]
    

class HadoopConfig(ConfigModel):
    namenode_setup = ConfigClassTask("nn_suite", HadoopNodeConfig, init_args=("namenode-setup",),
                                     task_role=HadoopNamespace.name_node)

    slaves_setup = MultiTask("slaves_setup",
                             ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("slave-setup",)),
                             HadoopNamespace.q.slaves.all())

    slave_ips = ShellTask("slave_ips",
                          "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                          " > !{HADOOP_CONF_DIR}/slaves",
                          task_role=HadoopNamespace.name_node)

    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=HadoopNamespace.name_node)

    with_dependencies(namenode_setup | format_hdfs)
    with_dependencies((namenode_setup & slaves_setup) | slave_ips)
