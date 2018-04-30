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

import json
import os
import sys
import six
from errator import get_narration
from actuator import ActuatorOrchestration
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.utils import persist_to_dict, reanimate_from_dict
from actuator.namespace import Var
from hadoop import HadoopInfra, HadoopNamespace
from prices import create_price_table, CITYCLOUD, RACKSPACE, VSPHERE
from hsimple import do_it
# from hevent import TaskEventManager
from vstest import VSHadoopInfra
from actuator.provisioners.vsphere import VSphereProvisionerProxy
user_env = "OS_USER"
pass_env = "OS_PASS"
tenant_env = "OS_TENANT"
auth_env = "OS_AUTH"

with_mongo = False
inst_id = None  # gets set when we are to save in mongo
with_zabbix = False
with_viz = False
zabbix_host_ids = []   # gets set if we inform zabbix of our new hosts
template_list = ["Template App SSH Service", "Template ICMP Ping", "Template OS Linux"]


def make_infra_for_forecast(num_slaves=1, infra_class=HadoopInfra):
    inf = infra_class("forecast")
    ns = HadoopNamespace("hadoop-namespace")
    ns.set_infra_model(inf)
    for i in range(num_slaves):
        _ = inf.slaves[i]
    inf.compute_provisioning_from_refs(inf.refs_for_components())
    for c in inf.components():
        c.fix_arguments()
    return inf


