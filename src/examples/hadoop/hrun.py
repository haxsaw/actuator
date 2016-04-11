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
from actuator import ActuatorOrchestration
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from actuator.utils import persist_to_dict, reanimate_from_dict
from hadoop import HadoopInfra, HadoopNamespace, HadoopConfig

user_env = "OS_USER"
pass_env = "OS_PASS"
tenant_env = "OS_TENANT"
auth_env = "OS_AUTH"

def do_it(uid, pwd, tenant, url, num_slaves=1):
    # this is what's needed to use the models
    inf = HadoopInfra("infra")
    namespace = HadoopNamespace()
    conf = HadoopConfig(remote_user="ubuntu",
                        private_key_file="actuator-dev-key")
    namespace.create_slaves(num_slaves)
        
    os_prov = OpenstackProvisioner(uid, pwd, tenant, url, num_threads=5, cloud_name="trystack")
    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 provisioner=os_prov,
                                 namespace_model_inst=namespace,
                                 config_model_inst=conf)
    success = ao.initiate_system()
    return success, inf, namespace, cfg, orch
    

if __name__ == "__main__":
    # this is all command line and environment processing overhead
    if (not os.environ.get(user_env) or not os.environ.get(pass_env) or
            not os.environ.get(auth_env)):
        print "\n>>>Environment variables missing!"
        help()
        sys.exit(1)
        
    success = infra = ns = cfg = ao = None
    json_file = None
    quit = False
    persist_op = "p=persist model"
    standup_op = "s=stand-up hadoop"
    rerun_op = "r=re-run stand-up"
    teardown_op = "t=teardown known system"
    load_op = "l=load persisted model"
    quit_op = "q=quit"
    uid = os.environ.get(user_env)
    pwd = os.environ.get(pass_env)
    tenant = os.environ.get(tenant_env, user_env)
    url = os.environ.get(auth_env)
    while not quit:
        ops = [quit_op, load_op]
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
        elif cmd == standup_op[0]:
            num_slaves = None
            while not num_slaves:
                print "Enter a number of slaves to start:",
                num_slaves = sys.stdin.readline().strip()
                try:
                    num_slaves = int(num_slaves)
                except Exception, _:
                    print "%s isn't a number" % num_slaves
                    num_slaves = None
            success, infra, ns, cfg, ao = do_it(uid, pwd, tenant, url, num_slaves=num_slaves)
            if success:
                print "\n...done! You can reach the reach the assets at the following IPs:"
                print ">>>namenode: %s" % infra.name_node_fip.get_ip()
                print ">>>slaves:"
                for s in infra.slaves.values():
                    print "\t%s" % s.slave_fip.get_ip()
            else:
                print "Orchestration failed; see the log for error messages"
        elif cmd == teardown_op[0]:
            print "Tearing down; won't be able to re-run later"
            if not ao.provisioner:
                ao.set_provisioner(OpenstackProvisioner(cloud_name="trystack", num_threads=5))
            success = ao.teardown_system()
            if success:
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
                print "\n...done! You can reach the reach the assets at the following IPs:"
                print ">>>namenode: %s" % infra.name_node_fip.get_ip()
                print ">>>slaves:"
                for s in infra.slaves.values():
                    print "\t%s" % s.slave_fip.get_ip()
            else:
                print "Orchestration failed; see the log for error messages"

        
#     args = [a.lower() for a in sys.argv]
#     show_help = reduce(lambda x, a: x or a.startswith("-h"), args, False)
#     if show_help:
#         help()
#         sys.exit(0)
#         
#     try:
#         num_slaves = int(sys.argv[1]) if len(sys.argv) > 1 else 1
#     except Exception, e:
#         print "you must supply an int arg for more slaves; error=%s" % e.message
#         help()
#         sys.exit(1)
#         
#     uid = os.environ.get(user_env)
#     pwd = os.environ.get(pass_env)
#     tenant = os.environ.get(tenant_env, user_env)
#     url = os.environ.get(auth_env)
#     
#     success, infra, ns, cfg, ao = do_it(uid, pwd, tenant, url, num_slaves=num_slaves)
#     if success:
#         print "\n...done! You can reach the reach the assets at the following IPs:"
#         print ">>>namenode: %s" % infra.name_node_fip.get_ip()
#         print ">>>slaves:"
#         for s in infra.slaves.values():
#             print "\t%s" % s.slave_fip.get_ip()
#     else:
#         print "Orchestration failed; see the log for error messages"
#     
#     cmd = ""
#     while cmd != 'q':
#         print "Now what? r=re-run initiate, t=teardown system, q=quit"
#         print "(r/t/q): "
#         cmd = sys.stdin.readline()
#         cmd = cmd.strip().lower()
#         cmd = cmd[0] if len(cmd) else ""
#         if cmd == "r":
#             print "Re-running initiate"
#             success = ao.initiate_system()
#             if success:
#                 print "\n...done! You can reach the reach the assets at the following IPs:"
#                 print ">>>namenode: %s" % infra.name_node_fip.get_ip()
#                 print ">>>slaves:"
#                 for s in infra.slaves.values():
#                     print "\t%s" % s.slave_fip.get_ip()
#             else:
#                 print "Orchestration failed; see the log for error messages"
#         elif cmd == "t":
#             print "Tearing down; won't be able to re-run later"
#             success = ao.teardown_system()
#             if success:
#                 print "\n...done! Your system has been de-commissioned"
#                 print "quitting now"
#                 break
#             else:
#                 print "Orchestration failed; see the log for error messages"
#         elif cmd == "q":
#             print "goodbye"
#             break
#         elif cmd == "":
#             continue
#         else:
#             print "Unrecognized command '%s'" % cmd

