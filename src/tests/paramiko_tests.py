# 
# Copyright (c) 2016 Tom Carroll
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
Created on Mar 16, 2016

@author: Tom Carroll
'''
import socket
import traceback
import sys
import os, os.path

from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.utils import find_file
from actuator.config import ConfigModel, with_config_options, with_dependencies
from actuator.config_tasks import (PingTask, CommandTask)
from actuator.namespace import Var, Role, NamespaceModel, with_variables


def find_ip():
    hostname = socket.gethostname()
    get_ip = socket.gethostbyname(hostname)
    if get_ip == "127.0.0.1":
        #try to find a better one; try a Linux convention
        hostname = "{}.local".format(hostname)
        try:
            get_ip = socket.gethostbyname(hostname)
        except Exception, _:
            pass
    return get_ip


def setup_module():
    pass

config_options = dict(remote_user="lxle1",
                      private_key_file=find_file("lxle1-dev-key"))


class TestConfigModel(ConfigModel):
    pass


class TestNamespaceModel(NamespaceModel):
    pass


def test01():
    """
    Test acquiring a Paramiko connection referring to a priv key file
    """
    user = "lxle1"
    pkey_file = find_file("lxle1-dev-key")
    host = socket.gethostname()
    
    cm = TestConfigModel("test01")
    nm = TestNamespaceModel()
    
    pea = ParamikoExecutionAgent(config_model_instance=cm,
                                 namespace_model_instance=nm)
    conn = pea.get_connection(host, user, priv_key_file=pkey_file)
    assert conn
    pea.return_connection(host, user, conn, dirty=True)
    assert True
    
    
def test02():
    """
    Test acquiring a Paramiko connection using a priv key
    """
    user = "lxle1"
    pkey_file = find_file("lxle1-dev-key")
    pkey = open(pkey_file, "r").read().strip()
    host = find_ip()

    cm = TestConfigModel("test02")
    nm = TestNamespaceModel()
    
    pea = ParamikoExecutionAgent(config_model_instance=cm,
                                 namespace_model_instance=nm)
    conn = pea.get_connection(host, user, priv_key=pkey)
    assert conn
    pea.return_connection(host, user, conn, dirty=True)
    assert True
    

def test03():
    """
    Test acquiring a Paramiko connection using a password
    """
    user = "lxle1"
    password = open("/home/lxle1/Documents/pass", "r").read().strip()
    host = find_ip()

    cm = TestConfigModel("test03")
    nm = TestNamespaceModel()
    
    pea = ParamikoExecutionAgent(config_model_instance=cm,
                                 namespace_model_instance=nm)
    conn = pea.get_connection(host, user, password=password)
    assert conn
    pea.return_connection(host, user, conn, dirty=True)
    assert True
    
    
def test04():
    """
    Test re-acquiring the same Paramiko connection for the same user/host
    """
    user = "lxle1"
    password = open("/home/lxle1/Documents/pass", "r").read().strip()
    host = find_ip()

    cm = TestConfigModel("test03")
    nm = TestNamespaceModel()
    
    pea = ParamikoExecutionAgent(config_model_instance=cm,
                                 namespace_model_instance=nm)
    conn = pea.get_connection(host, user, password=password)
    assert conn
    pea.return_connection(host, user, conn)
    # Doesn't really do anything but get rid of the client
#     assert conn is pea.get_connection(host, user, password=password)


def test05():
    user = "lxle1"
    password = open("/home/lxle1/Documents/pass", "r").read().strip()
    host = find_ip()

    cm = TestConfigModel("test03")
    nm = TestNamespaceModel()
    
    pea = ParamikoExecutionAgent(config_model_instance=cm,
                                 namespace_model_instance=nm)
    conn = pea.get_connection(host, user, password=password)
#     assert conn.invoke_shell() is not conn.invoke_shell()
    
    
class SingleRoleNS(NamespaceModel):
    target = Role("testTarget", host_ref=find_ip())
    
    
def test06():
    """
    Test a simple ping using Paramiko
    """
    class NS06(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()))
        target = Role('target', host_ref=find_ip())
    ns = NS06()
    
    class C06(ConfigModel):
        with_config_options(remote_user="lxle1",
                            private_key_file=find_file("lxle1-dev-key"))
        ping = PingTask("ping", task_role=NS06.target)
    cfg = C06()
    
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    try:
        pea.perform_config()
    except Exception as e:
        if not len(pea.get_aborted_tasks()):
            print("Missing aborted task message; need to find where it should be")
        else:
            print("Here are the traces:")
            for task, et, ev, tb in pea.get_aborted_tasks():
                print(">>>>Task: %s" % task.name)
                traceback.print_exception(et, ev, tb)
                print()
            print("Traces done")
        assert False, e.message
                
                
def test07():
    """
    test07: Test a very simple command task using Paramiko
    """
    class C07(ConfigModel):
        with_config_options(remote_user="lxle1",
                            private_key_file=find_file("lxle1-dev-key"))
        ls = CommandTask("list", "ls -l", task_role=SingleRoleNS.target)
    ns = SingleRoleNS()
    cfg = C07("list")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    
    try:
        pea.perform_config()
    except Exception as e:
        if not len(pea.get_aborted_tasks()):
            print("Missing aborted task messages; need to find where they are!!")
        else:
            print("Here are the traces:")
            for task, et, ev, tb in pea.get_aborted_tasks():
                print(">>>>>>Task %s:" % task.name)
                traceback.print_exception(et, ev, tb, file=sys.stdout)
                print()
        assert False, e.message
        
        
def test08():
    """
    test08: Try running two similar commands at the same time
    """
    class C08(ConfigModel):
        with_config_options(**config_options)
        ls1 = CommandTask("list1", "ls -l", task_role=SingleRoleNS.target)
        ls2 = CommandTask("list2", "ls -l /tmp", task_role=SingleRoleNS.target)

    ns = SingleRoleNS()
    cfg = C08("double list")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    
    try:
        pea.perform_config()
    except Exception as e:
        if not len(pea.get_aborted_tasks()):
            print("Missing aborted task messages; need to find where they are!!")
        else:
            print("Here are the traces:")
            for task, et, ev, tb in pea.get_aborted_tasks():
                print(">>>>>>Task %s:" % task.name)
                traceback.print_exception(et, ev, tb, file=sys.stdout)
                print()
        assert False, e.message
        
        
def test09():
    """
    test09: do a chdir before running the command to create a file
    """
    class C09(ConfigModel):
        with_config_options(**config_options)
        rm1 = CommandTask("rm1", "rm -f asdf", task_role=SingleRoleNS.target,
                          chdir="/tmp")
        touch1 = CommandTask("touch1", "touch asdf",
                             task_role=SingleRoleNS.target,
                             chdir="/tmp")
        with_dependencies(rm1 | touch1)

    ns = SingleRoleNS()
    cfg = C09("remove/create")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    
    try:
        pea.perform_config()
    except Exception as e:
        if not len(pea.get_aborted_tasks()):
            print("Missing aborted task messages; need to find where they are!!")
        else:
            print("Here are the traces:")
            for task, et, ev, tb in pea.get_aborted_tasks():
                print(">>>>>>Task %s:" % task.name)
                traceback.print_exception(et, ev, tb, file=sys.stdout)
                print()
        assert False, e.message
    else:
        assert os.path.exists("/tmp/asdf")
        
        
def test10():
    """
    test10: check that trying to chdir to a non-exitent directory causes an error
    """
    class C10(ConfigModel):
        with_config_options(**config_options)
        ls = CommandTask("ls", "ls -l", task_role=SingleRoleNS.target,
                         chdir="/wibble")
    
    ns = SingleRoleNS()
    cfg = C10("bad chdir")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    
    try:
        pea.perform_config()
    except:
        assert True
    else:
        assert False, "This should should have failed the cddir"

def do_all():
    setup_module()
    test10()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