if __name__ == "__main__":
    # this is all command line and environment processing overhead
    if len(sys.argv) == 2:
        arg1 = sys.argv[1].lower()
        with_mongo = "m" in arg1
        with_zabbix = "z" in arg1
        with_viz = "v" in arg1

    if with_zabbix:
        if not os.environ.get("ZABBIX_SERVER") or not os.environ.get("ZABBIX_PRIVATE"):
            six.print_("Ensure that you've set the ZABBIX_SERVER environment var to the public IP of the server,")
            six.print_("and that ZABBIX_PRIVATE is set to the internal IP of the server")

    if with_mongo:
        six.print_("Ensure that mongod is running")

    if with_viz:
        from hevent import TaskEventManager
        six.print_("Visualisation activated")
        handler = TaskEventManager()
    else:
        handler = None
        
    success = infra = ns = ao = None
    json_file = None
    quit = False
    inst_id = None
    persist_op = "p=persist model"
    standup_op = "s=stand-up hadoop"
    rerun_op = "r=re-run stand-up"
    teardown_op = "t=teardown known system"
    load_op = "l=load persisted model"
    forecast_op = "f=forecast"
    quit_op = "q=quit"
    while not quit:
        ops = [quit_op, load_op, forecast_op]
        if ao:
            ops.append(persist_op)
            ops.append(teardown_op)
            ops.append(rerun_op)
        elif not json_file:
            ops.append(standup_op)
        try:
            six.print_("%s" % (",".join(ops)))
            six.print_("/".join([o[0] for o in ops]), ": ",)
        except:
            continue
        cmd = sys.stdin.readline().strip().lower()
        if not cmd or cmd[0] not in [o[0] for o in ops]:
            six.print_("Unrecognized command: %s" % cmd)
        if cmd == quit_op[0]:
            six.print_("goodbye")
            sys.exit(0)
        elif cmd in (standup_op[0], forecast_op[0]):
            num_slaves = None
            while num_slaves is None:
                six.print_("Enter a number of slaves to start: ",)
                num_slaves = sys.stdin.readline().strip()
                try:
                    num_slaves = int(num_slaves)
                except Exception as _:
                    six.print_("%s isn't a number" % num_slaves)
                    num_slaves = None
            if cmd == forecast_op[0]:
                inf = make_infra_for_forecast(num_slaves=num_slaves)
                six.print_("\nPrices for cluster with %d slaves:" % num_slaves)
                for cloud in [CITYCLOUD, RACKSPACE]:
                    six.print_(">>>>>For %s:" % cloud)
                    six.print_(create_price_table(inf, for_cloud=cloud))
                    six.print_()
                # add in another for vsphere
                inf = make_infra_for_forecast(num_slaves=num_slaves,
                                              infra_class=VSHadoopInfra)
                six.print_(">>>>>For %s:" % VSPHERE)
                six.print_(create_price_table(inf, for_cloud=VSPHERE))
                six.print_()
                continue
            # if we get here, we're standing up; see which cloud
            cloud = None
            while cloud not in ('c', 'v', 'a'):
                six.print_("Enter 'c' for CityCloud, 'a' for Auro, 'v' for VMWare: ",)
                cloud = sys.stdin.readline().strip().lower()
            # prep all args
            kwargs = {"num_slaves": num_slaves, "handler": handler}
            on_cloud = CITYCLOUD

            cloud_name = None
            if cloud == "v":
                # add additional args for VMWare
                on_cloud = VSPHERE
                line = open("vscreds.txt", "r").readline().strip()
                h, u, p = line.split(",")
                prov = VSphereProvisionerProxy("vsphere", host=h, username=u, pwd=p)
                kwargs.update({"pkf": None,
                               "rempass": "tarnished99",
                               "infra_class": VSHadoopInfra,
                               "proxy": prov,
                               "overrides": [Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                                             Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)]})
            elif cloud == "a":
                # then use the Auro cloud
                kwargs.update({"overrides": [Var("IMAGE", "Ubuntu16.04-x86_64-20180223"),
                                             Var("AZ", "RegionOne"),
                                             Var("EXTNET", "provider"),
                                             Var("JAVA_HOME", "/usr/lib/jvm/java-8-openjdk-amd64"),
                                             Var("JAVA_VER", "openjdk-8-jre-headless", in_env=False)
                                             ]})
                cloud_name = 'auro'
            else:
                cloud_name = "citycloud"
            # record which cloud we used in the keys so we can recreate the proper one
            # on a reanimate
            mykeys = {"on_cloud": on_cloud, "cloud_name": cloud_name}
            kwargs["client_data"] = mykeys
            kwargs["cloud_name"] = cloud_name

            success, infra, ns, conf, ao = do_it(**kwargs)
            if success:
                if with_mongo:
                    from hreport import capture_running
                    six.print_("Storing model in Mongo...")
                    inst_id = capture_running(ao, "hadoop_demo")
                    six.print_("...done. Instance id is '%s'" % inst_id)
                if with_zabbix:
                    six.print_("Updating Zabbix with new hosts to monitor...")
                    from zabint import Zabact
                    try:
                        za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                        zabbix_host_ids = za.register_servers_in_group("Linux servers", [infra.name_node_fip.value()] +
                                                                       [s.slave_fip.value() for s in infra.slaves.values()],
                                                                       templates=template_list)
                        six.print_("...done")
                    except Exception as e:
                        six.print_("\nZABBIX UPDATED FAILED with %s:" % str(e))
                        six.print_("...traceback:")
                        import traceback
                        traceback.print_exception(*sys.exc_info())
                        six.print_()
                six.print_("\nStandup complete! You can reach the assets at the following IPs:")
                six.print_(">>>namenode: %s" % infra.name_node_fip.get_ip())
                six.print_(">>>slaves:")
                for s in infra.slaves.values():
                    six.print_("\t%s" % s.slave_fip.get_ip())
                six.print_("\nExecution prices for this infra:\n")
                six.print_(create_price_table(infra, for_cloud=on_cloud))
            else:
                six.print_("Orchestration failed; see the log for error messages")
        elif cmd == teardown_op[0]:
            six.print_("Tearing down; won't be able to re-run later")
            assert isinstance(ao, ActuatorOrchestration)
            if not ao.provisioner_proxies:
                client_keys = ao.client_keys
                on_cloud = client_keys["on_cloud"]
                if on_cloud == CITYCLOUD:
                    cloud_name = client_keys["cloud_name"]
                    ao.set_provisioner_proxies([OpenStackProvisionerProxy(cloud_name=cloud_name)])
                elif on_cloud == VSPHERE:
                    line = open("vscreds.txt", "r").readline().strip()
                    h, u, p = line.split(",")
                    ao.set_provisioner_proxies([VSphereProvisionerProxy("vsphere", host=h, username=u, pwd=p)])
                else:
                    raise Exception("Unknown cloud %s; can't tell what provisioner to make" % on_cloud)
            success = ao.teardown_system()
            if success:
                if inst_id is not None and with_mongo:
                    from hreport import capture_terminated
                    six.print_("Recording instance terminated in Mongo")
                    capture_terminated(ao, inst_id)
                    six.print_("...done")
                if zabbix_host_ids and with_zabbix:
                    six.print_("Removing hosts from zabbix")
                    from zabint import Zabact
                    za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                    za.deregister_servers(zabbix_host_ids)
                    six.print_("...done")
                six.print_("\n...done! Your system has been de-commissioned")
                six.print_("quitting now")
                break
            else:
                six.print_("Orchestration failed; see the log for error messages")
        elif cmd == load_op[0]:
            six.print_("Enter name of file to load: ",)
            fname = sys.stdin.readline().strip()
            if not os.path.exists(fname):
                six.print_("File can't be found! (%s)" % fname)
            else:
                try:
                    json_dict = open(fname, "r").read()
                except Exception as e:
                    six.print_("Got an exception reading %s: %s" % (fname, str(e)))
                else:
                    d = json.loads(json_dict)
                    ao = reanimate_from_dict(d)
                    if with_viz:
                        ao.set_event_handler(handler)
                    six.print_("Orchestrator reanimated!")
        elif cmd == persist_op[0]:
            six.print_("Enter name of the file to save to: ",)
            fname = sys.stdin.readline().strip()
            six.print_("Creating persistable form...")
            try:
                d = persist_to_dict(ao)
                json_dict = json.dumps(d)
            except Exception as e:
                six.print_("FAILED GETTING PERSISTED FORM; t = %s, v = %s" % (type(e), str(e)))
                six.print_("the story is:")
                for s in get_narration():
                    six.print_(s)
            else:
                six.print_("Writing persisted form out...")
                f = open(fname, "w")
                f.write(json_dict)
                six.print_("Orchestrator persisted!")
        elif cmd == rerun_op[0]:
            six.print_("Re-running initiate")
            success = ao.initiate_system()
            if success:
                if with_mongo:
                    from hreport import capture_running

                    six.print_("Storing model in Mongo...")
                    inst_id = capture_running(ao, "hadoop_demo")
                    six.print_("...done. Instance id is '%s'" % inst_id)
                if with_zabbix:
                    six.print_("Updating Zabbix with new hosts to monitor...")
                    from zabint import Zabact
                    try:
                        za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                        zabbix_host_ids = za.register_servers_in_group("Linux servers", [infra.name_node_fip.value()] +
                                                                       [s.slave_fip.value() for s in infra.slaves.values()],
                                                                       templates=template_list)
                        six.print_("...done")
                    except Exception as e:
                        six.print_("\nZABBIX UPDATED FAILED with %s:" % str(e))
                        six.print_("...traceback:")
                        import traceback
                        traceback.print_exception(*sys.exc_info())
                        six.print_()
                six.print_("\n...done! You can reach the assets at the following IPs:")
                six.print_(">>>namenode: %s" % infra.name_node_fip.get_ip())
                six.print_(">>>slaves:")
                for s in infra.slaves.values():
                    six.print_("\t%s" % s.slave_fip.get_ip())
                    six.print_("\nExecution prices for this infra:\n")
                    six.print_(create_price_table(infra, for_cloud=on_cloud))
            else:
                six.print_("Orchestration failed; see the log for error messages")
