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

import json

from errator import set_default_options, reset_all_narrations

from actuator import (ActuatorOrchestration, ctxt, MultiResource, ResourceGroup,
                      MultiResourceGroup)
from actuator import InfraModel
from actuator.provisioners.example_resources import Server, Network, Queue
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.namespace import (NamespaceModel, Role, Var, with_variables,
                                MultiRole, RoleGroup, MultiRoleGroup)
from pt_help import persistence_helper


def setup_module():
    reset_all_narrations()
    set_default_options(check=True)


def teardown_module():
    reset_all_narrations()


def test01():
    """
    test01: Check that orchestrators persist and reanimate themselves
    """
    op = persistence_helper(None, None)
    assert op


class Infra1(InfraModel):
    pass


def test02():
    """
    test02: Check that the orchestrator persists and reanimates with an empty infra model
    """
    orch = ActuatorOrchestration(infra_model_inst=Infra1("t2"))
    d = persist_to_dict(orch)
    d_json = json.dumps(d)
    d = json.loads(d_json)
    op = reanimate_from_dict(d)
    assert (hasattr(op, "infra_model_inst") and
            orch.infra_model_inst.name == op.infra_model_inst.name and
            orch.infra_model_inst.nexus is not op.infra_model_inst.nexus and
            op.infra_model_inst.nexus is not None and
            op.infra_model_inst.nexus.find_instance(Infra1) is op.infra_model_inst)


class Infra2(InfraModel):
    s = Server("s1", mem="8GB")


def test03():
    """
    test03: save orchestrator with an infra with a single server
    """
    i0 = Infra2("test3")
    op = persistence_helper(None, i0)
    assert (hasattr(op.infra_model_inst, "s") and
            op.infra_model_inst.s.name.value() == i0.s.name.value() and
            op.infra_model_inst.s.mem.value() == i0.s.mem.value())


class Infra3(InfraModel):
    n = Network("net", cidr="192.168.6.0/24")


def test04():
    """
    test04: save orch with an infra with a single network
    """
    i0 = Infra3("i3")
    op = persistence_helper(None, i0)
    assert (hasattr(op.infra_model_inst, "n") and
            op.infra_model_inst.n.name.value() == i0.n.name.value() and
            op.infra_model_inst.n.cidr.value() == i0.n.cidr.value())


class Infra4(InfraModel):
    n = Network("net", cidr="192.168.6.0/24")
    s = Server("server", network=ctxt.model.n)


def test05():
    """
    test05: save infra with a network an server, with the server using ctxt to ref the network
    """
    i0 = Infra4("test05")
    op = persistence_helper(None, i0)
    assert (op.infra_model_inst.n.value() is op.infra_model_inst.s.network.value())


class Infra5(InfraModel):
    cluster = MultiResource(Server("node", mem="8GB"))


def test06():
    """
    test06: save an infra with servers in a MultiResource container
    """
    i0 = Infra5("test06")
    for i in range(5):
        _ = i0.cluster[i]
    op = persistence_helper(None, i0)
    assert (len(op.infra_model_inst.cluster) == 5 and
            op.infra_model_inst.cluster[0].mem.value() == "8GB" and
            op.infra_model_inst.cluster[0].name.value() == "node_0")


class Infra6(InfraModel):
    group = ResourceGroup("group",
                          server=Server("server", mem="8GB", net=ctxt.model.group.network),
                          network=Network("net", cidr="192.168.6.0/24"),
                          queue=Queue("q", host=ctxt.model.group.server, port=8000))


def test07():
    """
    test07: check persistence with a ResourceGroup
    """
    i0 = Infra6("i6")
    op = persistence_helper(None, i0)
    i1 = op.infra_model_inst
    assert (i1.group.server.net.value() is i1.group.network.value() and
            i1.group.queue.host.value() is i1.group.server.value() and
            i1.group.server.mem.value() == "8GB" and
            i1.group.queue.name.value() == "q")


class Infra7(InfraModel):
    num_slaves = 20
    master = Server("master", mem="8GB", net=ctxt.model.network)
    network = Network("net", cidr="192.168.6.0/24")
    clusters = MultiResourceGroup("cell",
                                  foreman=Server("foreman", mem="8GB",
                                                 net=ctxt.model.network),
                                  queue=Queue("q", host=ctxt.comp.container.foreman),
                                  slaves=MultiResource(Server("slave",
                                                              mem="8GB",
                                                              net=ctxt.model.network)))

    def size(self, size):
        for i in range(size):
            c = self.clusters[i]
            for j in range(self.num_slaves):
                _ = c.slaves[j]


