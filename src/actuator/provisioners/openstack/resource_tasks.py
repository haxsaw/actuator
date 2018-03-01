# 
# Copyright (c) 2015 Tom Carroll
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
Internal to Actuator; responsible for processing Openstack resource objects
"""
import time
import threading

from actuator.provisioners.core import ProvisioningTask
from actuator.provisioners.openstack.resources import *
from actuator.utils import capture_mapping
from errator import narrate, narrate_cm

_rt_domain = "resource_task_domain"


@capture_mapping(_rt_domain, Network)
class ProvisionNetworkTask(ProvisioningTask):
    @narrate(lambda s, _: "...causing the start of the provisioning task for the network {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        with narrate_cm("-and tried to create the network"):
            response = run_context.cloud.create_network(self.rsrc.get_display_name(),
                                                        admin_state_up=self.rsrc.admin_state_up)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_network_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "...which started the de-provisioning task for the network {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        netid = self.rsrc.osid
        with narrate_cm("-and tried to delete the network"):
            run_context.cloud.delete_network(netid)
        
        
@capture_mapping(_rt_domain, Subnet)
class ProvisionSubnetTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionSubnetTask, self).depends_on_list())
        if isinstance(self.rsrc.network, Network):
            the_things.add(self.rsrc.network)
        return list(the_things)

    @narrate(lambda s, _: "...which started the provisioning task for the subnet {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        with narrate_cm("-and tried to created the subnet"):
            response = run_context.cloud.create_subnet(self.rsrc._get_arg_msg_value(self.rsrc.network,
                                                                                    Network,
                                                                                    "osid",
                                                                                    "network"),
                                                       self.rsrc.cidr, ip_version=self.rsrc.ip_version,
                                                       subnet_name=self.rsrc.get_display_name(),
                                                       dns_nameservers=self.rsrc.dns_nameservers,
                                                       enable_dhcp=True)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_subnet_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "...resulting in starting the de-provisioning task for the subnet {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        # this may not be needed as the subnet may go with the network
        subnet_id = self.rsrc.osid
        run_context.cloud.delete_subnet(subnet_id)


@capture_mapping(_rt_domain, SecGroup)
class ProvisionSecGroupTask(ProvisioningTask):
    """depends on nothing"""

    # @FIXME: this lock and its use are due to an apparent thread-safety issue
    # down in the novaclient. It would seem that even if there are different
    # client objects being used in different threads to build security groups,
    # nova has some shared state that gets hosed and causes one or the other to
    # fail if they're happening at the same time. For now, this lock will ensure
    # single-threaded operation of this trouble code, and hopefully we can get
    # a bug filed and the problem resolved soon.

    _sg_create_lock = threading.Lock()

    @narrate(lambda s, _: "...which started the provisioning task for the security group {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        with self._sg_create_lock:
            # @FIXME: this lock is because nova isn't threadsafe for this
            # call, and until it is we have to single-thread through it
            with narrate_cm("-which resulting in trying to create the security group"):
                response = run_context.cloud.create_security_group(name=self.rsrc.get_display_name(),
                                                                   description=self.rsrc.description)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "...resulting in starting the de-provisioning task for the security "
                          "group {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        secgroup_id = self.rsrc.osid
        with narrate_cm("-and tried to delete the security group"):
            run_context.cloud.delete_security_group(secgroup_id)


@capture_mapping(_rt_domain, SecGroupRule)
class ProvisionSecGroupRuleTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionSecGroupRuleTask, self).depends_on_list())
        if isinstance(self.rsrc.secgroup, SecGroup):
            the_things.add(self.rsrc.secgroup)
        return list(the_things)

    @narrate(lambda s, _: "...which started the provisioning task for the security group rule {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        self.rsrc._refix_arguments()
        sg_id = self.rsrc._get_arg_msg_value(self.rsrc.secgroup,
                                             SecGroup,
                                             "osid", "secgroup")
        with narrate_cm("-and then tried to create the security group"):
            response = run_context.cloud.create_security_group_rule(sg_id,
                                                                    port_range_min=self.rsrc.from_port,
                                                                    port_range_max=self.rsrc.to_port,
                                                                    protocol=self.rsrc.ip_protocol,
                                                                    remote_ip_prefix=self.rsrc.cidr)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_rule_id(self.rsrc._id, self.rsrc.osid)
        
    # NO _reverse required; the rules should follow the secgroup


@capture_mapping(_rt_domain, Server)
class ProvisionServerTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = super(ProvisionServerTask, self).depends_on_list()
        the_things.extend([i for i in self.rsrc.security_groups
                           if isinstance(i, SecGroup)] +
                          [j for j in self.rsrc.nics
                           if isinstance(j, Network)] +
                          ([self.rsrc.key_name]
                           if isinstance(self.rsrc.key_name, KeyPair)
                           else []))
        return list(set(the_things))

    def _process_server_addresses(self, addr_dict):
        self.rsrc.set_addresses(addr_dict)
        for i, (k, v) in enumerate(addr_dict.items()):
            iface = getattr(self.rsrc, "iface%d" % i)
            iface.name = k
            for j, iface_addr in enumerate(v):
                setattr(iface, "addr%d" % j, iface_addr['addr'])

    @narrate(lambda s, _: "...which started the provisioning task for the server {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        with narrate_cm("-requiring a refresh of the available images"):
            run_context.maps.refresh_images()
        with narrate_cm("-requiring a refresh of the available flavors"):
            run_context.maps.refresh_flavors()
        with narrate_cm("-requiring a refresh of the available networks"):
            run_context.maps.refresh_networks()

        with narrate_cm("-this required getting the already fixed arguments to the server"):
            args, kwargs = self.rsrc.get_fixed_args()
        _, image_name, flavor_name = args
        with narrate_cm("-this required getting the display name of the server"):
            name = self.rsrc.get_display_name()
        image = run_context.maps.image_map.get(image_name)
        if image is None:
            raise ProvisionerException("Image %s doesn't seem to exist" % image_name,
                                       record=run_context.record)
        flavor = run_context.maps.flavor_map.get(flavor_name)
        if flavor is None:
            raise ProvisionerException("Flavor %s doesn't seem to exist" % flavor_name,
                                       record=run_context.record)
        secgroup_list = []
        if self.rsrc.security_groups:
            with narrate_cm("-requiring a refresh of the available security groups"):
                run_context.maps.refresh_secgroups()
            for sgname in self.rsrc.security_groups:
                sgname = self.rsrc._get_arg_msg_value(sgname, SecGroup, "osid", "sec group name/id")
                sg = run_context.maps.secgroup_map.get(sgname)
                if sg is None:
                    raise ProvisionerException("Security group %s doesn't seem to exist" % sgname,
                                               record=run_context.record)
                secgroup_list.append(sg["id"])
            kwargs["security_groups"] = secgroup_list
            
        nics_list = []
        if self.rsrc.nics:
            for nicname in self.rsrc.nics:
                nicname = self.rsrc._get_arg_msg_value(nicname, Network, "osid", "network name/id")
                nic = run_context.maps.network_map.get(nicname)
                if nic is None:
                    raise ProvisionerException("NIC %s doesn't seem to exist" % nicname,
                                               record=run_context.record)
                nics_list.append({'net-id': nic["id"]})
            kwargs['nics'] = nics_list
            
        if isinstance(kwargs["key_name"], KeyPair):
            kwargs["key_name"] = kwargs["key_name"].get_key_name()

        with narrate_cm("-once all arguments have been collected, an attempt to create the server is started"):
            srvr = run_context.cloud.create_server(name, image, flavor, **kwargs)
        self.rsrc.set_osid(srvr["id"])
        run_context.record.add_server_id(self.rsrc._id, self.rsrc.osid)
        
        # while not srvr.addresses:
        with narrate_cm("-which requires waiting for the server creation to complete to get the server's addresses"):
            while not srvr["addresses"]:
                time.sleep(0.25)
                srvr = run_context.cloud.get_server(srvr["id"])
        with narrate_cm("-and finally, processing the servers addresses"):
            self._process_server_addresses(srvr["addresses"])

    @narrate(lambda s, _: "...resulting in starting the de-provisioning task for the server {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        run_context.cloud.delete_server(self.rsrc.osid)

                
@capture_mapping(_rt_domain, Router)
class ProvisionRouterTask(ProvisioningTask):
    # depends on nothing

    @narrate(lambda s, _: "...which started the provisioning task for the router {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        with narrate_cm(lambda r: "-first trying to create router {}".format(r.get_display_name()),
                        self.rsrc):
            reply = run_context.cloud.create_router(name=self.rsrc.get_display_name(),
                                                    admin_state_up=self.rsrc.admin_state_up)
        self.rsrc.set_osid(reply["id"])
        run_context.record.add_router_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "...resulting in starting the de-provisioning task for the router {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        router_id = self.rsrc.osid
        with narrate_cm(lambda rid: "-and then tried to delete the router with osid {}".format(rid),
                        router_id):
            run_context.cloud.delete_router(router_id)


@capture_mapping(_rt_domain, RouterGateway)
class ProvisionRouterGatewayTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionRouterGatewayTask, self).depends_on_list())
        if isinstance(self.rsrc.router, Router):
            the_things.add(self.rsrc.router)
        return list(the_things)

    @narrate(lambda s, _: "...which started the provisioning task for the the router gateway {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm("-but first the network maps need to be refreshed"):
            run_context.maps.refresh_networks()
        ext_net = run_context.maps.network_map.get(self.rsrc.external_network_name)
        with narrate_cm(lambda nid: "-which required updating the router with the gateway id {}".format(nid),
                        ext_net["id"]):
            run_context.cloud.update_router(router_id, ext_gateway_net_id=ext_net["id"])
        
    # no reversing; assume it goes with the router


@capture_mapping(_rt_domain, RouterInterface)
class ProvisionRouterInterfaceTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionRouterInterfaceTask, self).depends_on_list())
        if isinstance(self.rsrc.router, Router):
            the_things.add(self.rsrc.router)
        if isinstance(self.rsrc.subnet, Subnet):
            the_things.add(self.rsrc.subnet)
        return list(the_things)

    @narrate(lambda s, _: "...resulting in commencing the provisioning task for router interface {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm(lambda rid: "-first the router with osid {} was looked up".format(rid),
                        router_id):
            router = run_context.cloud.get_router(router_id)
        snid = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        with narrate_cm(lambda s, r: "-then the router interface was added to router {} for "
                                     "subnet {}".format(r, s),
                        snid, str(router)):
            response = run_context.cloud.add_router_interface(router, subnet_id=snid)
        self.rsrc.set_osid(response[u'port_id'])
        run_context.record.add_router_iface_id(self.rsrc._id, response[u'port_id'])

    @narrate(lambda s, _: "...which started the de-provisioning task for the router interface {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm(lambda r: "-first the router with osid {} was queried".format(r),
                        router_id):
            router = run_context.cloud.get_router(router_id)
        snid = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        with narrate_cm(lambda s, r: "-after finding the router {}, the interface "
                                     "to subnet {} was removed".format(r, s),
                        str(router), snid):
            run_context.cloud.remove_router_interface(router, subnet_id=snid)


@capture_mapping(_rt_domain, FloatingIP)
class ProvisionFloatingIPTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionFloatingIPTask, self).depends_on_list())
        if isinstance(self.rsrc.server, Server):
            the_things.add(self.rsrc.server)
        return list(the_things)

    @narrate(lambda s, _: "...resulting in commencing the provisioning task for floating ip {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        self.rsrc._refix_arguments()
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            with narrate_cm(lambda s: "-which required getting server {} to associate it with the "
                                      "floating ip".format(s),
                            servername):
                server = run_context.cloud.get_server(servername)
        else:
            server = None
        with narrate_cm(lambda s, p: "-which started the creation of the floating ip on pool {} for server {}"
                                     .format(p, str(s)),
                        self.rsrc.pool, str(server)):
            fip = run_context.cloud.create_floating_ip(network=self.rsrc.pool, server=server)
        self.rsrc.set_addresses(fip["floating_ip_address"])
        self.rsrc.set_osid(fip["id"])
        run_context.record.add_floating_ip_id(self.rsrc._id, self.rsrc.osid)

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            run_context.cloud.detach_ip_from_server(servername, self.rsrc.osid)
        run_context.cloud.delete_floating_ip(self.rsrc.osid)

            
@capture_mapping(_rt_domain, KeyPair)
class ProvisionKeyPairTask(ProvisioningTask):
    # KeyPairs depend on nothing

    @narrate(lambda s, e: "...which in turn started the provisioning task for keypair {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        name = self.rsrc.get_key_name()
        if self.rsrc.pub_key_file is not None:
            try:
                public_key = open(self.rsrc.pub_key_file, "r").read()
            except Exception, e:
                raise ProvisionerException("Couldn't open/read the public key file %s "
                                           "for KeyPair %s; %s" % (self.rsrc.pub_key_file,
                                                                   self.rsrc.name,
                                                                   e.message))
        else:
            public_key = self.rsrc.pub_key
        run_context.maps.refresh_keypairs()
        kp = run_context.maps.keypair_map.get(name)
        if kp is not None:
            if self.rsrc.force:
                with narrate_cm("-and since it was a forced create, the existing keypair first deleted"):
                    run_context.cloud.delete_keypair(name)
                with narrate_cm("-and after deleting the existing keypair (it was a forced create), the keypair "
                                "creation process was started"):
                    run_context.cloud.create_keypair(name, public_key)
        else:
            with narrate_cm("-so the process to create a new keypair was started"):
                run_context.cloud.create_keypair(name, public_key)
