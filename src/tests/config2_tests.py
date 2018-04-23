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

"""
Created on Jan 15, 2015
"""
import time
import threading
import six
from errator import set_default_options, reset_all_narrations

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.namespace import NamespaceModel, with_variables
ocf.get_shade_cloud = ost_support.mock_get_shade_cloud

from actuator import (InfraModel, MultiResourceGroup,
                      ctxt, Var, ResourceGroup, Role,
                      MultiRole, NullTask, LOG_DEBUG, ConfigModel,
                      MultiTask, ConfigClassTask, ExecutionException)
from actuator.provisioners.core import ProvisioningTaskEngine
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.provisioners.openstack.resources import (Server, Network,
                                                       Router, FloatingIP,
                                                       Subnet, SecGroup,
                                                       SecGroupRule, RouterGateway,
                                                       RouterInterface)
from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.exec_agents.core import ExecutionAgent


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

common_kwargs = {"key_name": "actuator-dev-key"}


def setup_module():
    reset_all_narrations()
    set_default_options(check=True)


def teardown_module():
    reset_all_narrations()


def host_list(ctx_exp, sep_char=" "):
    def host_list_inner(ctx):
        return sep_char.join([h.host_ref.get_ip() for h in ctx_exp(ctx).values()])
    return host_list_inner


def test001():
    class Infra1(InfraModel):
        fip_pool = "external"
        # add the standard secgroup and connectivity components
        gateway = external_connection
        slave_secgroup = make_std_secgroup
        
        # HADOOP slaves
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
    ns = Namespace("ns")
        
    class InnerConfig(ConfigModel):
        task = NullTask("inner_task", "summat")
    
    class Config(ConfigModel):
        do_it = MultiTask("multi", ConfigClassTask("suite", InnerConfig, init_args=("c2inner",)),
                          Namespace.q.slaves.all())
    cfg = Config("cm")
    
    os_prov = ProvisioningTaskEngine(infra, provisioner_proxies=[OpenStackProvisionerProxy("wibble")], num_threads=1)
    for i in range(5):
        _ = ns.slaves[i]
    ns.compute_provisioning_for_environ(infra)
    _ = infra.refs_for_components()
    import traceback
    try:
        os_prov.perform_tasks()
    except Exception as e:
        six.print_("Provision failed with %s; details below" % str(e))
        for t, et, ev, tb, _ in os_prov.get_aborted_tasks():
            six.print_("prov task %s failed with:" % t.name)
            traceback.print_exception(et, ev, tb)
            six.print_()
        assert False, "can't proceed due to provisioning errors"
        
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                                namespace_model_instance=ns,
                                num_threads=1,
                                no_delay=True, log_level=LOG_DEBUG)
    try:
        ea.perform_config()
    except Exception as e:
        six.print_("Config failed with %s; details below" % str(e))
        for t, et, ev, tb, _ in ea.get_aborted_tasks():
            six.print_("task %s failed with:" % t.name)
            traceback.print_exception(et, ev, tb)
            six.print_()
        assert False, "The config had errors; see output"
        
    assert (cfg.do_it.value().instances[0].instance.task.get_task_role().host_ref is not None and
            cfg.do_it.value().instances[0].instance.task.get_task_host() is not None and
            isinstance(cfg.do_it.value().instances[0].instance.task.get_task_host(),
                       six.string_types))


def test002():
    """
    test002: check that we properly catch the wrong type for the config model
    """
    class Infra2(InfraModel):
        pass
    
    try:
        _ = ParamikoExecutionAgent(config_model_instance=Infra2("i2"))
        assert False, "should have complained about wrong type for config_model_instance"
    except ExecutionException as _:
        assert True
    except Exception as e:
        assert False, "Wrong exception raised: %s" % str(e)


def test003():
    """
    test003: check that we raise the right exception when given the wrong type for namespacce
    """
    class Infra3(InfraModel):
        pass
    
    try:
        _ = ParamikoExecutionAgent(namespace_model_instance=Infra3("i3"))
        assert False, "should have complained about wrong type for namespace_model_instance"
    except ExecutionException as _:
        assert True
    except Exception as e:
        assert False, "Wrong exception raised: %s" % str(e)


def test004():
    """
    test004: check that we raise the right exception when given the wrong type for infra model
    """
    class NS4(NamespaceModel):
        pass
    
    try:
        _ = ParamikoExecutionAgent(infra_model_instance=NS4("ns"))
        assert False, "should have complained about wrong type for infra_model_instance"
    except ExecutionException as _:
        assert True
    except Exception as e:
        assert False, "Wrong exception raised: %s" % str(e)


def test005():
    """
    test005: check that we can initiate reversing config tasks
    """
    class Config5(ConfigModel):
        pass

    class NS5(NamespaceModel):
        pass

    ea = ExecutionAgent(config_model_instance=Config5("cm"),
                        namespace_model_instance=NS5("ns"))
    try:
        ea.reverse_task({}, {})
        assert True
    except Exception as e:
        assert False, "Failed with: %s" % str(e)


def test006():
    """
    test006: invoke the abort processing method
    """
    class Config6(ConfigModel):
        pass

    class NS6(NamespaceModel):
        pass

    ea = ExecutionAgent(config_model_instance=Config6("cm"),
                        namespace_model_instance=NS6("ns"))
    ea.abort_process_tasks()
    assert ea.stop, "Processing state not set to stop"


def test007():
    """
    test007: affirm that we can stop the processing loop; this can block forever if broken
    """
    class Config7(ConfigModel):
        pass

    class NS7(NamespaceModel):
        pass
    ea = ExecutionAgent(config_model_instance=Config7("cm"),
                        namespace_model_instance=NS7("ns"))

    def wait_and_abort(lea):
        time.sleep(0.5)
        lea.abort_process_tasks()
    
    ea.task_queue.put(({}, {}))
    
    t = threading.Thread(target=wait_and_abort, args=(ea,))
    t.start()
    ea.reverse_process_tasks()
    assert ea.stop, "We stopped processing without signaling abort"


def do_all():
    setup_module()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            six.print_(">>>>>>>>Running test %s" % k)
            v()
    teardown_module()


if __name__ == "__main__":
    do_all()
