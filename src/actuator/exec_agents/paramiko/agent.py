# -*- coding: utf-8 -*-
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

import sys
import platform
import threading
import socket
import uuid
import base64
import time
import shlex
import os.path
try:
    import subprocess32
except ImportError:
    import subprocess as subprocess32
import tempfile

from paramiko import (SSHClient, SSHException, BadHostKeyException, AuthenticationException,
                      AutoAddPolicy, RSAKey, SFTPClient, SFTPAttributes)

from actuator.exec_agents.core import (ExecutionAgent, ExecutionException,
                                       AbstractTaskProcessor)
from actuator.utils import capture_mapping, LOG_INFO
from actuator.config_tasks import (ConfigTask, PingTask, ScriptTask,
                                   CommandTask, ShellTask, CopyFileTask, ProcessCopyFileTask,
                                   LocalCommandTask)
from actuator.namespace import _ComputableValue
from actuator.service import ServiceModel
from errator import narrate, narrate_cm
if sys.version.startswith("2"):
    from six.moves import StringIO
else:
    from six.moves import cStringIO as StringIO


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
        full_prompt = str(uuid.uuid4())
        prompt = base64.b64encode(full_prompt.encode() if hasattr(full_prompt, "encode") else full_prompt)[-7:-1]
        self.prompt = "actuator-%s-ready$ " % (prompt.decode() if hasattr(prompt, "decode") else prompt)
        self.output = []

    @narrate(lambda s, t, h: "...which started the generic arguments creation process "
                             "for {} task {}".format(t.__class__.__name__, t.name))
    def make_args(self, task, hlist):
        """
        Set up the standard args for the task and then get any specific args for
        the particular task.
        
        @param task: Some kind of L{actuator.config_tasks.ConfigTask} object
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
        if hlist is None or len(hlist) is 0:
            raise ExecutionException("There are no hosts to apply task {} to".format(task.name))
        seq = (task, hlist[0], user)
        with narrate_cm("...during which the collection of passwords and key files started"):
            kwargs = {"password": task.get_remote_pass(),
                      "priv_key_file": task.get_private_key_file(),
                      "timeout": 20,
                      "priv_key": None,
                      "dirty": False}
        with narrate_cm("...and then the collection of the task-specific arguments started"):
            kwargs.update(self._make_args(task))
        return seq, kwargs
    
    def _make_args(self, task):
        return {}

    @narrate(lambda s, t, r, **kw: "...which then led to checking the result of {} task {}"
                                   .format(t.__class__.__name__, t.name))
    def result_check(self, task, result, logfile=None):
        assert isinstance(result, _Result)
        if not result.success:
            if logfile:
                logfile.write("Task %s (%s) failed; output follows:\n%s" %
                              (task.name, task._id, result.stdout))
            raise ExecutionException("Task %s failed; output: %s" %
                                     (task.name, result.stdout))
        else:
            return

    @narrate(lambda s, p, t, h, u, **kw: "...starting the Paramiko processing of {} task "
                                         "{} against host {} for user {}".format(t.__class__.__name__, t.name, h, u))
    def process_task(self, pea, task, host, user, password=None, priv_key_file=None, priv_key=None,
                     dirty=False, timeout=20, **kwargs):
        assert isinstance(pea, ParamikoExecutionAgent)
        with narrate_cm("...which required acquiring a Paramiko connection"):
            client = pea.get_connection(host, user, priv_key=priv_key, priv_key_file=priv_key_file,
                                        password=password, timeout=timeout)
        result = False
        try:
            with narrate_cm("...leading to the task-specific processing"):
                result = self._process_task(client, task, **kwargs)
        finally:
            pea.return_connection(host, user, client, dirty=dirty)
        return result
            
    def _process_task(self, client, task, **kwargs):
        pass
    
    read_chunk = 4096

    @narrate("...which started the output draining process")
    def _drain(self, channel, until=None):
        if until is None:
            until = self.prompt
        until = until.decode("utf-8") if hasattr(until, "decode") else until
        prompt_seen = False
        results = b"".decode("utf-8")
        while channel.recv_ready() or not prompt_seen:
            chunk = channel.recv(self.read_chunk)
            results += chunk.decode("utf-8") if hasattr(chunk, "decode") else chunk
            prompt_seen = results.endswith(until)
        sio = StringIO(results)
        return [l for l in sio]

    @narrate("...requiring the acquistion of a Paramiko shell")
    def _get_shell(self, client, width=200):
        sh = client.invoke_shell(width=width)
        sh.send("PS1='%s'\n" % self.prompt)
        time.sleep(0.2)
        return sh

    @narrate("...and then required checking if the task was successful")
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
        except Exception as _:
            pass
        return success, ecode

    @narrate(lambda s, c, t: "...which required populating the environment for the task with the following values:\n{}"
                             .format("\t\n".join(["{}={}".format(k, v)
                                                  for k, v in t.task_variables(for_env=True).items()])))
    def _populate_environment(self, channel, task):
        env_dict = task.task_variables(for_env=True)
        for k, v in env_dict.items():
            channel.sendall("export %s=%s\n" % (k, v))
            self.output.append("".join(self._drain(channel)))
            

@capture_mapping(_paramiko_domain, PingTask)
class PingProcessor(PTaskProcessor):
    @narrate(lambda s, c, t, **kw: "...which led to performing ping task {} on {}".format(t.name, t.get_task_host()))
    def _process_task(self, client, task, **kwargs):
        sh = self._get_shell(client)
        sh.close()
        result = _Result(True, 0, "", "")
        return result
    
    
@capture_mapping(_paramiko_domain, ScriptTask)
class ScriptProcessor(PTaskProcessor):
    @narrate(lambda s, t: "...which required getting the remaining arguments for "
                          "script processing task {}".format(t.name))
    def _make_args(self, task):
        args = {"free_form": task.free_form,
                "creates": task.creates,
                "removes": task.removes,
                "proc_ns": task.proc_ns}
        return args

    @narrate("...leading to starting a shell")
    def _start_shell(self, client):
        sh = self._get_shell(client)
        _ = self._drain(sh)
        return sh

    @narrate(lambda s, sh, c: "...where first we check if the creates file '{}' is already there".format(c))
    def _test_creates(self, sh, creates):
        sh.sendall("test -e %s\n" % creates)
        self.output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        return success

    @narrate(lambda s, sh, r: "...where first we check if the removes file '{}' is already gone".format(r))
    def _test_removes(self, sh, removes):
        sh.sendall("test ! -e %s\n" % removes)
        self.output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        return success

    @narrate(lambda s, c, t, **kw: "...which starts processing the script task {}".format(t.name))
    def _process_task(self, client, task, free_form=None, creates=None, removes=None,
                      proc_ns=False):
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
            # make sure we can create the script
            sh.send("touch %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Unable to create the remote script file %s: %s"
                                         % (tmp_script, "error code %s" % ecode))
                
            # now transmit the script
            sh.send("cat > %s\n" % tmp_script)
            task_role = task.get_task_role()
            for l in f:
                if proc_ns:  # if true, do replace pattern expansions before sending
                    cv = _ComputableValue(l)
                    l = cv.expand(task_role, raise_on_unexpanded=True)
                sh.sendall(l)
            sh.sendall("\n")
            sh.sendall(self.ctrl_d)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Unable to transmit the script %s to the remote host: %s"
                                         % (tmp_script, "error code %s" % ecode))
            
            # ensure the script is executable
            sh.sendall("chmod 755 %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
            success, ecode = self._was_success(sh)
            if not success:
                raise ExecutionException("Could not make the remote script %s executable: %s"
                                         % (tmp_script, "error code %s" % ecode))
            
            # execute the script
            remote_command = "%s %s" % (tmp_script, " ".join(parts[1:]))
            sh.sendall("%s\n" % remote_command)
            self.output.append("".join(self._drain(sh)))
            
            # check exit status
            success, ecode = self._was_success(sh)
            
            # remove the script
            sh.sendall("rm %s\n" % tmp_script)
            self.output.append("".join(self._drain(sh)))
        else:
            success = ecode = 0
            
        f.close()
    
        return _Result(success, ecode, "".join(self.output), "")
        

@capture_mapping(_paramiko_domain, CommandTask)
class CommandProcessor(ScriptProcessor):
    @narrate(lambda s, t: "...which required getting the remaining arguments for "
                          "command processing task {}".format(t.name))
    def _make_args(self, task):
        args = super(CommandProcessor, self)._make_args(task)
        args.update({"chdir": task.chdir,
                     "executable": task.executable,
                     "warn": task.warn})
        return args

    @narrate(lambda s, c: "...at which point we needed to perform final formatting on command '{}'".format(c))
    def _format_command(self, command):
        parts = shlex.split(command)
        formatted = [parts[0]]
        for p in parts[1:]:
            formatted.append('"%s"' % p)
        return ' '.join(formatted)

    @narrate(lambda s, c, t, **kw: "...which starts processing the command task {}".format(t.name))
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
            if executable is not None:
                sh.sendall("test -x %s\n" % executable)
                self.output.append("".join(self._drain(sh)))
                success, ecode = self._was_success(sh)
                if not success:
                    raise ExecutionException("Executable '%s' either can't be found or isn't executable"
                                             % executable)
                sh.sendall("%s\n" % executable)
            ff_formatted = self._format_command(free_form)
            sh.sendall("%s\n" % ff_formatted)
            time.sleep(0.2)
            if executable is not None:
                sh.sendall("\n")
                sh.sendall(self.ctrl_d)
            output.append("".join(self._drain(sh)))
        success, ecode = self._was_success(sh)
        result = _Result(success, ecode, "".join(output), "")
        return result
    
    
@capture_mapping(_paramiko_domain, ShellTask)
class ShellProcessor(CommandProcessor):
    def _format_command(self, command):
        return command


@capture_mapping(_paramiko_domain, LocalCommandTask)
class LocalCommandProcessor(PTaskProcessor):
    @narrate(lambda s, t: "...which required getting the remaining arguments for "
                          "local command processing task {}".format(t.name))
    def _make_args(self, task):
        assert isinstance(task, LocalCommandTask)
        args = {"command": task.command}
        return args
    
    @narrate(lambda s, c, t, **kw: "...which starts processing the local command task {}".format(t.name))
    def _process_task(self, client, task, command=None):
        output = []
        args = shlex.split(command)
        sp = subprocess32.Popen(args, stdout=subprocess32.PIPE, stderr=subprocess32.STDOUT)
        for l in sp.stdout:
            output.append(l)
        sp.wait()
        success = sp.returncode == 0
        return _Result(success, sp.returncode, "".join(output), "")
            

@capture_mapping(_paramiko_domain, CopyFileTask)
class CopyFileProcessor(PTaskProcessor):
    @narrate(lambda s, t: "...which required getting the remaining arguments for "
                          "copy file processing task {}".format(t.name))
    def _make_args(self, task):
        assert isinstance(task, CopyFileTask)
        args = {"dest": task.dest,
                "backup": task.backup,
                "content": task.content,
                "directory_mode": task.directory_mode,
                "follow": task.follow,
                "force": task.force,
                "group": task.group,
                "mode": task.mode,
                "owner": task.owner,
                "selevel": task.selevel,
                "serole": task.serole,
                "setype": task.setype,
                "seuser": task.seuser,
                "src": task.src,
                "validate": task.validate}
        return args

    @narrate(lambda s, t, sftp, rp, **kw: "...leading to copying task {}'s file to {}".format(t.name, rp))
    def _put_file(self, task, sftp, rem_path, abs_local_file=None, content=None, flo=None,
                  mode=None, owner=None, group=None):
        # flo is a "file-like object" from which we get content and send it to the remote
        assert isinstance(sftp, SFTPClient)
        
        if content is not None:
            f = sftp.open(rem_path, mode="w")
            f.write(content)
            f.close()
        elif flo is not None:
            pass
            f = sftp.open(rem_path, mode="w")
            for l in flo:
                f.write(l)
            f.close()
        else:
            if not os.path.exists(abs_local_file):
                return False, "The local file %s doesn't exist" % abs_local_file
            if not os.path.isfile(abs_local_file):
                return False, "%s isn't a plain file" % abs_local_file
            sftp.put(abs_local_file, rem_path)
            
        if mode is not None:
            sftp.chmod(rem_path, int(mode))
        elif abs_local_file is not None:
            # make the mode the same as the local file if not otherwise spec'd
            fstat = os.stat(abs_local_file)
            sftp.chmod(rem_path, fstat.st_mode)
            
        if owner is not None or group is not None:
            stat = sftp.stat(rem_path)
            assert isinstance(stat, SFTPAttributes)
            owner = owner if owner is not None else stat.st_uid
            group = group if group is not None else stat.st_gid
            sftp.chown(rem_path, owner, group)
        
        return True, ""

    @staticmethod
    @narrate("...which initiated setting the remote directory's perms")
    def _set_dir_perms(sftp, rem_dir, local_dir, mode=None, owner=None,
                       group=None):
        rstat = sftp.stat(rem_dir)
        if owner is not None or group is not None:
            owner = owner if owner is not None else rstat.st_uid
            group = group if group is not None else rstat.st_gid
            with narrate_cm(lambda o, g: "---which tried to set the owner/group to {}/{}".format(o, g),
                            owner, group):
                sftp.chown(rem_dir, owner, group)
            
        if mode is None:
            lstat = os.stat(local_dir)
            mode = lstat.st_mode
        with narrate_cm(lambda m: "---which tried to set the mod to {}".format(m),
                        mode):
            sftp.chmod(rem_dir, mode)
        
        return True, ""

    @staticmethod
    @narrate(lambda s, rp: "...leading to create the remote path {}".format(rp))
    def _make_dir(sftp, rem_path):
        assert isinstance(sftp, SFTPClient)
        sftp.mkdir(rem_path)
        
        return True, ""
    
    @narrate(lambda s, c, t, **kw: "...which starts processing the copy file task {}".format(t.name))
    def _process_task(self, client, task, dest, backup=None, content=None, directory_mode=None,
                      follow=False, force=True, group=None, mode=None, owner=None,
                      selevel="s0", serole=None, setype=None, seuser=None, src=None,
                      validate=None):

        if src is None and content is None:
            raise ExecutionException("Task %s can't run; neither src nor content were supplied"
                                     % task.name)
            
        sftp = client.open_sftp()

        if (src is not None and not os.path.isdir(src)) or content is not None:
            if src is not None and content is None and mode is None:
                fstat = os.stat(src)
                mode = fstat.st_mode
            success, ecode = self._put_file(task, sftp, dest, abs_local_file=src, content=content, mode=mode,
                                            owner=owner, group=group)
        elif src is not None and os.path.isdir(src):
            with_root = not src.endswith("/")
            _, tail = os.path.split(src)
            if with_root:
                target = os.path.join(dest, tail)
                self._make_dir(sftp, target)
            else:
                target = dest
            for dirpath, dirnames, filenames in os.walk(src, followlinks=follow):
                prefix = dirpath.split(src)[-1]
                if os.path.isabs(prefix):
                    prefix = prefix[1:]
                for dn in dirnames:
                    newdir = os.path.join(target, prefix, dn)
                    self._make_dir(sftp, newdir)
                for fn in filenames:
                    rp = os.path.join(target, prefix, fn)
                    lp = os.path.join(dirpath, fn)
                    if mode is None:
                        fstat = os.stat(lp)
                        fmode = fstat.st_mode
                    else:
                        fmode = mode
                    self._put_file(task, sftp, rp, abs_local_file=lp, mode=fmode, owner=owner, group=group)
                    
            # now pass over the local dirs again in order to set all directory modes on the remote
            for dirpath, _, _ in os.walk(src, followlinks=follow, topdown=False):
                prefix = dirpath.split(src)[-1]
                if os.path.isabs(prefix):
                    prefix = prefix[1:]
                self._set_dir_perms(sftp, os.path.join(target, prefix),
                                    dirpath, mode=directory_mode, owner=owner, group=group)
            if with_root:
                self._set_dir_perms(sftp, target, src, mode=directory_mode, owner=owner, group=group)
            success = True
            ecode = 0
                
        result = _Result(success, ecode, "", "")
        return result
    
    
@capture_mapping(_paramiko_domain, ProcessCopyFileTask)
class ProcessCopyFileProcessor(CopyFileProcessor):
    @narrate(lambda s, t: "...which required getting the remaining arguments for "
                          "process copy file processing task {}".format(t.name))
    def _make_args(self, task):
        args = super(ProcessCopyFileProcessor, self)._make_args(task)
        if args["content"] is not None:
            cv = _ComputableValue(args["content"])
            expanded_content = cv.expand(task.get_task_role(),
                                         raise_on_unexpanded=True)
            args["content"] = expanded_content
        return args

    @narrate(lambda s, t, sftp, rp, **kw: "...which starts putting the processed file from "
                                          "task {} to {}".format(t.name, rp))
    def _put_file(self, task, sftp, rem_path, abs_local_file=None, content=None, mode=None,
                  owner=None, group=None):
        if content is not None:
            super(ProcessCopyFileProcessor, self)._put_file(task, sftp, rem_path,
                                                            abs_local_file=abs_local_file,
                                                            content=content, mode=mode,
                                                            owner=owner, group=group)
        else:
            # we have a file to copy
            fstat = os.stat(abs_local_file)
            if mode is None:
                mode = fstat.st_mode
            tf = tempfile.TemporaryFile()
            for l in open(abs_local_file, "rb"):
                cv = _ComputableValue(l.decode() if hasattr(l, "decode") else l)
                output = cv.expand(task.get_task_role(), raise_on_unexpanded=True)
                tf.write(output.encode() if hasattr(output, "encode") else output)
            tf.seek(0)
            super(ProcessCopyFileProcessor, self)._put_file(task, sftp, rem_path,
                                                            abs_local_file=None,
                                                            content=None,
                                                            flo=tf, mode=mode,
                                                            owner=owner,
                                                            group=group)
        return True, ""
            
            
class ParamikoExecutionAgent(ExecutionAgent):
    def __init__(self, **kwargs):
        super(ParamikoExecutionAgent, self).__init__(**kwargs)
        self.connection_cache = {}
        self.in_process_locks = {}
        self.cache_lock = threading.RLock()

    def _logger_name(self):
        return "ea-PEA"

    @narrate(lambda s, h, u, **kw: "...leading to getting a Paramiko connection to {}".format(h))
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
        
        If none of priv_key, priv_key_file, or password are supplied, a private key
        must exist for this host in the user's known_hosts file.
        
        @return: A connected Paramiko SSHClient instance.
        @raise ExecutionException: Raised for incorrect arguments (missing credentials) or
            various inabilities to connect to the specified host as the provided user.
        """
        conn = None

        self.logger.debug("Entering get_connection")

        try:
            conn = SSHClient()
            if platform.system().lower() == "windows":
                devnull = "NUL"
            else:
                devnull = "/dev/null"
            conn.load_system_host_keys(devnull)
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
        self.logger.debug("Exiting get connection")
        return conn

        # @FIXME While Paramiko can handle more than one channel on a client, a bug
        # in the underlying open ssh implementation (need reference) makes this unreliable
        # so the following is commented out until that is corrected
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

    @narrate(lambda s, h, u, c, **kw: "...which then allowed the connection to {} to be returned".format(h))
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
        # @FIXME once Paramiko can properly handle more than one
        # channel on a client then we can use the code below
        self.logger.debug("Entering return_connection")
        assert isinstance(conn, SSHClient)
        conn.close()
        self.logger.debug("Exiting return_connection")
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

    @narrate(lambda s, t, p, a, kw: "...starting the performance of {} task {} "
                                    "with args {} and kwargs {}".format(t.__class__.__name__, t.name,
                                                                        str(a), str(kw)))
    def _perform_with_args(self, task, processor, args, kwargs):
        return processor.process_task(self, *args, **kwargs)


