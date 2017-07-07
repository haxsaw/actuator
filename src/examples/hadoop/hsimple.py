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

import sys
from actuator import ActuatorOrchestration
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from hadoop import HadoopInfra, HadoopNamespace, HadoopConfig


def do_it(num_slaves=1, handler=None, pkf="actuator-dev-key", rempass=None,
          infra_class=HadoopInfra,
          provisioner=OpenstackProvisioner(num_threads=10, cloud_name="citycloud"),
          overrides=()):
    """
    Stands up a hadoop infra and configures it
    """
    inf = infra_class("infra", event_handler=handler)
    namespace = HadoopNamespace()
    namespace.add_override(*overrides)
    namespace.create_slaves(num_slaves)
    conf = HadoopConfig(remote_user="ubuntu",
                        private_key_file=pkf,
                        remote_pass=rempass,
                        event_handler=handler)

    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 provisioner=provisioner,
                                 namespace_model_inst=namespace,
                                 config_model_inst=conf,
                                 post_prov_pause=10,
                                 num_threads=20)
    try:
        success = orch.initiate_system()
    except KeyboardInterrupt:
        success = False
    return success, inf, namespace, conf, orch


if __name__ == "__main__":
    success, inf, ns, conf, orch = do_it(1)
    sys.stdout.write("Hit ctrl-d to decommission")
    sys.stdin.read()
    orch.teardown_system()