def test08():
    """
    test08: Check that we can save/reanimate a MultiResourceGroup
    """
    i0 = Infra7("i8")
    i0.size(5)
    _ = i0.refs_for_components()
    op = persistence_helper(None, i0)
    i1 = op.infra_model_inst
    assert (len(i1.clusters[2].slaves) == Infra7.num_slaves and
            i1.clusters[2].value() is not i1.clusters[1].value() and
            i1.clusters[0].slaves[0] is not i1.clusters[1].slaves[0] and
            i1.clusters[1].name.value() == "cell_1")


class NS9(NamespaceModel):
    pass


def test09():
    """
    test09: check basic namespace persist/reanimate as part of a orchestrator
    """
    i9 = Infra7("i9")
    ns9 = NS9()
    ns9p = persistence_helper(ns9, i9).namespace_model_inst
    assert ns9p


def test10():
    """
    test10: check that nexus is consistent across models (infra and namespace)
    """
    i10 = Infra7("i10")
    ns10 = NS9()
    op = persistence_helper(ns10, i10)
    assert op.namespace_model_inst.nexus is op.infra_model_inst.nexus


class NS11(NamespaceModel):
    r = Role("ro1e1")


def test11():
    """
    test11: check if a simple Role can be reanimated
    """
    ns11 = NS11()
    op = persistence_helper(ns11, None)
    nsm = op.namespace_model_inst
    assert (nsm.r and
            nsm.r.name.value() == "ro1e1" and
            nsm.r.host_ref.value() is None and
            not nsm.r.variables.value() and
            not nsm.r.overrides.value())


class NS12(NamespaceModel):
    r = Role("role", variables=[Var("v1", "summat")])


def test12():
    """
    test12: check if a namespace role with a variable can be reanimated
    """
    ns12 = NS12()
    op = persistence_helper(ns12, None)
    nsm = op.namespace_model_inst
    assert (nsm.r.get_visible_vars() and
            nsm.r.var_value("v1") == "summat")


class Infra13(InfraModel):
    s = Server("wibble")


class NS13(NamespaceModel):
    r = Role("role", host_ref=Infra13.s)


def test13():
    """
    test13: check if a namespace role that has a host_ref to an inframodel server reanimates
    """
    infra = Infra13("13")
    ns = NS13()
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    im = op.infra_model_inst
    assert (nsm.r.host_ref.value() is im.s.value())


class Infra14(InfraModel):
    s = Server("wibble")


class NS14(NamespaceModel):
    r = Role("role", variables=[Var("server_name", Infra14.s.name)])


def test14():
    """
    test14: check if a role Var that get's it value from a model ref reanimates
    """
    infra = Infra14("14")
    ns = NS14()
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    im = op.infra_model_inst
    assert nsm.r.var_value("server_name") == "wibble"


class Infra15(InfraModel):
    s = Server("wibble", ip=ctxt.nexus.ns.r.v.IP)


class NS15(NamespaceModel):
    r = Role("role", variables=[Var("IP", "127.0.0.1")])


def test15():
    """
    test15: check if a server that get's its IP from a role's vars reanimates
    """
    infra = Infra15("15")
    ns = NS15()
    op = persistence_helper(ns, infra)
    im = op.infra_model_inst
    assert im.s.ip.value() == "127.0.0.1"


class Infra16(InfraModel):
    s = Server("wibble", ip=ctxt.nexus.ns.r.v.IP)


class NS16(NamespaceModel):
    with_variables(Var("IP", "192.168.6.14"))
    r = Role("headfake")


def test16():
    """
    test16: server gets IP from a role var but the var is declared globally; reanimate?
    """
    infra = Infra16("16")
    ns = NS16()
    op = persistence_helper(ns, infra)
    im = op.infra_model_inst
    assert im.s.ip.value() == "192.168.6.14"


class Infra17(InfraModel):
    s = Server("wow", ip="192.168.6.22")


class NS17(NamespaceModel):
    r = Role("wobble", host_ref=ctxt.nexus.inf.s.ip)


def test17():
    """
    test17: get a host ref from a context expression, persist/reanimate
    """
    infra = Infra17("17")
    ns = NS17()
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    assert nsm.r.host_ref.value() == "192.168.6.22"


class Infra18(InfraModel):
    s = Server("s18", ip="192.168.6.14")


class NS18(NamespaceModel):
    r = Role("wob", variables=[Var("IP", ctxt.nexus.inf.s.ip)])


def test18():
    """
    test18: have a Var get its value for a ctxt expr; persist/reanimate
    """
    infra = Infra18("18")
    ns = NS18()
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    assert nsm.r.v.IP.value() == "192.168.6.14"


class Infra19(InfraModel):
    grid = MultiResource(Server("node", mem="8GB"))


