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
from actuator.config import with_dependencies, MultiTask, ConfigClassTask
from actuator.namespace import MultiRole

'''
Created on Oct 21, 2014
'''

import getpass
import sys
import socket
import os
import os.path
import stat
from actuator import (NamespaceModel, Var, Role, ConfigModel, PingTask,
                      with_variables, ExecutionException, CommandTask,
                      ScriptTask, CopyFileTask, InfraModel, StaticServer,
                      ProcessCopyFileTask, ctxt, with_config_options,
                      NullTask, TaskGroup)
from actuator.exec_agents.ansible.agent import AnsibleExecutionAgent
from actuator.utils import find_file


def setup():
    #make sure the private key is read-only for the owner
    pkeyfile = find_file("lxle1-dev-key")
    os.chmod(pkeyfile, stat.S_IRUSR|stat.S_IWUSR)
    
    
user_home = os.path.expanduser("~")


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


def test001():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
      
def test002():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Role("ping-target", host_ref="!{PING_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
    
def test003():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", "not.an.get_ip.addy"))
        ping_target = Role("ping-target", host_ref="!{PING_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target,
                        repeat_count=1)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert False, "This should have caused an error to be raised"
    except ExecutionException, e:
        assert len(ea.get_aborted_tasks()) == 1
        
def test004():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("HOME", user_home))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = CommandTask("cmd", "/bin/ls !{HOME}", task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test005():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = CommandTask("cmd", "/bin/ls", chdir=user_home,
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test006():
    """test006 should raise an exception during perform_config() because
    /bin/wibble doesn't exist"""
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = CommandTask("cmd", "/bin/wibble", chdir=user_home,
                           task_role=SimpleNamespace.cmd_target,
                           repeat_count=1)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert False, "this should have failed"
    except ExecutionException, e:
        assert len(ea.get_aborted_tasks()) == 1

def test007():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        ping = CommandTask("cmd", "/bin/ls", chdir="!{WHERE}",
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message

def test008():
    #NOTE: this will only work with nose if run from the actuator/src directory
    #the test expects to find a directory named "tests" under the current
    #directory
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
           
    class SimpleConfig(ConfigModel):
        ping = ScriptTask("script", os.path.join(os.getcwd(), "tests", "test008.sh"),
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message
        
def test009():
    #NOTE: this will only work with nose if run from the actuator/src directory
    #the test expects to find a directory named "tests" under the current
    #directory
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("DEST", "/tmp"),
                       Var("PKG", "actuator"))
        copy_target = Role("copy_target", host_ref=find_ip())
    ns = SimpleNamespace()
    
    class SimpleConfig(ConfigModel):
        cleanup = CommandTask("clean", "/bin/rm -rf !{PKG}", chdir="!{DEST}",
                              task_role=SimpleNamespace.copy_target,
                              repeat_count=1)
        copy = CopyFileTask("copy-file", "!{DEST}",
                            src=os.path.join(os.getcwd(), "!{PKG}"),
                            task_role=SimpleNamespace.copy_target,
                            repeat_count=1)
        with_dependencies(cleanup | copy)
        
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb)
            print
        assert False, e.message
    
def test010():
    class SimpleInfra(InfraModel):
        testbox = StaticServer("testbox", find_ip())
    infra = SimpleInfra("simple")
        
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Role("cmd-target", host_ref=SimpleInfra.testbox)
    ns = SimpleNamespace()
    ns.compute_provisioning_for_environ(infra)
          
    class SimpleConfig(ConfigModel):
        ping = CommandTask("cmd", "/bin/ls", chdir="!{WHERE}",
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        assert False, e.message
        
        
# def find_file(filename, start_path=None):
#     if start_path is None:
#         start_path = os.getcwd()
#     if os.path.isabs(filename):
#         test_file_path = filename
#     else:
#         test_file_path = None
#         for root, _, files in os.walk(start_path):
#             if filename in files:
#                 test_file_path = os.path.join(root, filename)
#                 break
#     assert test_file_path, "Can't find the test file {}; aborting test".format(filename)
#     return test_file_path


def test011():
    """
    test011: this test checks the basic behavior of the ProcessCopyFileTask.
    The copied file should have the supplied Vars replacing the variable
    references in the file. 
    """
    test_file = "test011.txt"
    test_file_path = find_file(test_file)
    
    class SimpleInfra(InfraModel):
        testbox = StaticServer("testbox", find_ip())
    infra = SimpleInfra("simple")
    
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("DEST", "/tmp/!{FILE}"),
                       Var("FILE", test_file),
                       Var("var1", "summat"),
                       Var("var2", "or"),
                       Var("var3", "the"),
                       Var("var4", "other"))
        target = Role("target", host_ref=SimpleInfra.testbox)
    ns = SimpleNamespace()
        
    class SimpleConfig(ConfigModel):
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        file_content = file("/tmp/test011.txt", "r").read()
        assert "summat or the other" == file_content
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message

def test012():
    """
    test012: this checks ProcessCopyFileTask if not all Vars are supplied.
    The variable 'var3' won't be supplied. 
    """
    test_file = "test012.txt"
    test_file_path = find_file(test_file)
    
    class SimpleInfra(InfraModel):
        testbox = StaticServer("testbox", find_ip())
    infra = SimpleInfra("simple")
    
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("DEST", "/tmp/!{FILE}"),
                       Var("FILE", test_file),
                       Var("var1", "summat"),
                       Var("var2", "or"),
#                        Var("var3", "the"),  #This one is to be missing
                       Var("var4", "other"))
        target = Role("target", host_ref=SimpleInfra.testbox)
    ns = SimpleNamespace()
        
    class SimpleConfig(ConfigModel):
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert False, "this should have raised an exception about not finding var3"
    except ExecutionException, _:
        found_it = False
        for _, _, value, _ in ea.get_aborted_tasks():
            if 'var3' in value.message:
                found_it = True
                break
        assert found_it, "an exception was raised, but not about missing var3"

def test013():
    """
    test013: Similar to test011, but with multi-line files.
    The replacements should be made across all lines of the file 
    """
    test_file = "test013.txt"
    test_file_path = find_file(test_file)
    
    class SimpleInfra(InfraModel):
        testbox = StaticServer("testbox", find_ip())
    infra = SimpleInfra("simple")
    
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("DEST", "/tmp/!{FILE}"),
                       Var("FILE", test_file),
                       Var("var1", "summat"),
                       Var("var2", "or"),
                       Var("var3", "the"),
                       Var("var4", "other"))
        target = Role("target", host_ref=SimpleInfra.testbox)
    ns = SimpleNamespace()
        
    class SimpleConfig(ConfigModel):
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        file_content = [l.strip()
                        for l in file("/tmp/test013.txt", "r").readlines()]
        assert "summat or" == file_content[0] and "the other" == file_content[1]
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message

