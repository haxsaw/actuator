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

from actuator import *
from actuator.provisioners.openstack.resources import *
from hadoop_node import common_vars, HadoopNodeConfig, pkn

#This ResourceGroup is boilerplate for making Openstack resources available
#externally. They are created outside an infra model to illustrate that they
#can be factored out into a shared module of reusable components.
external_connection = ResourceGroup("route_out",
                                    net=Network("ro_net"),
                                    subnet=Subnet("ro_subnet",
                                                  ctxt.comp.container.net,
                                                  u"192.168.23.0/24",
                                                  dns_nameservers=[u'8.8.8.8']),
                                    router=Router("ro_router"),
                                    gateway=RouterGateway("ro_gateway",
                                                          ctxt.comp.container.router,
                                                          "external"),
                                    interface=RouterInterface("ro_inter",
                                                              ctxt.comp.container.router,
                                                              ctxt.comp.container.subnet))


def make_std_secgroup(name, desc="standard security group"):
    """
    Returns a standarized resource group with rules for ping and ssh access.
    The returned resource can be further configured with additional rules by the
    caller.
    
    The name parameter is used to form the name of the ResourceGroup, and also
    provides the name of the SecGroup that is created in the ResourceGroup.
    """
    return ResourceGroup("%s_std_secgroup" % name,
                         group=SecGroup(name, desc),
                         ping_rule=SecGroupRule("ping_rule",
                                                ctxt.comp.container.group,
                                                ip_protocol="icmp",
                                                from_port=-1, to_port=-1),
                         ssh_rule=SecGroupRule("ssh_rule",
                                               ctxt.comp.container.group,
                                               ip_protocol="tcp",
                                               from_port=22, to_port=22),
                         )


#name of the image we want to use
ubuntu_img = "Ubuntu 14.04 amd64"


#common keyword args used for servers
common_kwargs = {"key_name":pkn}


class HadoopInfra(InfraModel):
    fip_pool = "external"  #attributes that aren't resources are ignored
    #add the standard slave_secgroup and connectivity components
    slave_secgroup = make_std_secgroup("slave", desc="For Hadoop slaves")
    gateway = external_connection
    
    #create an additional secgroup for the namenode
    namenode_secgroup = make_std_secgroup("namenode", desc="For Hadoop namenode")
    #add additional rules specific to the Hadoop namenode secgroup
    jobtracker_webui_rule = SecGroupRule("jobtracker_webui_rule",
                                         ctxt.model.namenode_secgroup.group,
                                         ip_protocol="tcp",
                                         from_port=50030, to_port=50030)
    namenode_webui_rule = SecGroupRule("namenode_webui_rule",
                                       ctxt.model.namenode_secgroup.group,
                                       ip_protocol="tcp",
                                       from_port=50070, to_port=50070)
    jobtracker_rule = SecGroupRule("jobtracker_rule",
                                   ctxt.model.namenode_secgroup.group,
                                   ip_protocol="tcp",
                                   from_port=50031, to_port=50031)
    namenode_rule = SecGroupRule("namenode_rule",
                                 ctxt.model.namenode_secgroup.group,
                                 ip_protocol="tcp",
                                 from_port=50071, to_port=50071)
    
    #HADOOP name node
    name_node = Server("name_node", ubuntu_img, "m1.small",
                       security_groups=[ctxt.model.namenode_secgroup.group],
                       nics=[ctxt.model.gateway.net], **common_kwargs)
    name_node_fip = FloatingIP("name_node_fip", ctxt.model.name_node,
                               ctxt.model.name_node.iface0.addr0,
                               pool=fip_pool)
    #HADOOP slaves
    slaves = MultiResourceGroup("slaves",
                                 slave=Server("slave", ubuntu_img,
                                              "m1.small",
                                              nics=[ctxt.model.gateway.net],
                                              security_groups=[ctxt.model.slave_secgroup.group],
                                              **common_kwargs),
                                 slave_fip=FloatingIP("sn_fip",
                                                      ctxt.comp.container.slave,
                                                      ctxt.comp.container.slave.iface0.addr0,
                                                      pool=fip_pool))
    

def host_list(ctx_exp, sep_char=" "):
    """
    This returns a callable that computes a list of ip addresses separated by
    the indicated character. This is one approach to providing constructing
    callable arguments that Actuator will invoke when it is needed.
    
    In this case, the ctx_exp is expected to return a dict-like object when
    "called" with the Actuator-supplied CallContext (the 'ctx' argument to
    host_list_inner()). We ask for the values() of that object to get the list
    of roles in the dict.
    """
    def host_list_inner(ctx):
        return sep_char.join([role.host_ref.get_ip()
                              for role in ctx_exp(ctx).values()])
    return host_list_inner


class HadoopNamespace(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.slaves)),
                   Var("NAMENODE_IP", HadoopInfra.name_node.iface0.addr0),
                   Var("NAMENODE_PORT", HadoopInfra.namenode_rule.to_port),
                   Var("JOBTRACKER_PORT", HadoopInfra.jobtracker_rule.to_port))
    
    name_node = Role("name_node",
                     host_ref=HadoopInfra.name_node_fip)
    slaves = MultiRole(Role("slave",
                            host_ref=ctxt.model.infra.slaves[ctxt.name].slave_fip,
                            variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                       Var("COMP_KEY", ctxt.name)]))
    
    def create_slaves(self, count):
        """
        This method takes care of the creating the references to additional
        slave Roles, which in turn creates more slave infra resources.
        """
        for i in range(count):
            _ = self.slaves[i]
    

class HadoopConfig(ConfigModel):
    select_all = HadoopNamespace.q.union(HadoopNamespace.q.name_node,
                                         HadoopNamespace.q.slaves.all())
    node_setup = MultiTask("node_setup",
                           ConfigClassTask("setup_suite", HadoopNodeConfig),
                           select_all)
    slave_ip = ShellTask("slave_ips",
                         "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                         " > !{HADOOP_CONF_DIR}/slaves",
                         task_role=HadoopNamespace.name_node)
    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=HadoopNamespace.name_node)
    with_dependencies(node_setup | slave_ip | format_hdfs)
    
