#
# Copyright (c) 2018 Tom Carroll
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

from actuator.provisioners.core import ProvisioningTask
from actuator.provisioners.azure.resources import *
from actuator.utils import capture_mapping
from azure.mgmt.network.models import (PublicIPAddressSku, IPVersion, IPAllocationMethod,
                                       SecurityRule, SecurityRuleAccess, SecurityRuleDirection,
                                       SecurityRuleProtocol, NetworkSecurityGroup, PublicIPAddress)
# from azure.mgmt.compute.models import LinuxConfiguration, SshConfiguration, SshPublicKey

_azure_domain = "AZURE_DOMAIN"


@capture_mapping(_azure_domain, AzResourceGroup)
class AzResourceGroupTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc_client = run_context.resource
        rsrc_client.resource_groups.create_or_update(self.rsrc.get_display_name(),
                                                     {'location': self.rsrc.location})

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc_client = run_context.resource
        delete_async = rsrc_client.resource_groups.delete(self.rsrc.get_display_name())
        delete_async.wait()


@capture_mapping(_azure_domain, AzNetwork)
class AzNetworkTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = super(AzNetworkTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzResourceGroup):
            the_things.append(self.rsrc.rsrc_grp)
        return the_things

    # SLOWER
    # def _reverse(self, proxy):
    #     run_context = proxy.get_context()
    #     vnops = run_context.network.virtual_networks
    #     async_op = vnops.delete(self.rsrc.rsrc_grp.get_display_name(),
    #                             self.rsrc.get_display_name())
    #     async_op.wait()

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        network = run_context.network
        ad = {
              "location": self.rsrc.location,
              "address_space": {"address_prefixes": self.rsrc.address_prefixes},
             }
        async_creation = network.virtual_networks.create_or_update(
            self.rsrc.rsrc_grp.get_display_name(),
            self.rsrc.get_display_name(),
            ad
        )
        async_creation.wait()


@capture_mapping(_azure_domain, AzSubnet)
class AzSubnetTask(ProvisioningTask):
    def depends_on_list(self):
        the_things = super(AzSubnetTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzResourceGroup):
            the_things.append(self.rsrc.rsrc_grp)
        if isinstance(self.rsrc.network, AzNetwork):
            the_things.append(self.rsrc.network)
        return the_things

    # SLOWER
    # def _reverse(self, proxy):
    #     run_context = proxy.get_context()
    #     snops = run_context.network.subnets
    #     async_op = snops.delete(self.rsrc.rsrc_grp.get_display_name(),
    #                             self.rsrc.network.get_display_name(),
    #                             self.rsrc.get_display_name())
    #     async_op.wait()

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        network = run_context.network
        async_creation = network.subnets.create_or_update(self.rsrc.rsrc_grp.get_display_name(),
                                                          self.rsrc.network.get_display_name(),
                                                          self.rsrc.get_display_name(),
                                                          {"address_prefix": self.rsrc.address_prefix})
        subnet_info = async_creation.result()
        self.rsrc.set_subnet_id(subnet_info.id)


@capture_mapping(_azure_domain, AzNIC)
class AzNICTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(AzNICTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzResourceGroup):
            depson.append(self.rsrc.rsrc_grp)
        if isinstance(self.rsrc.network, AzNetwork):
            depson.append(self.rsrc.network)
        for sn in self.rsrc.subnets:
            if isinstance(sn, AzSubnet):
                depson.append(sn)
        if isinstance(self.rsrc.public_ip, AzPublicIP):
            depson.append(self.rsrc.public_ip)
        return depson

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        ifops = run_context.network.network_interfaces
        async_op = ifops.delete(self.rsrc.rsrc_grp.get_display_name(),
                                self.rsrc.get_display_name())
        async_op.wait()

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        network = run_context.network
        ipconfigs = [{"name": "{}-{}".format(self.rsrc.name, i),
                      "subnet": {"id": sn.get_subnet_id()},
                      "public_ip_address": PublicIPAddress(id=self.rsrc.public_ip.get_id())}
                     for i, sn in enumerate(self.rsrc.subnets)]
        async_creation = network.network_interfaces.create_or_update(self.rsrc.rsrc_grp.get_display_name(),
                                                                     self.rsrc.get_display_name(),
                                                                     {"location": self.rsrc.location,
                                                                      "ip_configurations": ipconfigs})
        nic_info = async_creation.result()
        self.rsrc.set_nic_id(nic_info.id)


