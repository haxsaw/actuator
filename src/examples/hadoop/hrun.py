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

import os
import sys
from actuator import ActuatorOrchestration
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from hadoop import HadoopInfra, HadoopNamespace, HadoopConfig

user_env = "OS_USER"
pass_env = "OS_PASS"
tenant_env = "OS_TENANT"
auth_env = "OS_AUTH"

def help():
        print "Usage: %s [-h]|[int]" % sys.argv[0]
        print "where the optional [int] is the number of slaves to allocate"
        print "the default is 1 slave"
        print "You must supply environment variables for:"
        print "  Openstack user with %s" % user_env
        print "  Openstack user's password with %s" % pass_env
        print ("  Openstack tenant with %s (optional; if not set %s "
               "value will be used" % (tenant_env, user_env))
        print "  Openstack auth uri with %s" % auth_env


def do_it(uid, pwd, tenant, url, num_slaves=1):
    #this is what's needed to use the models
    infra = HadoopInfra("infra")
    ns = HadoopNamespace()
    cfg = HadoopConfig(remote_user="ubuntu",
                       private_key_file="actuator-dev-key")
    for i in range(num_slaves):
        _ = ns.slaves[i]
        
    os_prov = OpenstackProvisioner(uid, pwd, tenant, url, num_threads=5)
    ao = ActuatorOrchestration(infra_model_inst=infra,
                               provisioner=os_prov,
                               namespace_model_inst=ns,
                               config_model_inst=cfg)
    ao.initiate_system()
    return infra, ns, cfg
    

if __name__ == "__main__":
    #this is all command line and environment processing overhead
    if (not os.environ.get(user_env) or not os.environ.get(pass_env) or
            not os.environ.get(auth_env)):
        print "\n>>>Environment variables missing!"
        help()
        sys.exit(1)
        
    args = [a.lower() for a in sys.argv]
    show_help = reduce(lambda x, a: x or a.startswith("-h"), args, False)
    if show_help:
        help()
        sys.exit(0)
        
    try:
        num_slaves = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    except Exception, e:
        print "you must supply an int arg for more slaves; error=%s" % e.message
        help()
        sys.exit(1)
        
    uid = os.environ.get(user_env)
    pwd = os.environ.get(pass_env)
    tenant = os.environ.get(tenant_env, user_env)
    url = os.environ.get(auth_env)
    
    infra, ns, cfg = do_it(uid, pwd, tenant, url, num_slaves=num_slaves)
    print "\n...done! You can reach the reach the assets at the following IPs:"
    print ">>>namenode: %s" % infra.name_node_fip.get_ip()
    print ">>>slaves:"
    for s in infra.slaves.values():
        print "\t%s" % s.slave_fip.get_ip()