class NS19(NamespaceModel):
    nodes = MultiRole(Role("node", host_ref=ctxt.nexus.inf.grid[ctxt.name]))


def test19():
    """
    test19: multirole/resource persist save
    """
    infra = Infra19("19")
    ns = NS19()
    for i in range(5):
        _ = ns.nodes[i]
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    im = op.infra_model_inst
    node_keys = set(nsm.nodes.keys())
    grid_keys = set(im.grid.keys())
    assert (len(nsm.nodes) == 5 and len(im.grid) == 5 and
            node_keys == grid_keys)


class Infra20(InfraModel):
    cluster = ResourceGroup("single",
                            foreman=Server("foreman", mem="8GB"),
                            slave=Server("slave", mem="8GB"))


class NS20(NamespaceModel):
    cluster = RoleGroup("thingie",
                        foreman=Role("foreman_role", host_ref=Infra20.cluster.foreman,
                                     variables=[Var("foreman", ctxt.name)]),
                        slave=Role("slave_role", host_ref=ctxt.nexus.inf.cluster.slave,
                                   variables=[Var("slave", ctxt.name)]))


def test20():
    """
    test20: mode with RoleGroup; test persist/reanimate
    """
    infra = Infra20("20")
    ns = NS20()
    op = persistence_helper(ns, infra)
    im = op.infra_model_inst
    nsm = op.namespace_model_inst
    assert (nsm.cluster.foreman.host_ref.value() is im.cluster.foreman.value() and
            nsm.cluster.slave.host_ref.value() is im.cluster.slave.value() and
            nsm.cluster.foreman.name.value() == "foreman_role" and
            nsm.cluster.slave.name.value() == "slave_role" and
            nsm.cluster.foreman.v.foreman.value() == "foreman" and
            nsm.cluster.slave.v.slave.value() == "slave")


class Infra21(InfraModel):
    cluster = ResourceGroup("single",
                            foreman=Server("foreman", mem="8GB"),
                            slaves=MultiResource(Server("slave", mem="4GB")))


class NS21(NamespaceModel):
    cluster = RoleGroup("thingie",
                        foreman=Role("foreman_role", host_ref=Infra21.cluster.foreman,
                                     variables=[Var("COMPNAME", Infra21.cluster.foreman.name)]),
                        slaves=MultiRole(Role("slave",
                                              host_ref=ctxt.nexus.inf.cluster.slaves[ctxt.name],
                                              variables=[Var("COMPNAME", ctxt.name)])))


def test21():
    """
    test21: test RoleGroup with MultiRole persists/reanimates properly
    """
    infra = Infra21("21")
    ns = NS21()
    num = 10
    for i in range(num):
        _ = ns.cluster.slaves[i]
    op = persistence_helper(ns, infra)
    im = op.infra_model_inst
    nsm = op.namespace_model_inst
    ex_slave_comp_names = set(["slave_%s" % i for i in nsm.cluster.slaves.keys()])
    act_slave_comp_names = set([s.name.value() for s in nsm.cluster.slaves.values()])
    assert (len(im.cluster.slaves) == num and
            len(nsm.cluster.slaves) == num and
            reduce(lambda x, y: x and (im.cluster.slaves[y].value() is
                                       nsm.cluster.slaves[y].host_ref.value()),
                   im.cluster.slaves.keys(),
                   True) and
            ex_slave_comp_names == act_slave_comp_names)


class Infra22(InfraModel):
    clusters = MultiResourceGroup("clusters",
                                  foreman=Server("foreman", mem="8GB"),
                                  slaves=MultiResource(Server("slave", mem="8GB")))


class NS22(NamespaceModel):
    clusters = MultiRoleGroup("clusters_role",
                              foreman=Role("foreman_role",
                                           host_ref=ctxt.nexus.inf.clusters[ctxt.comp.container.idx].foreman),
                              slaves=MultiRole(Role("slave",
                                                    host_ref=ctxt.nexus.inf.clusters[ctxt.comp.container.idx].slaves[
                                                        ctxt.comp.idx]))
                              )


def test22():
    """
    test22: check that MultiRoleGroup persists/reanimates properly
    """
    infra = Infra22("22")
    ns = NS22()
    num = 5
    for i in range(num):
        cluster = ns.clusters[i]
        for j in range(1 + i):
            _ = cluster.slaves[j]
    op = persistence_helper(ns, infra)
    im = op.infra_model_inst
    nsm = op.namespace_model_inst
    summer = lambda m: sum([len(c.slaves) for c in m.clusters.values()])
    right_sum = sum([i + 1 for i in range(num)])
    assert (len(im.clusters) == len(nsm.clusters) and
            len(im.clusters) == num and
            summer(im) == right_sum and
            summer(nsm) == right_sum)


