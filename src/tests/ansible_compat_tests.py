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
# from actuator.config import with_dependencies, MultiTask, ConfigClassTask

'''
Created on Oct 21, 2014
'''

import getpass
import sys
import socket
import os
import os.path
import stat
import traceback
from actuator import (NamespaceModel, Var, Role, ConfigModel, PingTask,
                      with_variables, ExecutionException, CommandTask,
                      ScriptTask, CopyFileTask, InfraModel, StaticServer,
                      ProcessCopyFileTask, ctxt, with_config_options,
                      NullTask, with_dependencies, MultiTask,
                      ConfigClassTask, MultiRole)
from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.utils import find_file, LOG_DEBUG


def setup():
    #make sure the private key is read-only for the owner
    pkeyfile = find_file("lxle1-dev-key")
    os.chmod(pkeyfile, stat.S_IRUSR|stat.S_IWUSR)
    
    
user_home = os.path.expanduser("~lxle1")


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
        
        
config_options = dict(remote_user="lxle1",
                      private_key_file=find_file("lxle1-dev-key"))
    
    
def test001():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)
      
      
def test002():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()))
        ping_target = Role("ping-target", host_ref="!{PING_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)
    
    
def test003():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", "not.an.ip.addy"))
        ping_target = Role("ping-target", host_ref="!{PING_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target,
                        repeat_count=1)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        perform_and_complain(ea)
        assert False, "this should have failed due to the bad ip address"
    except:
        assert True

        
def test004():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("HOME", user_home))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = CommandTask("cmd", "/bin/ls !{HOME}", task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)


def test005():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = CommandTask("cmd", "/bin/ls", chdir=user_home,
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)


def test006():
    """test006 should raise an exception during perform_config() because
    /bin/wibble doesn't exist"""
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = CommandTask("cmd", "/bin/wibble", chdir=user_home,
                           task_role=SimpleNamespace.cmd_target,
                           repeat_count=1)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        perform_and_complain(ea)
        assert False, "this should have failed"
    except:
        assert len(ea.get_aborted_tasks()) == 1


def test007():
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("CMD_TARGET", find_ip()),
                       Var("WHERE", "/bin"))
        cmd_target = Role("cmd-target", host_ref="!{CMD_TARGET}")
    ns = SimpleNamespace()
          
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = CommandTask("cmd", "/bin/ls", chdir="!{WHERE}",
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)
    

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
        with_config_options(**config_options)
        ping = ScriptTask("script", os.path.join(os.getcwd(), "tests", "test008.sh"),
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

        
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
        with_config_options(**config_options)
        cleanup = CommandTask("clean", "/bin/rm -rf !{PKG}", chdir="!{DEST}",
                              task_role=SimpleNamespace.copy_target,
                              repeat_count=1)
        copy = CopyFileTask("copy-file", "!{DEST}",
                            src=os.path.join(os.getcwd(), "!{PKG}"),
                            task_role=SimpleNamespace.copy_target,
                            repeat_count=1)
        with_dependencies(cleanup | copy)
        
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

    
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
        with_config_options(**config_options)
        ping = CommandTask("cmd", "/bin/ls", chdir="!{WHERE}",
                           task_role=SimpleNamespace.cmd_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)

    perform_and_complain(ea)
        
        
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
        with_config_options(**config_options)
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)
    file_content = file("/tmp/test011.txt", "r").read()
    assert "summat or the other" == file_content


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
        with_config_options(**config_options)
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    try:
        perform_and_complain(ea)
        assert False, "this should have raised an exception about not finding var3"
    except (ExecutionException, AssertionError) as _:
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
        with_config_options(**config_options)
        reset = CommandTask("reset", "/bin/rm -rf !{DEST}", removes="!{DEST}",
                            task_role=SimpleNamespace.target)
        process = ProcessCopyFileTask("pcf", "!{DEST}",
                                      src=test_file_path,
                                      task_role=SimpleNamespace.target,
                                      repeat_count=1)
        with_dependencies(reset | process)
    cfg = SimpleConfig()
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)
    file_content = [l.strip()
                    for l in file("/tmp/test013.txt", "r").readlines()]
    assert "summat or" == file_content[0] and "the other" == file_content[1]


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
        reset = CommandTask("014_reset", "/bin/rm -f !{DEST}", removes="!{DEST}")
        copy = CopyFileTask("014_cpf", "!{DEST}",
                            src=test_file_path)
        with_dependencies(reset | copy)
        
    class MultiCopy(ConfigModel):
        with_config_options(**config_options)
        task_suite = MultiTask("all-copies", ConfigClassTask("one-copy", SingleCopy),
                               SimpleNamespace.q.target.all())
        
    cfg = MultiCopy()
    
    for i in range(5):
        _ = ns.target[i]
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               num_threads=5, no_delay=True, log_level=LOG_DEBUG)
    perform_and_complain(ea)


