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

import sys
from actuator import *   # @UnusedWildImport
from actuator.provisioners.openstack.resource_tasks import (Server, SecGroup, SecGroupRule,
                                                            Network, Router, RouterGateway,
                                                            RouterInterface, Subnet, KeyPair,
                                                            FloatingIP, OpenstackProvisioner)


pubkey = "actuator-dev-key.pub"


class SimpleInfra(InfraModel):
    with_infra_options(long_names=True)
    fip_pool = "public"  # this is the name of the pool at TryStack

    #
    # connectivity
    network = Network("simple_network")
    subnet = Subnet("simple_subnet", ctxt.model.network, "192.168.10.0/24",
                    dns_nameservers=['8.8.8.8'])
    router = Router("simple_router")
    gateway = RouterGateway("simple_gateway", ctxt.model.router, "public")
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
    server = Server("simple_server", "ubuntu14.04-LTS", "m1.small",
                    nics=[ctxt.model.network],
                    security_groups=[ctxt.model.secgroup], key_name=ctxt.model.kp,
                    availability_zone="nova")

    #
    # external access
    fip = FloatingIP("simple_fip", ctxt.model.server,
                     ctxt.model.server.iface0.addr0,
                     pool=fip_pool)


def start_and_stop():
    infra = SimpleInfra("simple")
    prov = OpenstackProvisioner("it", "doesn't", "matter", "now", num_threads=5, cloud_name="trystack")
    ao = ActuatorOrchestration(infra_model_inst=infra, provisioner=prov)
    _ = ao.initiate_system()
    print "Hit return when you want to tear down:\n",
    _ = sys.stdin.readline()
    ao.teardown_system()


if __name__ == "__main__":
    start_and_stop()
