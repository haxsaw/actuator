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
Created on Mar 15, 2016

@author: Tom Carroll
'''

import threading
import socket
import uuid
import base64
from collections import deque
from cStringIO import StringIO
import time
import shlex
import os.path

from paramiko import (SSHClient, SSHException, BadHostKeyException, AuthenticationException,
                      AutoAddPolicy, RSAKey)

from actuator.exec_agents.core import (ExecutionAgent, ExecutionException,
                                       AbstractTaskProcessor)
from actuator.utils import capture_mapping
from actuator.config_tasks import (ConfigTask, PingTask, ScriptTask,
                                   CommandTask, ShellTask)


_paramiko_domain = "PARAMIKO_AGENT"


class _Result(object):
    def __init__(self, success, result_code, stdout, stderr):
        self.success = success
        self.result_code = result_code
        self.stdout = stdout
        self.stderr = stderr


class PTaskProcessor(AbstractTaskProcessor):
    
    ctrl_d = chr(4)
    
    def __init__(self, *args, **kwargs):
        super(PTaskProcessor, self).__init__(*args, **kwargs)
        prompt = base64.b64encode(str(uuid.uuid4()))[-7:-1]
        self.prompt = "actuator-%s-ready$ " % prompt
        self.output = []
        
    def make_args(self, task, hlist):
        """
        Set up the standard args for the task and then get any specific args for
        the particular task.
        
        @param task: Some kind of L{actuator.config_tasks.ConfigTask object
        @param hlist: a sequence of strings that are either host names or IP addresses
            that the task is to apply to; this is a single host, but is a list
            for compatibility with other execution agents
        @return: A two-tuple consisting of a sequence of positional arguments and dict
            of keyword arguments. The position arguments will always contain:
            
            (task, host, user)
            
            And the dict will always contain the following keys (but some values may be None):
                priv_key
                priv_key_file
                password
                timeout
                dirty (always False)
            Other key/values may exist that are relevant to the specific task processor
        """
        assert isinstance(task, ConfigTask)
        user = task.get_remote_user()
        if not user:
            raise ExecutionException("Unable to determine a remote user for task %s; can't continue" %
                                     user)
        seq = (task, hlist[0], user)
        kwargs = {"password": task.get_remote_pass(),
                  "priv_key_file": task.get_private_key_file(),
                  "timeout": 20,
                  "priv_key": None,
                  "dirty": False}
        kwargs.update(self._make_args(task))
        return seq, kwargs
    
    def _make_args(self, task):
        return {}
        
    def result_check(self, task, result, logfile=None):
        return
    
    def process_task(self, pea, task, host, user, password=None, priv_key_file=None, priv_key=None,
                      dirty=False, timeout=20, **kwargs):
        assert isinstance(pea, ParamikoExecutionAgent)
        client = pea.get_connection(host, user, priv_key=priv_key, priv_key_file=priv_key_file,
                                    password=password, timeout=timeout)
        try:
            result = self._process_task(client, task, **kwargs)
        finally:
            pea.return_connection(host, user, client, dirty=dirty)
        return result
            
    def _process_task(self, client, task, **kwargs):
        pass
    
    read_chunk = 4096
    
    def _drain(self, channel, until=None):
        if until is None:
            until = self.prompt
        results = []
        prompt_seen = False
        while channel.recv_ready() or not prompt_seen:
            chunk = channel.recv(self.read_chunk)
            results.append(chunk)
            if until in chunk:
                prompt_seen = True
            else:
                prompt_seen = False
        sio = StringIO("".join(results))
        return [l for l in sio]
    
    def _get_shell(self, client, width=200):
        sh = client.invoke_shell(width=width)
        sh.send("PS1='%s'\n" % self.prompt)
        time.sleep(0.2)
        return sh
    
    def _was_success(self, channel):
        channel.send("echo $?\n")
        result = self._drain(channel)
        sio = StringIO("".join(result))
        _ = sio.readline().strip()
        line = sio.readline().strip()
        success = False
        ecode = -1
        try:
            val = int(line)
            if val == 0:
                success = True
            else:
                ecode = val
        except:
            pass
        return success, ecode
    
    def _populate_environment(self, channel, task):
        env_dict = task.task_variables(for_env=True)
        for k, v in env_dict.items():
            channel.sendall("export %s=%s\n" % (k, v))
            self.output.append("".join(self._drain(channel)))
            

@capture_mapping(_paramiko_domain, PingTask)
class PingProcessor(PTaskProcessor):
    def _process_task(self, client, task, **kwargs):
        sh = self._get_shell(client)
        sh.close()
        result = _Result(True, 0, "", "")
        return result
    
    
@capture_mapping(_paramiko_domain, ScriptTask)
class ScriptProcessor(PTaskProcessor):
    def _make_args(self, task):
        args = {"free_form": task.free_form,
                "creates": task.creates,
                "removes": task.removes}
        return args
    
    def _start_shell(self, client):
        sh = self._get_shell(client)
        welcome = self._drain(sh)
        return sh
    
    def _test_creates(self, sh, creates):
        sh.sendall("test -e %s\n" % creates)
        self.output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        return success

    def _test_removes(self, sh, removes):
        sh.sendall("test ! -e %s\n" % removes)
        self.output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        return success
        
    def _process_task(self, client, task, free_form=None, creates=None, removes=None):
        assert isinstance(client, SSHClient)
        sh = self._start_shell(client)
        skip = False
        
        if free_form is None:
            raise ExecutionException("There is no text in the script task %s" % task.name)
    
        parts = shlex.split(free_form)
        script = parts[0]
        if not os.path.exists(script) or not os.path.isfile(script):
            raise ExecutionException("Can't find the script '%s' on the local system" % script)
        
        try:
            f = open(script, "rb")
        except Exception as e:
            raise ExecutionException("Can't open the script '%s' to copy it to the remote system:%s"
                                     % (str(e), script))
        
        if creates is not None:
            skip = self._test_creates(sh, creates)
            
        if not skip and removes is not None:
            skip = self._test_removes(sh, removes)
            
        self._populate_environment(sh, task)
            
        if not skip:
            script_path, sfile = os.path.split(script)
            tmp_script = "/tmp/%s" % sfile
            #make sure we can create the script
            sh.send("touch %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Unable to create the remote script file %s: %s"
                                         % (tmp_script, "error code %s" % ecode))
                
            #now transmit the script
            sh.send("cat > %s\n" % tmp_script)
            for l in f:
                sh.sendall(l)
            sh.sendall("\n")
            sh.sendall(self.ctrl_d)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Unable to transmit the script %s to the remote host: %s"
                                         % (tmp_script, "error code %s" % ecode))
            
            #ensure the script is executable
            sh.sendall("chmod 755 %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Could not make the remote script %s executable: %s"
                                         % (tmp_script, "error code %s" % ecode))
            
            #execute the script
            remote_command = "%s %s" % (tmp_script, " ".join(parts[1:]))
            sh.sendall("%s\n" % remote_command)
            self.output.append("".join(self._drain(sh)))
            
            #check exit status
            success, ecode = self._was_success(sh)
            
            #remove the script
            sh.sendall("rm %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
        else:
            success = ecode = 0
            
        f.close()
    
        return _Result(success, ecode, "".join(self.output), "")
        

@capture_mapping(_paramiko_domain, CommandTask)
class CommandProcessor(ScriptProcessor):
    def _make_args(self, task):
        args = super(CommandProcessor, self)._make_args(task)
        args.update( {"chdir": task.chdir,
                      "executable": task.executable,
                      "warn": task.warn} )
        return args
    
    def _process_task(self, client, task, free_form=None, creates=None, removes=None,
                      chdir=None, executable=None, warn=None, **kwargs):
        output = []
        sh = self._get_shell(client)
        _ = self._drain(sh)
        if chdir is not None:
            sh.sendall("cd %s\n" % chdir)
            output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Unable to change to directory '%s': %s" %
                                         (chdir, "".join(output)))
                
        skip_command = False
        if creates is not None:
            skip_command = self._test_creates(sh, creates)
        
        if removes is not None and not skip_command:
            skip_command = self._test_removes(sh, removes)
                
        self._populate_environment(sh, task)
        
        if not skip_command:
            sh.sendall("%s\n;" % free_form)
            time.sleep(0.2)
            output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        result = _Result(success, ecode, "".join(output), "")
        return result
    
    
@capture_mapping(_paramiko_domain, ShellTask)
class ShellProcessor(CommandProcessor):
    pass


class ParamikoExecutionAgent(ExecutionAgent):
    def __init__(self, **kwargs):
        super(ParamikoExecutionAgent, self).__init__(**kwargs)
        self.connection_cache = {}
        self.in_process_locks = {}
        self.cache_lock = threading.RLock()
        
    def get_connection(self, host, user, priv_key=None, priv_key_file=None, password=None,
                       timeout=5):
        """
        Get a Paramiko encrypted connection for a particular host/user pair
        
        Returns a Paramiko SSHClient object connected to the specified host as the specified
        user. The remaining arguments deal with credentials and connection timing.
        
        @param host: string. The host name or ip to perform the SSH connection to.
        @param user: string. The name of the user to connect as.
        @param priv_key: string, optional. The private RSA key to use for authentication for
            this host and user.
        @param priv_key_file: string, optional. A file that contains the RSA key for the
            named host and user.
        @param password: string, optional. The user's password for logging into the named host.
        
        One of priv_key, priv_key_file, or password must be supplied in order to connect
        to the host.
        
        @return: A connected Paramiko SSHClient instance.
        @raise ExecutionException: Raised for incorrect arguments (missing credentials) or
            various inabilities to connect to the specified host as the provided user.
        """
        conn = None
        
        if priv_key is None and priv_key_file is None and password is None:
            raise ExecutionException("Can't get connection to host; one of priv_key, "
                                     "priv_key_file, or password must be supplied in "
                                     "order to connect")
            
        try:
            conn = SSHClient()
            conn.set_missing_host_key_policy(AutoAddPolicy())
            if priv_key:
                sio = StringIO(priv_key)
                priv_key = RSAKey.from_private_key(sio)
            conn.connect(hostname=host, username=user, timeout=timeout,
                     pkey=priv_key, key_filename=priv_key_file,
                     password=password)
        except (BadHostKeyException, AuthenticationException) as e:
            raise ExecutionException("Encountered authentication problem: %s" % str(e))
        except SSHException as e:
            raise ExecutionException("Encountered non-authentication SSH problem: %s" % str(e))
        except socket.error as e:
            raise ExecutionException("Encountered socket error when trying to "
                                     "create an SSH connection: %s" % str(e))
        return conn

        #@FIXME Paramiko can't handle more than one channel on a single client
        #so the follow is commented out until that is corrected
#         while not conn:
#             wait_on_ipc = False
#             with self.cache_lock:
#                 conn = self.connection_cache.get((host, user))
#                 if not conn:
#                     ipc = self.in_process_locks.get((host, user))
#                     if not ipc:
#                         ipc = threading.Lock()
#                         self.in_process_locks[(host, user)] = ipc
#                         ipc.acquire()
#                     else:
#                         wait_on_ipc = True
#             if wait_on_ipc:
#                 ipc.acquire()
#                 ipc.release()
#                 continue
#             elif not conn:
#                 conn = SSHClient()
#                 conn.set_missing_host_key_policy(AutoAddPolicy())
#                 try:
#                     try:
#                         if priv_key:
#                             sio = StringIO(priv_key)
#                             priv_key = RSAKey.from_private_key(sio)
#                         conn.connect(hostname=host, username=user, timeout=timeout,
#                                  pkey=priv_key, key_filename=priv_key_file,
#                                  password=password)
#                     except (BadHostKeyException, AuthenticationException) as e:
#                         raise ExecutionException("Encountered authentication problem: %s" % str(e))
#                     except SSHException as e:
#                         raise ExecutionException("Encountered non-authentication SSH problem: %s" % str(e))
#                     except socket.error as e:
#                         raise ExecutionException("Encountered socket error when trying to "
#                                                  "create an SSH connection: %s" % str(e))
#                     else:
#                         with self.cache_lock:
#                             self.connection_cache[(host, user)] = conn
#                             del self.in_process_locks[(host, user)]
#                 finally:
#                     ipc.release()
#                     
#         return conn
        
    def return_connection(self, host, user, conn, dirty=False):
        """
        Return a connection to the available list for this host/user pair. If the
        connection is irrepairably dirty (say a chroot has been done) then get rid
        of it altogether.
        
        @param host: string; a hostname or IP for the host the connection is with
        @param user: string; the user that is logged into the host
        @param conn: a Paramiko SSHClient object
        @param dirty: boolean, optional. If 'true' then the connection should be
            closed as it is somehow no longer usable
        """
        #@FIXME once Paramiko can properly handle more than one
        #channel on a client then we can use the code below
        assert isinstance(conn, SSHClient)
        conn.close()
        return
#         assert isinstance(conn, SSHClient)
#         if dirty:
#             with self.cache_lock:
#                 del self.connection_cache[(host, user)]
#             conn.close()
#             del conn
        
    @classmethod
    def get_exec_domain(cls):
        return _paramiko_domain
    
    def _perform_with_args(self, task, processor, args, kwargs):
        processor.process_task(self, *args, **kwargs)
    