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

from collections import Iterable
from actuator import NamespaceModel, Role, MultiRole, MultiRoleGroup
from actuator.modeling import AbstractModelReference, ModelInstanceReference
from actuator.provisioners.azure.resources import *
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.resources import _OpenstackProvisionableInfraResource
from actuator.provisioners.aws.resources import *


class VarDescriptor(object):
    """
    unpacks and organises the data to be extracted from a Var
    """
    _unexpanded = "-INCOMPLETE-"

    def __init__(self, v, owner):
        """
        create a new instance using Var v from the perspective of the owner 'owner'
        :param v: a Var instance
        :param owner: a Variable container such as a NamespaceModel instance, a Role, or a
            MultiRole or MultiRoleGroup. This container should nominally 'own' the Var, but
            in any event will be the place where the evaluation of the Var's value will be
            anchored.
        """
        self.vname = v.name
        self.v = v
        self.owner = owner
        self.was_complete = False
        try:
            value = v.get_value(self.owner)
            self.was_complete = True
        except Exception:
            try:
                value = v.get_value(self.owner, allow_unexpanded=True)
            except Exception:
                value = self._unexpanded
        self.value = value
        self.raw_value = v.get_raw_value()
        if isinstance(self.raw_value, ContextExpr):
            self.path = reversed(self.raw_value._path)
        else:
            self.path = ""
        self.is_external = self.v.value_is_external()
        self.in_env = self.v.in_env

    def to_dict(self):
        return {"name": self.vname,
                "in_env": "T" if self.in_env else "F",
                "value": self.value,
                "complete": "T" if self.was_complete else "F",
                "external": "T" if self.is_external else "F",
                "path": self.path}


def get_vars_for_roles(roles):
    """
    computes the VarDescriptors for each role in the supplied sequence of roles
    :param roles: a iterable of role objects (or refs to them)
    :return: a dict where the role is the key and the values is a list of VarDescriptor objects
        for each Var the role can see
    """
    vars_by_role = {}
    for role in roles:
        if isinstance(role, AbstractModelReference):
            role = role.value()
        if isinstance(role, Role):
            vars_by_role[role] = [VarDescriptor(*role.find_variable(vname))
                                  for vname in role.get_visible_vars()]
        elif isinstance(role, (MultiRole, MultiRoleGroup)):
            vars_by_role.update(get_vars_for_roles(role.values()))
    return vars_by_role


def all_namespace_vars(nsm):
    """
    returns a dict whose keys are either the input namespace or the roles in the namespace, and whose
    values are lists of variables visible from the perspective of each key
    :param nsm: instance of a namespace model
    :return: dict of {(nsm|role): List[VarDescriptor]}
    """
    assert isinstance(nsm, NamespaceModel)
    vars_by_container = dict()
    vars_by_container[nsm] = [VarDescriptor(*nsm.find_variable(vname))
                              for vname in nsm.get_visible_vars()]

    vars_by_container.update(get_vars_for_roles(nsm.get_roles().values()))

    return vars_by_container