def test015():
    "test015: try pinging as another user"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER", "lxle1"))
        ping_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping = PingTask("ping", task_role=SimpleNamespace.ping_target,
                        remote_user="!{RUSER}",
                        private_key_file=find_file("lxle1-dev-key"))
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
def test016():
    "test016: try writing a file into another user's directory"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER", "lxle1"),
                       Var("HOME", user_home))
        copy_target = Role("ping-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        copy = CopyFileTask("cpf", "!{HOME}/tmp/failure.txt",
                            task_role=SimpleNamespace.copy_target,
                            remote_user="!{RUSER}",
                            private_key_file=find_file("lxle1-dev-key"),
                            content="This shouldn't get written!\n",
                            )
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
def test017():
    "test017: ping as another user, use password instead of key"
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
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
def test018():
    "test018: ping as two different users"
    class SimpleNamespace(NamespaceModel):
        with_variables(Var("PING_TARGET", find_ip()),
                       Var("RUSER1", "lxle1"))
        ping1_target = Role("ping1-target", host_ref=find_ip())
        ping2_target = Role("ping2-target", host_ref=find_ip())
    ns = SimpleNamespace()
       
    class SimpleConfig(ConfigModel):
        with_config_options(**config_options)
        ping1 = PingTask("ping", task_role=SimpleNamespace.ping1_target,
                        remote_user="!{RUSER1}",
                        private_key_file=find_file("lxle1-dev-key"))
        ping2 = PingTask("ping", task_role=SimpleNamespace.ping2_target)
    cfg = SimpleConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
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
        with_config_options(**config_options)
        u1_copy = ConfigClassTask("u1-copy", CopyConfig,
                                  task_role=SimpleNamespace.copy1_target,
                                  remote_user="!{RUSER}",
                                  private_key_file=find_file("lxle1-dev-key"))
        u2_copy = ConfigClassTask("u2-copy", CopyConfig,
                                  task_role=SimpleNamespace.copy2_target,
                                  remote_user="!{RUSER}")
         
        
    cfg = CopyAllConfig()
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
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
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
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
    
    ea = ParamikoExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns,
                               no_delay=True)
    perform_and_complain(ea)

      
def test022():
    class NS022(NamespaceModel):
        def_role = Role("def_role", host_ref="127.0.0.1")
        r = Role("r", host_ref="8.8.8.8")
    ns = NS022()
    
    class C022(ConfigModel):
        with_config_options(**config_options)
        with_config_options(default_run_from=NS022.def_role)
        t = NullTask("null", task_role=NS022.r)
    cfg = C022()
    
    cfg.set_namespace(ns)
    ea = ParamikoExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
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
    ea = ParamikoExecutionAgent(config_model_instance=cfg, namespace_model_instance=ns)
    assert ea._get_run_host(cfg.t) == "127.0.0.1"


def do_all():
    setup()
    for k, v in globals().items():
        if k.startswith("test") and callable(v):
            v()
            
if __name__ == "__main__":
    do_all()
