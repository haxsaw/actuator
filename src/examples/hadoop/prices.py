#
# Copyright (c) 2017 Tom Carroll
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

from actuator.infra import InfraModel
from actuator.provisioners.openstack.resources import Server, FloatingIP
from actuator.provisioners.vsphere.resources import TemplatedServer

CORES2_MEM2_STO50 = u"2C-2GB-50GB"
CORES1_MEM0_5_STO20 = u"1C-0.5GB"
CORES1_MEM1_STO200 = u'1C-1GB-200GB'
CORES2_MEM4_STO50 = u'2C-4GB-50GB'

# clouds we can price against
CITYCLOUD = "citycloud"
RACKSPACE = "rackspace"
VSPHERE = 'vsphere'

#
# CityCloud pricing
# this table maps a flavor name to the coefficients of core, gigmem, gigstore per hour
citycloud_hourly_price_table = {CORES2_MEM2_STO50: (2, 2, 50),
                                CORES1_MEM0_5_STO20: (1, 0.5, 20),
                                CORES1_MEM1_STO200: (1, 1, 200),
                                CORES2_MEM4_STO50: (2, 4, 50)}

pound_per_dollar = 0.77936
core_per_hour = 0.0098 * pound_per_dollar
gigmem_per_hour = 0.00817 * pound_per_dollar
gigstore_per_hour = 0.00016 * pound_per_dollar
ip_per_hour = 0.003263 * pound_per_dollar


def get_citycloud_houly_cost_of_servers(im):
    assert isinstance(im, InfraModel)
    servers = [c for c in im.components() if isinstance(c, Server)]
    core_cost = gigmem_cost = gigstore_cost = 0.0
    for s in servers:
        assert isinstance(s, Server)
        try:
            num_cores, num_gigmem, num_gigstore = citycloud_hourly_price_table[s.flavorName]
        except KeyError:
            raise Exception("Flavor name %s of server %s isn't recognized" % (s.get_display_name(),
                                                                              s.flavorName))
        else:
            core_cost += num_cores * core_per_hour
            gigmem_cost += num_gigmem * gigmem_per_hour
            gigstore_cost += num_gigstore * gigstore_per_hour

    ip_cost = ip_per_hour * len([o for o in im.components() if isinstance(o, FloatingIP)])

    return core_cost, gigmem_cost, gigstore_cost, ip_cost