def namespace_report(nsm):
    """
    returns a list of strings that describe all variables for each variable container in a namespace
    :param nsm: a NamespaceModel instance
    :return: pre-formatted list of strings that describe the variable containers (namespace & roles)
        and the value of their variables. The returned report contains:
        variable name
        T/F flag if the variable will be passed as an environment variable for jobs run on the
            role's host
        value of the variable, if it can be determined
        T/F flag if the value could be completely determined
        T/F flag as to whether the variable's value came from an external source
        path for the case where the variable is from a context expression
    """
    assert isinstance(nsm, NamespaceModel)
    report = list()
    report.append("---Vars at namespace {} level:".format(nsm.name))
    report.append("{:21}|{:^3}|{:50s}|{:^3}|{:^3}|{:15}|".format("Var name", "Env", "Value",
                                                                 "Cmp", "Ext", "Path"))
    report.append("-" * len(report[-1]))
    all_nsvs = all_namespace_vars(nsm)
    nsvds = all_nsvs[nsm]
    for vd in nsvds:
        d = vd.to_dict()
        for k, v in d.items():
            if v is None:
                d[k] = ""
        report.append("{name:21}|{in_env:^3}|{value:50s}|{complete:^3}|{external:^3}|{path:15}|".format(**d))
    del all_nsvs[nsm]
    report.append("")

    for role, rolevars in all_nsvs.items():
        assert isinstance(role, Role)
        roleref = role.get_ref()
        if roleref is not None:
            assert isinstance(roleref, ModelInstanceReference)
            path = ".".join(roleref.get_path())
        else:
            path = ""
        host_ref = role.host_ref.value().name if role.host_ref is not None else "NO_HOST"
        report.append(" --> Vars visible to role:{}, path:{}, host_ref:{}".format(role.name, path,
                                                                                  host_ref))
        report.append("{:21}|{:^3}|{:50s}|{:^3}|{:^3}|{:15}|".format("Var name", "Env", "Value",
                                                                     "Cmp", "Ext", "Path"))
        report.append("-" * len(report[-1]))
        for vd in rolevars:
            d = vd.to_dict()
            for k, v in d.items():
                if v is None:
                    d[k] = ""
            report.append("{name:21}|{in_env:^3}|{value:50s}|{complete:^3}|{external:^3}|{path:15}|".
                          format(**d))
        report.append("")
    return report


def make_os_secgroup_entry(ossg):
    sge = {"Desc": ossg.description,
           "Rules": []}
    return sge


def make_az_resource_group(rsrc_grp):
    return {"Azure Resource Group Name": rsrc_grp.get_display_name(),
            "Security Groups": {},
            "Group Servers": []}


def make_aws_secgroup_entry(aws_sg):
    sge = {"Desc": aws_sg.description,
           "Rules": []}
    return sge


def attr_val(obj, attrname):
    val = getattr(obj, attrname)
    if val is None:
        val = obj.get_init_value_for_attr(attrname)
        if isinstance(val, ContextExpr):
            val = ".".join(reversed(val._path))
        elif isinstance(val, AbstractModelReference):
            val = val.get_path()
    return val


def security_check(inf_inst):
    report = []
    os_sec_groups = {}
    az_resource_groups = {}
    aws_sec_groups = {}
    inf_inst.compute_provisioning_from_refs(inf_inst.refs_for_components())
    # for c in inf_inst.components():
    #     c.fix_arguments()
    inf_inst.fix_arguments()
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
        elif isinstance(c, AWSProvisionableInfraResource):
            if isinstance(c, (AWSInstance, NetworkInterface)):
                security_groups = {}
                server_details = {"Groupholder name": c.get_display_name(),
                                  "Groupholder type": ("AWS instance"
                                                       if isinstance(c, AWSInstance)
                                                       else "NetworkInterface"),
                                  "Region": c.cloud,
                                  "Security groups": security_groups}
                if isinstance(c, AWSInstance) and isinstance(c.network_interfaces, Iterable):
                    server_details["Network Interface names"] = [ni.get_display_name() for ni in c.network_interfaces]
                if isinstance(c.sec_groups, Iterable):
                    for sg in c.sec_groups:
                        group = aws_sec_groups.get(sg.get_display_name())
                        if group is None:
                            group = make_aws_secgroup_entry(sg)
                            aws_sec_groups[sg.get_display_name()] = group
                        security_groups[sg.get_display_name()] = group
                report.append(server_details)
            elif isinstance(c, SecurityGroup):
                group = aws_sec_groups.get(c.get_display_name())
                if group is None:
                    group = make_aws_secgroup_entry(c)
                    aws_sec_groups[c.get_display_name()] = group
            elif isinstance(c, SecurityGroupRule):
                sg = c.security_group
                if sg is None:
                    report.append("Unbound AWS SecurityGroupRule: {}".format(c.get_display_name()))
                else:
                    group = aws_sec_groups.get(sg.get_display_name())
                    if group is None:
                        group = make_aws_secgroup_entry(sg)
                        aws_sec_groups[sg.get_display_name()] = group
                    rules = group["Rules"]
                    rules.append("Rule {}, proto {}, from {}, to {}, cidr {}".format(c.get_display_name(),
                                                                                     c.ip_protocol,
                                                                                     c.from_port,
                                                                                     c.to_port,
                                                                                     c.cidrip))
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
