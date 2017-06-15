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
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from actuator.utils import persist_to_dict, reanimate_from_dict
from hadoop import HadoopInfra, HadoopNamespace
from prices import create_price_table
from hsimple import do_it
from hevent import TaskEventManager

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


def make_infra_for_forcast(num_slaves=1):
    inf = HadoopInfra("forecast")
    ns = HadoopNamespace()
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
            print("Ensure that you've set the ZABBIX_SERVER environment var to the public IP of the server,")
            print("and that ZABBIX_PRIVATE is set to the internal IP of the server")

    if with_mongo:
        print("Ensure that mongod is running")

    if with_viz:
        print("Visualisation activated")
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
        print "%s" % (",".join(ops))
        print "/".join([o[0] for o in ops]), ": ",
        cmd = sys.stdin.readline().strip().lower()
        if not cmd or cmd[0] not in [o[0] for o in ops]:
            print "Unrecognized command: %s" % cmd
        if cmd == quit_op[0]:
            print "goodbye"
            sys.exit(0)
        elif cmd in (standup_op[0], forecast_op[0]):
            num_slaves = None
            while num_slaves is None:
                print "Enter a number of slaves to start: ",
                num_slaves = sys.stdin.readline().strip()
                try:
                    num_slaves = int(num_slaves)
                except Exception, _:
                    print "%s isn't a number" % num_slaves
                    num_slaves = None
            if cmd == forecast_op[0]:
                inf = make_infra_for_forcast(num_slaves=num_slaves)
                print("\nPrices for cluster with %d slaves:" % num_slaves)
                print(create_price_table(inf))
                print()
                continue
            success, infra, ns, conf, ao = do_it(num_slaves=num_slaves, handler=handler)
            if success:
                if with_mongo:
                    from hreport import capture_running
                    print("Storing model in Mongo...")
                    inst_id = capture_running(ao, "hadoop_demo")
                    print("...done. Instance id is '%s'" % inst_id)
                if with_zabbix:
                    print("Updating Zabbix with new hosts to monitor...")
                    from zabint import Zabact
                    za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                    zabbix_host_ids = za.register_servers_in_group("Linux servers", [infra.name_node_fip.value()] +
                                                                   [s.slave_fip.value() for s in infra.slaves.values()],
                                                                   templates=template_list)
                    print("...done")
                print "\nStandup complete! You can reach the assets at the following IPs:"
                print ">>>namenode: %s" % infra.name_node_fip.get_ip()
                print ">>>slaves:"
                for s in infra.slaves.values():
                    print "\t%s" % s.slave_fip.get_ip()
                print("\nExecution prices for this infra:\n")
                print(create_price_table(infra))
            else:
                print "Orchestration failed; see the log for error messages"
        elif cmd == teardown_op[0]:
            print "Tearing down; won't be able to re-run later"
            if not ao.provisioner:
                ao.set_provisioner(OpenstackProvisioner(cloud_name="citycloud", num_threads=5))
            success = ao.teardown_system()
            if success:
                if inst_id is not None and with_mongo:
                    from hreport import capture_terminated
                    print("Recording instance terminated in Mongo")
                    capture_terminated(ao, inst_id)
                    print("...done")
                if zabbix_host_ids and with_zabbix:
                    print("Removing hosts from zabbix")
                    from zabint import Zabact
                    za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                    za.deregister_servers(zabbix_host_ids)
                    print("...done")
                print "\n...done! Your system has been de-commissioned"
                print "quitting now"
                break
            else:
                print "Orchestration failed; see the log for error messages"
        elif cmd == load_op[0]:
            print "Enter name of file to load: ",
            fname = sys.stdin.readline().strip()
            if not os.path.exists(fname):
                print "File can't be found! (%s)" % fname
            else:
                try:
                    json_dict = file(fname, "r").read()
                except Exception, e:
                    print "Got an exception reading %s: %s" % (fname, e.message)
                else:
                    d = json.loads(json_dict)
                    ao = reanimate_from_dict(d)
                    print "Orchestrator reanimated!"
        elif cmd == persist_op[0]:
            print "Enter name of the file to save to: ",
            fname = sys.stdin.readline().strip()
            print "Creating persistable form..."
            d = persist_to_dict(ao)
            json_dict = json.dumps(d)
            print "Writing persisted form out..."
            f = file(fname, "w")
            f.write(json_dict)
            print "Orchestrator persisted!"
        elif cmd == rerun_op[0]:
            print "Re-running initiate"
            success = ao.initiate_system()
            if success:
                print "\n...done! You can reach the assets at the following IPs:"
                print ">>>namenode: %s" % infra.name_node_fip.get_ip()
                print ">>>slaves:"
                for s in infra.slaves.values():
                    print "\t%s" % s.slave_fip.get_ip()
            else:
                print "Orchestration failed; see the log for error messages"
