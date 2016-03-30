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

from nose import SkipTest

from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.utils import find_file
from actuator.config import ConfigModel, with_config_options, with_dependencies
from actuator.config_tasks import (PingTask, CommandTask, ScriptTask, ShellTask,
                                   CopyFileTask, LocalCommandTask)
from actuator.namespace import (Var, Role, NamespaceModel, with_variables)


here, this_file = os.path.split(__file__)


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
    with_variables(Var("CMD_TARGET", find_ip()),
                   Var("WHERE", "/bin"))
    target = Role("testTarget", host_ref=find_ip())
    
    
def perform_and_complain(pea):
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
    perform_and_complain(pea)
                
                
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
    
    perform_and_complain(pea)
        
        
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
    
    perform_and_complain(pea)
        
        
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
        perform_and_complain(pea)
    except:
        raise
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
        
        
def test11():
    """
    test11: check that the 'creates' kwarg causes the task to be skipped
    """
    to_remove = "/tmp/xyz"
    class C11(ConfigModel):
        with_config_options(**config_options)
        touch = CommandTask("touch", "touch /tmp/abc",
                            task_role=SingleRoleNS.target,
                            creates="/tmp/xyz")
    ns = SingleRoleNS()
    cfg = C11("create skip")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    
    #now create the /tmp/xyz file
    try:
        os.remove("/tmp/xyz")
    except:
        pass
    f = open("/tmp/xyz", "w")
    f.close()
    
    try:
        os.remove("/tmp/abc")
    except:
        pass
    
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert os.path.exists("/tmp/xyz")
        assert not os.path.exists("/tmp/abc")
        
        
def test11a():
    """
    test11a: check that a 'creates' where the test file doesn't exist does run
    """
    class C11a(ConfigModel):
        with_config_options(**config_options)
        touch = CommandTask("touch", "touch /tmp/def", task_role=SingleRoleNS.target,
                            creates="/tmp/def")
    ns = SingleRoleNS()
    cfg = C11a("create doesn't exist")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)

    try:
        os.remove("/tp/def")
    except:
        pass
    
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert os.path.exists("/tmp/def")
        
        
def test12():
    """
    test12: check that 'removes' kwarg causes the task to be skipped
    """
    class C12(ConfigModel):
        with_config_options(**config_options)
        touch = CommandTask("touch", "touch /tmp/mno",
                         task_role=SingleRoleNS.target,
                         removes="/tmp/jkl")
        
    ns = SingleRoleNS()
    cfg = C12("remove skip")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)

    try:
        os.remove("/tmp/jkl")
    except:
        pass
    
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert not os.path.exists("/tmp/mno")


def test13():
    """
    test13: run a simple script
    """
    class C13(ConfigModel):
        with_config_options(**config_options)
        script = ScriptTask("script13",
                            os.path.join(here, "test013.sh"),
                            task_role=SingleRoleNS.target)
    ns = SingleRoleNS()
    cfg = C13("run test13 script")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert os.path.exists("/tmp/test013Out.txt")                                  
        assert not os.path.exists("/tmp/test013.sh")
        
        
def test13a():
    """
    test13a: run a simple script with replacements
    """
    class C13a(ConfigModel):
        with_config_options(**config_options)
        script = ScriptTask("script13a",
                            os.path.join(here, "test013a.sh"),
                            task_role=SingleRoleNS.target,
                            proc_ns=True)
    ns = SingleRoleNS()
    cfg = C13a("run test13a script")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert os.path.exists("/tmp/test013aOut.txt")
        assert not os.path.exists("/tmp/test013a.sh")
        
        
def test14():
    """
    test14: check the ShellTask (same as CommandTask)
    """
    class C14(ConfigModel):
        with_config_options(**config_options)
        task = ShellTask("shell ls", "ls -l",
                         chdir="/tmp",
                         task_role=SingleRoleNS.target)
    
    ns = SingleRoleNS()
    cfg = C14("shell task")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)


def test15():
    """
    test15: back to CommandTask one last time; try running another shell
    """
    class C15(ConfigModel):
        with_config_options(**config_options)
        task = CommandTask("dash!", "ls -l",
                           task_role=SingleRoleNS.target,
                           executable="/bin/dash")
        
    ns = SingleRoleNS()
    cfg = C15("alt shell")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)
        
        
def test16():
    """
    test16: Run a command with shell metachars and see they don't expand
    """
    class C16(ConfigModel):
        with_config_options(**config_options)
        task = CommandTask("echo-1", "/bin/echo $PATH > test16",
                           task_role=SingleRoleNS.target,
                           chdir="/tmp")
        
    ns = SingleRoleNS()
    cfg = C16("echo-1")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    try:
        perform_and_complain(pea)
    except:
        raise
    else:
        assert not os.path.exists("/tmp/test16")
        
        
def test17():
    """
    test17: Run a shell with shell metachars and see they are respected
    """
    thefile = "/tmp/test17"
    class C17(ConfigModel):
        with_config_options(**config_options)
        task = ShellTask("echo-2", "/bin/echo $PATH > !{SINK_FILE}",
                           task_role=SingleRoleNS.target)
        check = CommandTask("check", "test -e !{SINK_FILE}",
                            task_role=SingleRoleNS.target)
        rm = CommandTask("rm", "rm !{SINK_FILE}",
                         task_role=SingleRoleNS.target)
        with_dependencies(task | check | rm)
        
    ns = SingleRoleNS()
    ns.add_variable(Var("SINK_FILE", thefile))
    cfg = C17("echo-2")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)
    