def test014():
    """
    test014: multiple copies of the same task going against the same host to
    see if any parallel processing issues arise. 
    """
    test_file = "test014-BigTextFile.txt"
    test_file_path = find_file(test_file)
    
    class SimpleInfra(InfraModel):
        testbox = StaticServer("testbox", find_ip())
    infra = SimpleInfra("simple")
    
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PREFIX", ctxt.name),
                       Var("DEST", "/tmp/!{PREFIX}-!{FILE}"),
                       Var("FILE", test_file))
        target = MultiRole(Role("target", host_ref=SimpleInfra.testbox))
    ns = SimpleNamespace()
    
    class SingleCopy(ConfigModel):
        reset = CommandTask("014_reset", "/bin/rm -rf !{DEST}", removes="!{DEST}")
        copy = CopyFileTask("014_cpf", "!{DEST}",
                            src=test_file_path)
        with_dependencies(reset | copy)
        
    class MultiCopy(ConfigModel):
        task_suite = MultiTask("all-copies", ConfigClassTask("one-copy", SingleCopy),
                               SimpleNamespace.q.target.all())
        
    cfg = MultiCopy()
    
    for i in range(5):
        _ = ns.target[i]
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               num_threads=5, no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message

def test015():
    "test015: try pinging as another user"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER", "lxle1"))
        ping_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target,
                        remote_user="!{RUSER}",
                        private_key_file=find_file("lxle1-dev-key"))
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test016():
    "test016: try writing a file into another user's directory"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER", "lxle1"),
                       Var("HOME", user_home))
        copy_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        copy = CopyFileTask("cpf", "!{HOME}/tmp/failure.txt",
                            task_role=SimpleNamespace.copy_target,
                            remote_user="!{RUSER}",
                            private_key_file=find_file("lxle1-dev-key"),
                            content="This shouldn't get written!\n",
                            )
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert False, "This copy should not have succeeded"
    except ExecutionException, _:
        pass
      
