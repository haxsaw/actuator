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
from actuator.config import with_dependencies

'''
Created on Oct 21, 2014
'''

import socket
import os.path
from actuator import (NamespaceSpec, Var, Component, ConfigSpec, PingTask,
                      with_variables, ExecutionException, CommandTask,
                      ScriptTask, CopyFileTask)
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
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
      
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
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
    
def test003():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("PING_TARGET", "not.an.ip.addy"))
        ping_target = Component("ping-target", host_ref="!PING_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = PingTask("ping", task_component=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
        assert False, "This should have caused an error to be raised"
    except ExecutionException, e:
        assert "not.an.ip.addy" in e.message
        
def test004():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Component("cmd-target", host_ref="!CMD_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = CommandTask("cmd", "/bin/ls /home/tom", task_component=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test005():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Component("cmd-target", host_ref="!CMD_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = CommandTask("cmd", "/bin/ls", chdir="/home/tom",
                           task_component=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test006():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Component("cmd-target", host_ref="!CMD_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = CommandTask("cmd", "/bin/wibble", chdir="/home/tom",
                           task_component=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
        assert False, "this should have failed"
    except ExecutionException, e:
        assert "failed on" in e.message

def test007():
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Component("cmd-target", host_ref="!CMD_TARGET!")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigSpec):
        ping = CommandTask("cmd", "/bin/ls", chdir="!WHERE!",
                           task_component=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test008():
    #NOTE: this will only work with nose if run from the actuator/src directory
    #the test expects to find a directory named "tests" under the current
    #directory
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Component("cmd-target", host_ref="!CMD_TARGET!")
    ns = SimpleNamespace()
           
    class SimpleConfig(ConfigSpec):
        ping = ScriptTask("script", os.path.join(os.getcwd(), "tests", "test008.sh"),
                           task_component=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
        
def test009():
    #NOTE: this will only work with nose if run from the actuator/src directory
    #the test expects to find a directory named "tests" under the current
    #directory
    class SimpleNamespace(NamespaceSpec):
        with_variables(Var("DEST", "/tmp"),
                       Var("PKG", "actuator"))
        copy_target = Component("copy_target", host_ref=find_ip())
    ns = SimpleNamespace()
    
    class SimpleConfig(ConfigSpec):
        cleanup = CommandTask("clean", "/bin/rm -f !PKG!", chdir="!DEST!",
                              task_component=SimpleNamespace.copy_target)
        copy = CopyFileTask("copy-file", "!DEST!",
                            src=os.path.join(os.getcwd(), "!PKG!"),
                            task_component=SimpleNamespace.copy_target)
        with_dependencies(cleanup | copy)
        
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
    

def do_all():
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()