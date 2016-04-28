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

from actuator import *   # @UnusedWildImport
from actuator.provisioners.openstack.resource_tasks import (Server, SecGroup, SecGroupRule,
                                                            Network, Router, RouterGateway,
                                                            RouterInterface, Subnet, KeyPair,
                                                            FloatingIP, OpenstackProvisioner)

# cloud_name = "trystack"
cloud_name = "citycloud"


if cloud_name == "trystack":
    image = "ubuntu14.04-LTS"
    flavor = "m1.small"
    extern_netname = "public"
    az = "nova"
elif cloud_name == "citycloud":
    image = "Ubuntu 14.04 - LTS - Trusty Tahr"
    flavor = '2C-2GB'
    extern_netname = "ext-net"  # do a
    az = None
else:
    raise Exception("I don't recognize clouds with the name %s" % cloud_name)


pubkey = "actuator-dev-key.pub"


class SimpleInfra(InfraModel):
    with_infra_options(long_names=True)
    fip_pool = extern_netname  # this is the name of the pool

    #
    # connectivity
    network = Network("simple_network")
    subnet = Subnet("simple_subnet", ctxt.model.network, "192.168.10.0/24",
                    dns_nameservers=['8.8.8.8'])
    router = Router("simple_router")
    gateway = RouterGateway("simple_gateway", ctxt.model.router, extern_netname)
    interface = RouterInterface("simple_interface",
                                ctxt.model.router,
                                ctxt.model.subnet)

    #
    # security
    secgroup = SecGroup("simple_secgroup")
    ping_rule = SecGroupRule("ping_rule", ctxt.model.secgroup,
                             ip_protocol="icmp", from_port=-1, to_port=-1)
    ssh_rule = SecGroupRule("ssh_rule", ctxt.model.secgroup,
                            ip_protocol="tcp", from_port=22, to_port=22)
    kp = KeyPair("simple_kp", "simple_kp", pub_key_file=pubkey)

    #
    # server
    server = Server("simple_server", image, flavor,
                    nics=[ctxt.model.network],
                    security_groups=[ctxt.model.secgroup], key_name=ctxt.model.kp,
                    availability_zone=az)

    #
    # external access
    fip = FloatingIP("simple_fip", ctxt.model.server,
                     ctxt.model.server.iface0.addr0,
                     pool=fip_pool)


def start_and_stop():
    infra = SimpleInfra("simple")
    prov = OpenstackProvisioner(num_threads=1, cloud_name=cloud_name)
    ao = ActuatorOrchestration(infra_model_inst=infra, provisioner=prov)
    success = ao.initiate_system()
    if not success:
        for t, et, ev, tb in ao.get_errors():
            print "\nFAILED TASK: %s" % t.name
            traceback.print_exception(et, ev, tb)
    print "\nHit return when you want to tear down:\n",
    _ = sys.stdin.readline()
    ao.teardown_system()


if __name__ == "__main__":
    start_and_stop()
