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
from actuator.namespace import NamespaceModel
'''
Created on Mar 16, 2016

@author: Tom Carroll
'''
import socket
from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.utils import find_file
from actuator.config import ConfigModel


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
    assert conn is pea.get_connection(host, user, password=password)
    
    
def test05():
    """
    Test forcing a new Paramiko connection even if one is available
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
    new_conn = pea.get_connection(host, user, password=password, fresh=True)
    assert conn is not new_conn

    
def do_all():
    setup_module()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
