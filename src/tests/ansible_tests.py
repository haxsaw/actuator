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

'''
Created on Oct 21, 2014
'''

import socket
from actuator import NamespaceSpec, Var, Component, ConfigSpec, PingTask, with_variables
from actuator.exec_agents.ansible.agent import AnsibleExecutionAgent


def find_ip():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    if ip == "127.0.0.1":
        #try to find a better one; try a Linux convention
        hostname = "{}.local".format(hostname)
        try:
            ip = socket.gethostbyname(hostname)
        except Exception, _:
            pass
    return ip


def test001():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Component("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigSpec):
        ping = PingTask("ping", task_component=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    ea.perform_config()
      
def test002():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Component("ping-target", host_ref="!PING_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = PingTask("ping", task_component=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    ea.perform_config()
    

def do_all():
    test002()
#     for k, v in globals().items():
#         if k.startswith("test") and callable(v):
#             v()
            
if __name__ == "__main__":
    do_all()