def create_citycloud_price_table(im):
    """
    Creates a formatted string showing the costs involved in running the supplied infra
    model for a hour, day, and 30-day month on CityCloud
    :param im: instance of an InfraModel
    :return: formatted string containing a table of results
    """
    cc, mc, sc, ic = get_citycloud_houly_cost_of_servers(im)
    result = ["     |    Hourly      Daily      30-day  ",
              "-----+-----------------------------------"]
    result.append(" Cor |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc, cc*24, cc*24*30))
    result.append(" Mem |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(mc, mc*24, mc*24*30))
    result.append(" Sto |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(sc, sc*24, sc*24*30))
    result.append(" Ips |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(ic, ic*24, ic*24*30))
    result.append("-----+-----------------------------------")
    result.append(" Tot |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc+mc+sc+ic,
                                                               24 * (cc+sc+mc+ic),
                                                               24 * 30 * (cc+mc+sc+ic)))
    return "\n".join(result)

#
# Rackspace pricing
# this table maps a flavor name to a tuple of (raw infra costs, management costs)
rackspace_hourly_price_table = {CORES1_MEM0_5_STO20: (0.01963, 0.00307),
                                CORES2_MEM2_STO50: (0.03926, 0.00614)}


def get_rackspace_hourly_cost_of_servers(im):
    assert isinstance(im, InfraModel)
    servers = [c for c in im.components() if isinstance(c, Server)]
    total_raw_infra_cost = total_management_cost = 0.0
    for s in servers:
        assert isinstance(s, Server)
        try:
            infra_cost, mgmt_cost = rackspace_hourly_price_table[s.flavorName]
        except KeyError:
            raise Exception("Flavor name %s of server %s isn't recognized" % (s.get_display_name(),
                                                                              s.flavorName))
        else:
            total_raw_infra_cost += infra_cost
            total_management_cost += mgmt_cost
    return total_raw_infra_cost, total_management_cost


def create_rackspace_price_table(im):
    """
    Creates a formatted string showing the costs involved in running the supplied infra
    model for a hour, day, and 30-day month on Rackspace
    :param im: instance of an InfraModel
    :return: formatted string containing a table of results
    """
    ic, mc = get_rackspace_hourly_cost_of_servers(im)
    result = ["     |    Hourly      Daily      30-day  ",
              "-----+-----------------------------------"]
    result.append(
              " Inf |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(ic, ic*24, ic*24*30))
    result.append(
              "Mgmt |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(mc, mc*24, mc*24*30))
    result.append(
              "-----+-----------------------------------")
    result.append(
              " Tot |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(ic+mc,
                                                           24 * (ic + mc),
                                                           24*30 * (ic + mc)))
    return "\n".join(result)


#
# VSphere pricing
hours_per_30_days = 30.0 * 24
vs_vcpu_price = 0.01 / hours_per_30_days
vs_mem_price = 0.01 / hours_per_30_days
vs_disk_price = 1.51 / hours_per_30_days
vs_pubip_price = 15.61 / hours_per_30_days
vsphere_hourly_pricing_table = {"ActuatorBase3": (1, 1, 16, 1),
                                "ActuatorBase5": (1, 1, 16, 1),
                                "ActuatorBase6": (1, 1, 16, 1)}


def get_vsphere_houly_cost_of_servers(im):
    assert isinstance(im, InfraModel)
    servers = [c for c in im.components() if isinstance(c, TemplatedServer)]
    core_cost = gigmem_cost = gigstore_cost = ip_cost = 0.0
    for s in servers:
        assert isinstance(s, TemplatedServer)
        try:
            num_cores, num_gigmem, num_gigstore, num_ips = vsphere_hourly_pricing_table[s.template_name]
        except KeyError:
            raise Exception("Flavor name %s of server %s isn't recognized" % (s.template_name,
                                                                              s.get_display_name()))
        else:
            core_cost += num_cores * vs_vcpu_price
            gigmem_cost += num_gigmem * vs_mem_price
            gigstore_cost += num_gigstore * vs_disk_price
            ip_cost += num_ips * vs_pubip_price

    return core_cost, gigmem_cost, gigstore_cost, ip_cost


def create_vsphere_price_table(im):
    """
    Creates a formatted string showing the costs involved in running the supplied infra
    model for a hour, day, and 30-day month on VSphere
    :param im: instance of an InfraModel
    :return: formatted string containing a table of results
    """
    cc, mc, sc, ic = get_vsphere_houly_cost_of_servers(im)
    result = ["     |    Hourly      Daily      30-day  ",
              "-----+-----------------------------------"]
    result.append(" Cor |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc, cc*24, cc*24*30))
    result.append(" Mem |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(mc, mc*24, mc*24*30))
    result.append(" Sto |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(sc, sc*24, sc*24*30))
    result.append(" Ips |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(ic, ic*24, ic*24*30))
    result.append("-----+-----------------------------------")
    result.append(" Tot |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc+mc+sc+ic,
                                                               24 * (cc+sc+mc+ic),
                                                               24 * 30 * (cc+mc+sc+ic)))
    return "\n".join(result)

#
price_calculators = {CITYCLOUD: create_citycloud_price_table,
                     RACKSPACE: create_rackspace_price_table,
                     VSPHERE: create_vsphere_price_table}


def create_price_table(im, for_cloud=CITYCLOUD):
    """
    Creates a formatted string showing the costs involved in running the supplied infra
    model for a hour, day, and 30-day month
    :param im: instance of an InfraModel
    :param for_cloud: restricts generation of prices to a single cloud. If None
        (the default), all known clouds are priced
    :return: formatted string containing a table of results
    """
    calculator = price_calculators.get(for_cloud)
    if calculator is None:
        raise Exception("I don't have a calculator for cloud %s" % for_cloud)
    return calculator(im)
