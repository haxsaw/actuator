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

'''
Created on Jan 15, 2015
'''

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.namespace import NamespaceModel, with_variables
ocf.set_neutron_client_class(ost_support.MockNeutronClient)
ocf.set_nova_client_class(ost_support.MockNovaClient)

from actuator import (InfraModel, ProvisionerException, MultiResourceGroup,
                      MultiResource, ctxt, Var, ResourceGroup, Role,
                      MultiRole, NullTask, LOG_DEBUG, LOG_INFO, ConfigModel,
                      MultiTask, ConfigClassTask)
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from actuator.provisioners.openstack.resources import (Server, Network,
                                                        Router, FloatingIP,
                                                        Subnet, SecGroup,
                                                        SecGroupRule, RouterGateway,
                                                        RouterInterface)
from actuator.exec_agents.ansible.agent import AnsibleExecutionAgent
from actuator.modeling import AbstractModelReference


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

make_std_secgroup = ResourceGroup("make_std_secgroup",
                              group=SecGroup("group", "standard security group"),
                              ping_rule=SecGroupRule("ping_rule",
                                                     ctxt.comp.container.group,
                                                     ip_protocol="icmp",
                                                     from_port=-1, to_port=-1),
                              ssh_rule=SecGroupRule("ssh_rule",
                                                    ctxt.comp.container.group,
                                                    ip_protocol="tcp",
                                                    from_port=22, to_port=22))

ubuntu_img = "Ubuntu 13.10"

common_kwargs = {"key_name":"actuator-dev-key"}


def host_list(ctx_exp, sep_char=" "):
    def host_list_inner(ctx):
        return sep_char.join([h.host_ref.get_ip() for h in ctx_exp(ctx).values()])
    return host_list_inner


def test001():
    class Infra1(InfraModel):
        fip_pool = "external"
        #add the standard secgroup and connectivity components
        gateway = external_connection
        slave_secgroup = make_std_secgroup
        
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
    infra = Infra1("infra")
    
    class Namespace(NamespaceModel):
        with_variables(Var("SLAVE_IPS", host_list(ctxt.model.slaves)))
        
        slaves = MultiRole(Role("slave",
                                host_ref=ctxt.nexus.inf.slaves[ctxt.name].slave_fip,
                                variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                           Var("COMP_KEY", ctxt.name)]))
    ns = Namespace()
        
    class InnerConfig(ConfigModel):
        task = NullTask("inner_task", "summat")
    
    class Config(ConfigModel):
        do_it = MultiTask("multi", ConfigClassTask("suite", InnerConfig),
                          Namespace.q.slaves.all())
    cfg = Config()
    
    uid = "it"
    pwd = "doesn't"
    url = "matter"
    
    os_prov = OpenstackProvisioner(uid, pwd, uid, url, num_threads=1)
    for i in range(5):
        _ = ns.slaves[i]
    ns.compute_provisioning_for_environ(infra)
    _ = infra.refs_for_components()
    import traceback
    try:
        os_prov.provision_infra_model(infra)
    except Exception, e:
        print "Provision failed with %s; details below" % e.message
        for t, et, ev, tb in os_prov.agent.get_aborted_tasks():
            print "prov task %s failed with:" % t.name
            traceback.print_exception(et, ev, tb)
            print
        assert False, "can't proceed due to provisioning errors"
        
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               num_threads = 1,
                               no_delay=True, log_level=LOG_DEBUG)
    try:
        ea.perform_config()
    except Exception, e:
        print "Config failed with %s; details below" % e.message
        for t, et, ev, tb in ea.get_aborted_tasks():
            print "task %s failed with:" % t.name
            traceback.print_exception(et, ev, tb)
            print
        assert False, "The config had errors; see output"
        
    assert (cfg.do_it.value().instances[0].instance.task.get_task_role().host_ref is not None and
            cfg.do_it.value().instances[0].instance.task.get_task_host() is not None and
            isinstance(cfg.do_it.value().instances[0].instance.task.get_task_host(),
                           basestring))


def do_all():
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()

        