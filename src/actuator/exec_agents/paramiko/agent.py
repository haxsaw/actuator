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
from collections import deque
from cStringIO import StringIO
from paramiko import (SSHClient, SSHException, BadHostKeyException, AuthenticationException,
                      AutoAddPolicy, RSAKey)

from actuator.exec_agents.core import (ExecutionAgent, ExecutionException,
                                       AbstractTaskProcessor)
from actuator.utils import capture_mapping


_paramiko_domain = "PARAMIKO_AGENT"


class PTaskProcessor(AbstractTaskProcessor):
    
    def make_args(self, task, hlist):
        AbstractTaskProcessor.make_args(self, task, hlist)
        
    def result_check(self, task, result, logfile=None):
        return
    
    
class PingProcessor(PTaskProcessor):
    pass


class ParamikoExecutionAgent(ExecutionAgent):
    def __init__(self, **kwargs):
        super(ParamikoExecutionAgent, self).__init__(**kwargs)
        self.connection_cache = {}
        self.cache_lock = threading.RLock()
        
    def get_connection(self, host, user, priv_key=None, priv_key_file=None, password=None,
                       timeout=20, fresh=False):
        with self.cache_lock:
            conn_deque = self.connection_cache.get((host, user))
            if not conn_deque:
                conn_deque = deque()
                self.connection_cache[(host, user)] = conn_deque
        try:
            if fresh:
                raise IndexError("force new connection")
            conn = conn_deque.popleft()
        except IndexError:
            # we need a new connection
            conn = SSHClient()
            conn.set_missing_host_key_policy(AutoAddPolicy())
            try:
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
            
    def return_connection(self, host, user, conn, dirty=False):
        """
        Return a connection to the available list for this host/user pair. If the
        connection is irrepairably dirty (say a chroot has been done) then get rid
        of it altogether.
        
        @param host: string; a hostname or IP for the host the connection is with
        @param user: string; the user that is logged into the host
        @param conn: a Paramiko SSHClient object
        @param dirty: boolean, optional. If 'true' then the connection should be
            closed as the state it is left in may make it impossible for other
            tasks to use the connection
        """
        assert isinstance(conn, SSHClient)
        if dirty:
            conn.close()
            del conn
        else:
            self.connection_cache[(host, user)].append(conn)
        
    @classmethod
    def get_exec_domain(cls):
        return _paramiko_domain
    
    def _perform_with_args(self, task, args, kwargs):
        pass
    