#
# NOTE:
# test18 normally raises SkipTest as the test is predicated on the user running the test
# having their known_hosts file containing credentials for the user named in the
# rem_user variable for localhost. Since this can't be guaranteed this test
# is usually skipped, but it can be activated simply by commenting out the
# raise SkipTest after replacing the value of rem_user with a credentialed user name.
        
def test18():
    """
    test18: check logging in when using system keys only
    """
    rem_user = "tom"
    raise SkipTest("See comment; only run this test if the credentials for 'rem_user' to localhost "
                     "are in the current user's known_hosts")
    class C18(ConfigModel):
        with_config_options(remote_user=rem_user)
        ping = PingTask("system-keys-ping", task_role=SingleRoleNS.target)
 
    ns = SingleRoleNS()
    cfg = C18("system-creds-check")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)
        
        
def test19():
    """
    test19: simple copy file test
    """
    there = os.path.join("/tmp", this_file)
    class C19(ConfigModel):
        with_config_options(**config_options)
        cp = CopyFileTask("sendit", there, src=__file__,
                          task_role=SingleRoleNS.target)
        check1 = LocalCommandTask("check there", "/usr/bin/test -e %s" % there,
                                  task_role=SingleRoleNS.target)
        diff = LocalCommandTask("diff", "diff %s %s" % (there, __file__),
                                task_role=SingleRoleNS.target)
        rm = CommandTask("removeit", "rm %s" % there,
                         task_role=SingleRoleNS.target)
        check2 = LocalCommandTask("check gone", "/usr/bin/test ! -e %s" % there,
                                  task_role=SingleRoleNS.target)
        with_dependencies(cp | check1 | diff | rm | check2)
        
    ns = SingleRoleNS()
    cfg = C19("local command and simple copy")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)
        
        
def test20():
    """
    test20: copy a file from memory
    """
    there = os.path.join("/tmp", this_file)
    my_content = open(__file__, "r").read()
    class C20(ConfigModel):
        with_config_options(**config_options)
        cp = CopyFileTask("sendit", there, content=my_content,
                          task_role=SingleRoleNS.target)
        check1 = LocalCommandTask("check there", "/usr/bin/test -e %s" % there,
                                  task_role=SingleRoleNS.target)
        diff = LocalCommandTask("diff", "diff %s %s" % (there, __file__),
                                task_role=SingleRoleNS.target)
        rm = CommandTask("removeit", "rm %s" % there,
                         task_role=SingleRoleNS.target)
        check2 = LocalCommandTask("check gone", "/usr/bin/test ! -e %s" % there,
                                  task_role=SingleRoleNS.target)
        with_dependencies(cp | check1 | diff | rm | check2)

    ns = SingleRoleNS()
    cfg = C20("copy content from memory")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)
        
        
def test21():
    """
    test21: try copying a whole directory hierarchy including the root
    """
    dir_to_copy = here
    dest = os.path.join("/tmp", os.path.split(here)[-1])
    class C21(ConfigModel):
        with_config_options(**config_options)
        check1 = LocalCommandTask("check gone", "/usr/bin/test ! -e %s" % dest,
                                  task_role=SingleRoleNS.target)
        cp = CopyFileTask("copy-dir-with-root", "/tmp", src=dir_to_copy,
                          task_role=SingleRoleNS.target)
        check2 = LocalCommandTask("check there", "/usr/bin/test -e %s" % dest,
                                  task_role=SingleRoleNS.target)
        rm = CommandTask("rmdir", "rm -rf %s" % dest,
                         task_role=SingleRoleNS.target)
        
        with_dependencies(check1 | cp | check2 | rm)

    ns = SingleRoleNS()
    cfg = C21("copy directory with root")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)   


def test22():
    """
    test22: copy a whole directory but not the root
    """
    dir_to_copy = "%s/" % here
    dest = "/tmp/terst"
    this_new = os.path.join(dest, this_file)
    class C22(ConfigModel):
        with_config_options(**config_options)
        check1 = LocalCommandTask("check gone", "/usr/bin/test ! -e %s" % dest,
                                  task_role=SingleRoleNS.target)
        mkdir = CommandTask("mkdir", "mkdir %s" % dest,
                            task_role=SingleRoleNS.target)
        cp = CopyFileTask("copy-dir-without-root", dest, src=dir_to_copy,
                          task_role=SingleRoleNS.target)
        check2 = LocalCommandTask("check there", "/usr/bin/test -e %s" % this_new,
                                  task_role=SingleRoleNS.target)
        rm = CommandTask("rm", "rm -rf %s" % dest,
                         task_role=SingleRoleNS.target)
        with_dependencies(check1 | mkdir | cp | check2 | rm)
        
    ns = SingleRoleNS()
    cfg = C22("copy directory without root")
    pea = ParamikoExecutionAgent(config_model_instance=cfg,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    perform_and_complain(pea)   


def do_all():
    setup_module()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