class ParamikoServiceExecutionAgent(object):
    def __init__(self, service, num_threads=5, do_log=False, no_delay=False, log_level=LOG_INFO):
        if service is None or not isinstance(service, ServiceModel):
            raise ExecutionException("'service' must be an instance of some kind of ServiceModel")
        self.service = service
        self.num_threads = num_threads
        self.do_log = do_log
        self.no_delay = no_delay
        self.log_level = log_level
        self.ptes = {}
        self.results = {}

    def _process_config_model(self, pea):
        try:
            pea.perform_config()
            self.results[pea] = None
        except ExecutionException as e:
            self.results[pea] = e

    def perform_config(self):
        services = self.service.all_services()
        num_threads = int(self.num_threads / len(services)) + 1
        exec_threads = []
        for service in services:
            self.ptes[service] = ParamikoExecutionAgent(config_model_instance=service.config.value(),
                                                        namespace_model_instance=service.namespace.value(),
                                                        infra_model_instance=service.infra.value(),
                                                        num_threads=num_threads,
                                                        do_log=self.do_log,
                                                        no_delay=self.no_delay,
                                                        log_level=self.log_level
                                                        )
            t = threading.Thread(target=self._process_config_model,
                                 args=(self.ptes[service],),
                                 name=service.name)
            exec_threads.append(t)
            t.start()

        for t in exec_threads:
            t.join()

    def get_aborted_tasks(self):
        for pea, exc in self.results.items():
            if exc is None:
                continue
            for t, et, ev, tb, story in pea.get_aborted_tasks():
                yield t, et, ev, tb, story
