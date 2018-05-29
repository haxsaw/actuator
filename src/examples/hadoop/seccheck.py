from pprint import pprint as pp
from actuator.provisioners.azure.resources import *
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.resources import _OpenstackProvisionableInfraResource
from actuator.modeling import ContextExpr, AbstractModelReference


def make_os_secgroup_entry(ossg):
    sge = {"Desc": ossg.description,
           "Rules": []}
    return sge


def make_az_resource_group(rsrc_grp):
    return {"Azure Resource Group Name": rsrc_grp.get_display_name(),
            "Security Groups": {},
            "Group Servers": []}


def attr_val(obj, attrname):
    val = getattr(obj, attrname)
    if val is None:
        val = obj.get_init_value_for_attr(attrname)
        if isinstance(val, ContextExpr):
            val = ".".join(reversed(val._path))
        elif isinstance(val, AbstractModelReference):
            val = val.get_path()
    return val


def check(inf_inst):
    report = []
    os_sec_groups = {}
    az_resource_groups = {}
    inf_inst.compute_provisioning_from_refs(inf_inst.refs_for_components())
    for c in inf_inst.components():
        c.fix_arguments()
    for c in inf_inst.components():
        if isinstance(c, _OpenstackProvisionableInfraResource):
            if isinstance(c, Server):
                # security groups are reachable via the server, and come from the server perspective
                security_groups = {}
                server_details = {"Server name": c.get_display_name(),
                                  "Server type": "OpenStack",
                                  "Cloud": c.cloud,
                                  "Security groups": security_groups}
                for sg in c.security_groups:
                    group = os_sec_groups.get(sg.get_display_name())
                    if group is None:
                        group = make_os_secgroup_entry(sg)
                        os_sec_groups[sg.get_display_name()] = group
                    security_groups[sg.get_display_name()] = group
                report.append(server_details)
            elif isinstance(c, SecGroup):
                group = os_sec_groups.get(c.get_display_name())
                if group is None:
                    group = make_os_secgroup_entry(c)
                    os_sec_groups[c.get_display_name()] = group
            elif isinstance(c, SecGroupRule):
                sg = c.secgroup
                if sg is None:
                    report.append("Unbound OS SecGroupRule: {}".format(c.get_display_name()))
                else:
                    group = os_sec_groups.get(sg.get_display_name())
                    if group is None:
                        group = make_os_secgroup_entry(sg)
                        os_sec_groups[sg.get_display_name()] = group
                    rules = group["Rules"]
                    rules.append("Rule {}, proto {}, from {}, to {}, cidr {}".format(c.get_display_name(),
                                                                                     c.ip_protocol,
                                                                                     c.from_port,
                                                                                     c.to_port,
                                                                                     c.cidr))
        elif isinstance(c, AzureProvisionableInfraResource):
            if isinstance(c, AzResourceGroup):
                rg = az_resource_groups.get(c.get_display_name())
                if rg is None:
                    rg = make_az_resource_group(c)
                    az_resource_groups[c.get_display_name()] = rg
                    report.append(rg)
            elif isinstance(c, AzServer):
                rsrc_grp = c.rsrc_grp
                if rsrc_grp is None:
                    report.append("Unattached AzServer {}".format(c.get_display_name()))
                else:
                    rg = az_resource_groups.get(rsrc_grp.get_display_name())
                    if rg is None:
                        rg = make_az_resource_group(rsrc_grp)
                        az_resource_groups[rsrc_grp.get_display_name()] = rg
                        report.append(rg)
                    servers = rg["Group Servers"]
                    servers.append(c.get_display_name())
            elif isinstance(c, AzSecurityGroup):
                rsrc_grp = c.rsrc_grp
                if rsrc_grp is None:
                    report.append("Unattached AzSecurityGroup {}".format(c.get_display_name()))
                else:
                    rg = az_resource_groups.get(rsrc_grp.get_display_name())
                    if rg is None:
                        rg = make_az_resource_group(rsrc_grp)
                        az_resource_groups[rsrc_grp.get_display_name()] = rg
                        report.append(rg)
                    all_sgs = rg["Security Groups"]
                    rules = []
                    all_sgs[c.get_display_name()] = {"Rules": rules}
                    for rule in c.rules:
                        rules.append("Name {}, direction {}, proto {}, src port {},"
                                     " dst port {}, src pre {}".format(rule.get_display_name(),
                                                                       rule.direction,
                                                                       rule.protocol,
                                                                       rule.source_port_range,
                                                                       rule.destination_port_range,
                                                                       attr_val(rule, "source_address_prefix")))
    return report


if __name__ == "__main__":
    # OpenStack trial
    from hadoop import HadoopInfra, HadoopNamespace
    inf = HadoopInfra("Trial")
    ns = HadoopNamespace("ns")
    ns.set_infra_model(inf)
    for i in range(5):
        _ = inf.slaves[i]
    rep = check(inf)
    print("OpenStack:")
    pp(rep)

    # Azure trial
    from azuretest import AzureExample
    ae = AzureExample("azure")
    for i in range(5):
        _ = ae.slaves[i]
    rep = check(ae)
    print("\nAzure")
    pp(rep)