class NS23(NamespaceModel):
    clusters = MultiRoleGroup("clusters_role",
                              foreman_role=Role("foreman_role",
                                                variables=[Var("IDX", ctxt.comp.idx)]),
                              slave_roles=MultiRole(Role("slave_role",
                                                    variables=[Var("IDX", ctxt.comp.idx),
                                                               Var("PIDX", ctxt.comp.container.idx)]))
                              )


def test23():
    """
    test23: check that we determine indexes properly before persist and after reanimate
    """
    ns = NS23()
    num = 5
    for i in range(num):
        cluster = ns.clusters[i]
        for j in range(i + 1):
            _ = cluster.slave_roles[j]
    end_idx = str(num - 1)
    assert ('0' == ns.clusters[0].foreman_role.v.IDX() and
            end_idx == ns.clusters[num - 1].foreman_role.v.IDX() and
            '0' == ns.clusters[num - 1].slave_roles[0].v.IDX() and
            end_idx == ns.clusters[num - 1].slave_roles[0].v.PIDX())
    op = persistence_helper(ns, None)
    nsm = op.namespace_model_inst
    assert ('0' == nsm.clusters[0].foreman_role.v.IDX() and
            end_idx == nsm.clusters[num - 1].foreman_role.v.IDX() and
            '0' == nsm.clusters[num - 1].slave_roles[0].v.IDX() and
            end_idx == nsm.clusters[num - 1].slave_roles[0].v.PIDX())


class NS24(NamespaceModel):
    with_variables(Var("IDX", ctxt.comp.idx))
    clusters = MultiRoleGroup("clusters_role",
                              foreman=Role("foreman_role"),
                              slaves=MultiRole(Role("slave",
                                                    variables=[Var("PIDX", ctxt.comp.container.idx)]))
                              )


def test24():
    """
    test24: like test23, but move the IDX variable to the global level
    """
    ns = NS24()
    num = 2
    for i in range(num):
        cluster = ns.clusters[i]
        for j in range(i + 1):
            _ = cluster.slaves[j]
    end_idx = str(num - 1)
    assert ('0' == ns.clusters[0].foreman.v.IDX() and
            end_idx == ns.clusters[num - 1].foreman.v.IDX() and
            '0' == ns.clusters[num - 1].slaves[0].v.IDX() and
            end_idx == ns.clusters[num - 1].slaves[0].v.PIDX())
    op = persistence_helper(ns, None)
    nsm = op.namespace_model_inst
    assert ('0' == nsm.clusters[0].foreman.v.IDX() and
            end_idx == nsm.clusters[num - 1].foreman.v.IDX() and
            '0' == nsm.clusters[num - 1].slaves[0].v.IDX() and
            end_idx == nsm.clusters[num - 1].slaves[0].v.PIDX())


class ValFormatter(object):
    def __init__(self, prefix):
        self.value = "%s_in_bed" % prefix

    def __call__(self, *args, **kwargs):
        return self.value


class NS25(NamespaceModel):
    tester = ValFormatter("coding")
    r = Role("sleepy", variables=[Var("wut", tester)])


def test25():
    """
    test25: check that other callables are handled properly in persist/reanimate for Vars on roles
    """
    ns = NS25()
    assert ns.r.v.wut() == ns.tester()
    op = persistence_helper(ns, None)
    nsm = op.namespace_model_inst
    assert nsm.r.v.wut() == nsm.tester()


class NS26(NamespaceModel):
    tester = ValFormatter("wibble")
    with_variables(Var("wut", tester))
    r = Role("r")


def test26():
    """
    test26: check other callables are handled properly in persist/reanimate for Vars on models
    """
    ns = NS26()
    assert (ns.v.wut() == ns.tester() and
            ns.r.v.wut() == ns.tester())
    op = persistence_helper(ns, None)
    nsm = op.namespace_model_inst
    assert (nsm.v.wut() == ns.tester() and
            nsm.r.v.wut() == ns.tester())


class Infra27(InfraModel):
    s_name = "wibble"
    s = Server(s_name, mem="8GB")


class NS27(NamespaceModel):
    with_variables(Var("name", Infra27.s.name))


def test27():
    """
    test27: check Vars that use model refs persist/reanimate properly
    """
    infra = Infra27("27")
    ns = NS27()
    op = persistence_helper(ns, infra)
    nsm = op.namespace_model_inst
    assert (nsm.v.name() == infra.s_name)


def do_all():
    setup_module()
    g = globals()
    keys = list(g.keys())
    keys.sort()
    for k in keys:
        v = g[k]
        if k.startswith("test") and callable(v):
            print "Running ", k
            v()


if __name__ == "__main__":
    do_all()
