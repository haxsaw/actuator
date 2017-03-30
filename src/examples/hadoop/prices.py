from actuator.infra import InfraModel
from actuator.provisioners.openstack.resources import Server

core_per_hour = 0.00877 * 0.8659
gigmem_per_hour = 0.00731 * 0.8659
gigstore_per_hour = 0.00014 * 0.8659

CORES2_MEM2_STO50 = u"2C-2GB-50GB"
CORES1_MEM0_5_STO20 = u"1C-0.5GB"
CORES1_MEM1_STO200 = u'1C-1GB-200GB'
CORES2_MEM4_STO50 = u'2C-4GB-50GB'

# this table maps a flavor name to the coefficients of core, gigmem, gigstore per hour
hourly_price_table = {CORES2_MEM2_STO50: (2, 2, 50),
                      CORES1_MEM0_5_STO20: (1, 0.5, 20),
                      CORES1_MEM1_STO200: (1, 1, 200),
                      CORES2_MEM4_STO50: (2, 4, 50)}


def get_houly_cost_of_servers(im):
    assert isinstance(im, InfraModel)
    servers = [c for c in im.components() if isinstance(c, Server)]
    core_cost = gigmem_cost = gigstore_cost = 0.0
    for s in servers:
        assert isinstance(s, Server)
        try:
            num_cores, num_gigmem, num_gigstore = hourly_price_table[s.flavorName]
        except KeyError:
            raise Exception("Flavor name %s of server %s isn't recognized" % (s.get_display_name(),
                                                                              s.flavorName))
        else:
            core_cost += num_cores * core_per_hour
            gigmem_cost += num_gigmem * gigmem_per_hour
            gigstore_cost += num_gigstore * gigstore_per_hour

    return core_cost, gigmem_cost, gigstore_cost


def create_price_table(im):
    """
    Creates a formated string showing the costs involved in running the supplied infra
    model for a hour, day, and 30-day month
    :param im: instance of an InfraModel
    :return: formatted string containing a table of results
    """
    cc, mc, sc = get_houly_cost_of_servers(im)
    result = ["     |    Hourly      Daily      30-day  ",
              "-----+-----------------------------------"]
    result.append(" Cor |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc, cc*24, cc*24*30))
    result.append(" Mem |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(mc, mc*24, mc*24*30))
    result.append(" Sto |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(sc, sc*24, sc*24*30))
    result.append("-----+-----------------------------------")
    result.append(" Tot |{:^12.2f}|{:^11.2f}|{:^12.2f}".format(cc+mc+sc,
                                                         cc*24+sc*24+mc*24,
                                                         cc*24*30+mc*24*30+sc*24*30))
    return "\n".join(result)
