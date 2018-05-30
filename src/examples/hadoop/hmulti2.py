import sys
import traceback
from actuator.provisioners.azure.resources import *
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator import (ctxt, InfraModel, ActuatorOrchestration, with_infra_options,
                      MultiResourceGroup, ResourceGroup)
from hadoop import make_std_secgroup, HadoopConfig, HadoopNamespace


model = ctxt.model
parent = ctxt.comp.container


external_connection = ResourceGroup("route_out",
                                    net=Network("ro_net"),
                                    subnet=Subnet("ro_subnet",
                                                  parent.net,
                                                  u"192.168.23.0/24",
                                                  dns_nameservers=[u'8.8.8.8']),
                                    router=Router("ro_router"),
                                    gateway=RouterGateway("ro_gateway",
                                                          parent.router,
                                                          "ext-net"),
                                    interface=RouterInterface("ro_inter",
                                                              parent.router,
                                                              parent.subnet))


rempass = "C0rnD0ggi3"

common_server_args = dict(publisher="Canonical",
                          offer="UbuntuServer",
                          sku="16.04.0-LTS",
                          version="latest",
                          vm_size='Standard_DS1_v2',
                          admin_user="ubuntu",
                          admin_password=rempass)


class AzureOS(InfraModel):
    with_infra_options(long_names=True)

    # The Azure part
    rg = AzResourceGroup("hm2-rg", "westus")
    network = AzNetwork("hm2-network", model.rg, ["10.0.0.0/16"])
    subnet = AzSubnet("hm2-subnet", model.rg, model.network, "10.0.0.0/24")
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

    # The OpenStack part
    gateway = external_connection
    std_sg = make_std_secgroup("std-sg", desc="for hadoop")
    nn_sg = SecGroup("nn-access-sg", description="allows namenode to access slaves")
    nn_sgr = SecGroupRule("nn-to-slave", secgroup=model.nn_sg, ip_protocol="tcp",
                          from_port=50031, to_port=50031,
                          cidr=model.name_node_fip.get_cidr4)
    os_slaves = MultiResourceGroup(
        "slave",
        slave=Server("slave", "Ubuntu 14.04 - LTS - Trusty Tahr", u"2C-2GB-50GB",
                     nics=[model.gateway.net],
                     security_groups=[model.std_sg.group,
                                      model.nn_sg]),
        slave_fip=FloatingIP("slave-fip", parent.slave, parent.slave.iface0.addr0, pool="ext-net")
    )
    name_node = Server("namenode", "Ubuntu 14.04 - LTS - Trusty Tahr", u"2C-2GB-50GB",
                       nics=[model.gateway.net],
                       security_groups=[model.std_sg.group])
    name_node_fip = FloatingIP("name_node_fip", model.name_node, model.name_node.iface0.addr0,
                               pool="ext-net")


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

    city = OpenStackProvisionerProxy("citycloud")

    inf = AzureOS("multi2", event_handler=ehandler)
    numslaves = 5
    for i in range(numslaves):
        _ = inf.az_slaves[i]
        _ = inf.os_slaves[i]

    ao = ActuatorOrchestration(infra_model_inst=inf,
                               provisioner_proxies=[city, azure],
                               num_threads=2*numslaves*3 + 3,
                               post_prov_pause=10,
                               no_delay=True)
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