@capture_mapping(_azure_domain, AzServer)
class AzServerTask(ProvisioningTask):
    def vm_name(self):
        return self.rsrc.get_display_name().replace(".", "-").replace("_", "-")

    def depends_on_list(self):
        depson = super(AzServerTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzResourceGroup):
            depson.append(self.rsrc.rsrc_grp)
        for nic in self.rsrc.nics:
            if isinstance(nic, AzNIC):
                depson.append(nic)
        return depson

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        vmops = run_context.compute.virtual_machines
        async_op = vmops.delete(self.rsrc.rsrc_grp.get_display_name(), self.vm_name())
        async_op.wait()

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        compute = run_context.compute
        # create the big swinging dict
        name = self.vm_name()
        os_profile = {"computer_name": name,
                      "admin_username": self.rsrc.admin_user,
                      "admin_password": self.rsrc.admin_password}
        if self.rsrc.pub_key_file:
            key_data = open(self.rsrc.pub_key_file, "r").read()
            linux_config = {"disable_password_authentication": True,
                            "ssh": {"public_keys": [{"path": "/home/%s/.ssh/authorized_keys" % self.rsrc.admin_user,
                                                     "key_data": key_data}
                                                    ]
                                    }
                            }
            os_profile["linux_configuration"] = linux_config
        bsd = {
            "location": self.rsrc.location,
            "os_profile": os_profile,
            "hardware_profile": {
                "vm_size": self.rsrc.vm_size
            },
            "storage_profile": {
                "image_reference": {
                    "publisher": self.rsrc.publisher,
                    "offer": self.rsrc.offer,
                    "sku": self.rsrc.sku,
                    "version": self.rsrc.version
                }
            },
            "network_profile": {
                "network_interfaces": [{"id": nic.get_nic_id()}
                                       for nic in self.rsrc.nics]
            }
        }

        async_creation = compute.virtual_machines.create_or_update(self.rsrc.rsrc_grp.get_display_name(),
                                                                   name,
                                                                   bsd)
        async_creation.wait()
        network = run_context.network
        interface = network.network_interfaces.get(self.rsrc.rsrc_grp.get_display_name(),
                                                   self.rsrc.nics[0].get_display_name())
        private_ip = interface.ip_configurations[0].private_ip_address
        self.rsrc.set_ip(private_ip)


@capture_mapping(_azure_domain, AzPublicIP)
class AzPublicIPTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(AzPublicIPTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzResourceGroup):
            depson.append(self.rsrc.rsrc_grp)
        return depson

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        ipops = run_context.network.public_ip_addresses
        async_op = ipops.delete(self.rsrc.rsrc_grp.get_display_name(), self.rsrc.get_display_name())
        async_op.wait()

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        network = run_context.network
        params = {"location": self.rsrc.location,
                  "sku": PublicIPAddressSku(name="Basic"),
                  "public_ip_allocation_method": IPAllocationMethod.static,
                  "public_ip_address_version": IPVersion.ipv4}
        async_creation = network.public_ip_addresses.create_or_update(self.rsrc.rsrc_grp.get_display_name(),
                                                                      self.rsrc.get_display_name(),
                                                                      params)
        publicip_info = async_creation.result()
        self.rsrc.set_ip(publicip_info.ip_address)
        self.rsrc.set_id(publicip_info.id)


@capture_mapping(_azure_domain, AzSecurityRule)
class AzSecurityRuleTask(ProvisioningTask):
    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        # we need the Azure object for the sec group later, but the rules don't persist nicely
        # so we'll put the args to the object into a dict and save that until later
        kwargs = dict(name=self.rsrc.get_display_name(),
                      access=self.rsrc.access.lower(),
                      description=self.rsrc.description,
                      destination_address_prefix="*",
                      destination_port_range=self.rsrc.destination_port_range,
                      direction=self.rsrc.direction.lower(),
                      protocol=self.rsrc.protocol.lower(),
                      source_address_prefix=self.rsrc.source_address_prefix,
                      source_port_range=self.rsrc.source_port_range,
                      priority=self.rsrc.priority)
        self.rsrc.set_azure_obj(kwargs)


@capture_mapping(_azure_domain, AzSecurityGroup)
class AzSecurityGroupTask(ProvisioningTask):
    def depends_on_list(self):
        depson = super(AzSecurityGroupTask, self).depends_on_list()
        if isinstance(self.rsrc.rsrc_grp, AzSecurityGroup):
            depson.append(self.rsrc.rsrc_grp)
        for rule in self.rsrc.rules:
            if isinstance(rule, AzSecurityRule):
                depson.append(rule)
        return depson

    # SLOWER
    # def _reverse(self, proxy):
    #     run_context = proxy.get_context()
    #     sgops = run_context.network.network_security_groups
    #     async_op = sgops.delete(self.rsrc.rsrc_grp.get_display_name(),
    #                             self.rsrc.get_display_name())
    #     async_op.wait()

    @staticmethod
    def update_access(val):
        return (SecurityRuleAccess.allow
                if val == "allow"
                else SecurityRuleAccess.deny)

    @staticmethod
    def update_direction(val):
        return (SecurityRuleDirection.inbound
                if val == "inbound"
                else SecurityRuleDirection.outbound)

    @staticmethod
    def update_protocol(val):
        return (SecurityRuleProtocol.tcp
                if val == "tcp"
                else SecurityRuleProtocol.udp)

    def _perform(self, proxy):
        self.rsrc._refix_arguments()
        run_context = proxy.get_context()
        net_secops = run_context.network.network_security_groups
        rules_args = [rule.get_azure_obj() for rule in self.rsrc.rules]
        for args in rules_args:
            args["access"] = self.update_access(args["access"])
            args["direction"] = self.update_direction(args["direction"])
            args["protocol"] = self.update_protocol(args["protocol"])
        rules = [SecurityRule(**kwargs) for kwargs in rules_args]
        nsg = NetworkSecurityGroup(location=self.rsrc.rsrc_grp.location,
                                   security_rules=rules)
        async_create = net_secops.create_or_update(self.rsrc.rsrc_grp.get_display_name(),
                                                   self.rsrc.get_display_name(),
                                                   nsg)
        sg_info = async_create.result()