def test017():
    "test017: ping as another user, use password instead of key: requires sshpass, but frequently fails anyway with a Broken Pipe for some reason"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER", "lxle1"),
                       Var("RPASS", file("/home/lxle1/Documents/pass", "r").read().strip()))
        ping_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target,
                        remote_user="!{RUSER}",
                        remote_pass="!{RPASS}")
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test018():
    "test018: ping as two different users"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER1", "lxle1"))
        ping1_target = Role("ping1-target", host_ref=find_ip())
        ping2_target = Role("ping2-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        ping1 = PingTask("ping", task_role=SimpleNamespace.ping1_target,
                        remote_user="!{RUSER1}",
                        private_key_file=find_file("lxle1-dev-key"))
        ping2 = PingTask("ping", task_role=SimpleNamespace.ping2_target)
    cfg = SimpleConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test019():
    "test019: clear and copy files"
    the_ip = find_ip()
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", the_ip),
                       Var("RUSER1", "lxle1"),
                       Var("RUSER2", getpass.getuser()),
                       Var("TARGET", "019target.txt"),
                       Var("DIRPATH", "/home/!{RUSER}/tmp"),
                       Var("FILEPATH", "!{DIRPATH}/!{TARGET}"))
        copy1_target = Role("copy1_target", host_ref=the_ip,
                                 variables=[Var("RUSER", "!{RUSER1}")])
        copy2_target = Role("copy2_target", host_ref=the_ip,
                                 variables=[Var("RUSER", "!{RUSER2}")])
    ns = SimpleNamespace()
     
    class CopyConfig(ConfigModel):
        make = CommandTask("make", "/bin/mkdir -p !{DIRPATH}",
                           creates="!{DIRPATH}")
        remove = CommandTask("remove", "/bin/rm -f !{FILEPATH}")
        copy = CopyFileTask("copy-file", "!{FILEPATH}",
                            content="This should be in !{RUSER}'s tmp\n")
        with_dependencies(make | remove | copy)
         
    class CopyAllConfig(ConfigModel):
        u1_copy = ConfigClassTask("u1-copy", CopyConfig,
                                  task_role=SimpleNamespace.copy1_target,
                                  remote_user="!{RUSER}",
                                  private_key_file=find_file("lxle1-dev-key"))
        u2_copy = ConfigClassTask("u2-copy", CopyConfig,
                                  task_role=SimpleNamespace.copy2_target,
                                  remote_user="!{RUSER}")
         
        
    cfg = CopyAllConfig()
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert (os.path.exists(ns.copy1_target.var_value("FILEPATH")) and
                os.path.exists(ns.copy2_target.var_value("FILEPATH")))
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test020():
    "test020: write some data to a user's tmp dir based on config-level user"
    from datetime import datetime
    target = "/home/lxle1/tmp/020test.txt"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("TARGET_FILE", target))
        copy_target = Role("copy-target", host_ref=find_ip())
    ns = SimpleNamespace()
    
    now_str = datetime.now().ctime()
    class SimpleConfig(ConfigModel):
        copy = CopyFileTask("cpf", "!{TARGET_FILE}",
                            task_role=SimpleNamespace.copy_target,
                            content="This content created at: {}\n".format(now_str),
                            )
    #we're testing if setting the user stuff at this level works right
    cfg = SimpleConfig(remote_user="lxle1",
                       private_key_file=find_file("lxle1-dev-key"))
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert now_str in "".join(file(target, "r").readlines())
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test021():
    "test021: Have a multi-task get the proper user from the config class"
    from datetime import datetime
    target_dir = "/home/lxle1/tmp/test021"
    num_files = 5
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("TARGET_DIR", target_dir),
                       Var("COMPNUM", ctxt.name),
                       Var("FILE_NAME", "!{TARGET_DIR}/!{COMPNUM}-target.txt"))
        targets = MultiRole(Role("pseudo-role", host_ref=find_ip()))
        
    ns = SimpleNamespace()
    for i in range(num_files):
        _ = ns.targets[i]
    
    now_str = datetime.now().ctime()
    class SimpleConfig(ConfigModel):
        clear = CommandTask("clear-previous", "/bin/rm -rf !{TARGET_DIR}",
                            task_role=SimpleNamespace.targets[0])
        make = CommandTask("make-output-dir", "/bin/mkdir -p !{TARGET_DIR}",
                           task_role=SimpleNamespace.targets[0])
        copies = MultiTask("copy", CopyFileTask("cpf", "!{FILE_NAME}",
                                                content="Created at: {}\n".format(now_str)),
                           SimpleNamespace.q.targets.all())
        with_dependencies(clear | make | copies)
    #we're testing if setting the user stuff at this level works right
    cfg = SimpleConfig(remote_user="lxle1",
                       private_key_file=find_file("lxle1-dev-key"))
    
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        ea.perform_config()
        assert num_files == len(os.listdir(target_dir))
    except ExecutionException, e:
        import traceback
        for task, etype, value, tb in ea.get_aborted_tasks():
            print ">>>Task {} failed with the following:".format(task.name)
            traceback.print_exception(etype, value, tb, file=sys.stdout)
            print
        assert False, e.message
      
def test022():
    class NS022(NamespaceModel):
        def_role = Role("def_role", host_ref="127.0.0.1")
        r = Role("r", host_ref="8.8.8.8")
    ns = NS022()
    
    class C022(ConfigModel):
        with_config_options(default_run_from=NS022.def_role)
        t = NullTask("null", task_role=NS022.r)
    cfg = C022()
    
    cfg.set_namespace(ns)
    ea = AnsibleExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    assert ea._get_run_host(cfg.t) == "127.0.0.1"

def test023():
    class NS023(NamespaceModel):
        def_role = Role("def_role", host_ref="127.0.0.1")
        r = Role("r", host_ref="8.8.8.8")
    ns = NS023()
    
    class C023(ConfigModel):
        t = NullTask("null", task_role=NS023.r, run_from=NS023.def_role)
    cfg = C023()
    
    cfg.set_namespace(ns)
    ea = AnsibleExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    assert ea._get_run_host(cfg.t) == "127.0.0.1"


def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
