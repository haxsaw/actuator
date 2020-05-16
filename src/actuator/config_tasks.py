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

import time
from errator import narrate
from actuator.config import ConfigTask, ConfigException
from actuator.exec_agents.core import ExecutionException


class PingTask(ConfigTask):
    """
    Checks to see if a remote machine is alive by ssh'ing into it. No other action is taken.
    """
    pass


class ScriptTask(ConfigTask):
    """
    Transfers a script *as is* to the remote host and executes it. The script
    is run in a shell environment. This task will process Var replacement 
    patterns out of the arguments, but does not touch the contents of the 
    script.
    """
    def __init__(self, name, free_form, creates=None, removes=None, proc_ns=False, **kwargs):
        """
        :param name: logical name for the task
        :param free_form: A string with the path to the locally available
            script followed by optional arguments to the script. This may
            contain Var replacement patterns that will be processed through
            the Vars for the task_role.

        :Keyword args:
            *  **creates** String; the name of a file on the remote system that
               the script will create. If already present, the script will not
               be run. If not supplied no test for a file to be created will be
               done.
            *  **removes** String; the name of a file on the remote system that
               the script will remove. If it isn't there, then the script will
               not be run. If not supplied then no removal test will be performed.
            *  **proc_ns** boolean; a flag to indicate if the script should be processed
               through the namespace prior to being copied to the remote system. This allows
               for scripts with Actuator Var replacement patterns to have those patterns
               replaced with the appropriate value in the final script that will be executed.
               The default is False, so no namespace processing is done.
            *  **kwargs** the other available keyword arguments for
               :py:class:`ConfigTask<actuator.config.ConfigTask>`
        """
        super(ScriptTask, self).__init__(name, **kwargs)
        self.free_form = None
        self._free_form = free_form
        self.creates = None
        self._creates = creates
        self.removes = None
        self._removes = removes
        self.proc_ns = None
        self._proc_ns = proc_ns

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        __doc__ = ConfigTask.get_init_args.__doc__
        args, kwargs = super(ScriptTask, self).get_init_args()
        args = args + (self._free_form,)
        kwargs["creates"] = self._creates
        kwargs["removes"] = self._removes
        kwargs["proc_ns"] = self._proc_ns
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(ScriptTask, self)._fix_arguments()
        self.free_form = self._get_arg_value(self._free_form)
        self.creates = self._get_arg_value(self._creates)
        self.removes = self._get_arg_value(self._removes)
        self.proc_ns = self._get_arg_value(self._proc_ns)
        

class CommandTask(ScriptTask):
    """
    Runs a command on the remote system. Nothing is transferred to the remote
    system; the command is expected to exist already.
    
    Arguments besides the name can contain Var replacement patterns; these
    will be processed through the task_role's view of its Vars in the
    namespace.
    
    If your command needs to use shell metacharacters, use :py:class:`ShellTask`
    instead.
    """
    def __init__(self, name, free_form, chdir=None, creates=None,
                 executable=None, removes=None, warn=None, **kwargs):
        """
        :param name: logical name for the task
        :param free_form: A string containing the remote command to run, along
            with any arguments the command needs

        :Keyword args:
            *  **chdir** Directory path to cd to before running the command.
            *  **executable** Full path to an alternative shell to run the
               in
            *  **warn** whether or not to warn about this specific command
            *  **creates** String; the name of a file on the remote system that
               the script will create. If already present, the script will not
               be run. If not supplied no test for a file to be created will be
               done.
            *  **removes** String; the name of a file on the remote system that
               the script will remove. If it isn't there, then the script will
               not be run. If not supplied then no removal test will be performed.
            *  **kwargs** the other available keyword arguments for
               :py:class:`ConfigTask<actuator.config.ConfigTask>`
        """

        super(CommandTask, self).__init__(name, free_form, creates=creates,
                                          removes=removes, **kwargs)
        self.chdir = None
        self._chdir = chdir
        self.executable = None
        self._executable = executable
        self.warn = None
        self._warn = warn

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        args, kwargs = super(CommandTask, self).get_init_args()
        kwargs["chdir"] = self._chdir
        kwargs["executable"] = self._executable
        kwargs["warn"] = self._warn
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(CommandTask, self)._fix_arguments()
        self.chdir = self._get_arg_value(self._chdir)
        self.executable = self._get_arg_value(self._executable)
        self.warn = self._get_arg_value(self._warn)


class ShellTask(CommandTask):
    """
    Almost the same as the :py:class:`CommandTask`, except that the task is run within
    a shell, and so shell meta-characters (redirection, etc) can be used.
    
    The arguments for ShellTask are the same as those for :py:class:`CommandTask`.
    """
    pass


class CopyFileTask(ConfigTask):
    """
    Copies a file from the local system to the remote system.
    
    The file is copied without impacting its contents. If you want to modify
    a file using Var replacement patterns and for the Vars in the task_role's
    namespace, use :py:class:`ProcessCopyFileTask` instead.
    
    Copy can work on a single file or a directory hierarchy of files.
    """
    def __init__(self, name, dest, backup=False, content=None,
                 directory_mode=None, follow=False, force=True, group=None,
                 mode=None, owner=None, selevel="s0", serole=None, setype=None,
                 seuser=None, src=None, validate=None,
                 **kwargs):
        """
        :param name: logical name for the task
        :param dest: The full path of where to copy the file. If src is a
            directory this must be a directory as well

        :Keyword args:
            *   **backup** boolean; if True, create a backup of any existing
                file with the same name
            *   **content** Content of the file to copy to the remote. If this is
                used instead of src, then dest must be the path to a file
            *   **directory_mode** If the copy is recursive, set the directories
                to this mode, but only if the directory doesn't already exist.
            *   **follow** boolean; flag to indicate that if there are filesystem
                links, they should be followed. Default no.
            *   **force** boolean; default is True. If True, replace the remote
                file if it already exists. If False, do not replace.
            *   **group** name of the group that should own the file/directory,
                as would be given to chown
            *   **mode** string mode that the file/directory should be. Symbolic
                modes are supported.
            *   **owner** name of the user who should own the file/directory,
                as will be supplied to chown
            *   **selevel** Default is 's0'. Level part of the SELinux file
                context. This is the MLS/MCS attribute, sometimes known as the
                range. _default feature works as for seuser.
            *   **serole** role part of SELinux file context, _default feature
                works as for seuser.
            *   **setype** type part of SELinux file context, _default feature
                works as for seuser.
            *   **seuser** user part of SELinux file context. Will default to
                system policy, if applicable. If set to _default, it will use the
                user portion of the policy if available
            *   **src** Local path to copy to the remote server; may be absolute
                or relative. If the path ends in a directory, the directory will
                be copied recursively. In this case, if the path ends in '/', only
                the directory content will be copied recursively. If there is no
                '/' on the end, then the directory and its contents are copied
                recursively.
            *   **validate** The validation command to run before copying into
                place. The path to the file to validate is passed in via '%s' which
                must be present as in the visudo example below (or, if in a Var,
                it can be represented with a replacement pattern). The command is
                passed securely so shell features like expansion and pipes won't
                work.
            *   **kwargs** the other available keyword arguments for
                :py:class:`ConfigTask`
        """
        super(CopyFileTask, self).__init__(name, **kwargs)
        if content is None and src is None:
            raise ConfigException("Either 'content' or 'src' must be provided")
        self.dest = None
        self._dest = dest
        self.backup = None
        self._backup = backup
        self.content = None
        self._content = content
        self.directory_mode = None
        self._directory_mode = directory_mode
        self.follow = None
        self._follow = follow
        self.force = None
        self._force = force
        self.group = None
        self._group = group
        self.mode = None
        self._mode = mode
        self.owner = None
        self._owner = owner
        self.selevel = None
        self._selevel = selevel
        self.serole = None
        self._serole = serole
        self.setype = None
        self._setype = setype
        self.seuser = None
        self._seuser = seuser
        self.src = None
        self._src = src
        self.validate = None
        self._validate = validate

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        args, kwargs = super(CopyFileTask, self).get_init_args()
        args = args + (self._dest,)
        kwargs["backup"] = self._backup
        kwargs["content"] = self._content
        kwargs["directory_mode"] = self._directory_mode
        kwargs["follow"] = self._follow
        kwargs["force"] = self._force
        kwargs["group"] = self._group
        kwargs["mode"] = self._mode
        kwargs["owner"] = self._owner
        kwargs["selevel"] = self._selevel
        kwargs["serole"] = self._serole
        kwargs["setype"] = self._setype
        kwargs["seuser"] = self._seuser
        kwargs["src"] = self._src
        kwargs["validate"] = self._validate
        return args, kwargs
    
    def _get_content(self):
        return self._content

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(CopyFileTask, self)._fix_arguments()
        self.dest = self._get_arg_value(self._dest)
        self.backup = self._get_arg_value(self._backup)
        self.backup = "yes" if self.backup else "no"
        self.content = self._get_content()
        self.directory_mode = self._get_arg_value(self._directory_mode)
        self.follow = self._get_arg_value(self._follow)
        self.follow = "yes" if self.follow else "no"
        self.force = self._get_arg_value(self._force)
        self.force = "yes" if self.force else "no"
        self.group = self._get_arg_value(self._group)
        self.mode = self._get_arg_value(self._mode)
        self.owner = self._get_arg_value(self._owner)
        self.selevel = self._get_arg_value(self._selevel)
        self.serole = self._get_arg_value(self._serole)
        self.setype = self._get_arg_value(self._setype)
        self.seuser = self._get_arg_value(self._seuser)
        self.src = self._get_arg_value(self._src)
        self.validate = self._get_arg_value(self._validate)
    
    
class ProcessCopyFileTask(CopyFileTask):
    """
    Like :py:class:`CopyFileTask`, except for two crucial differences:
    
      1. The file to be copied can contain Var replacement patterns that will
         be processed through the task_role's view of the namespace, replacing
         Var replacement patterns with their namespace value. The modified file
         is then copied to the remote. The local file remains unchanged.
      2. Given that the file is changed, recursive copies will not result in
         replacement patterns being processed. If you have a directory hierarchy
         to copy that contains some files to replace, the best approach is to
         use :py:class:`CopyFileTask` to copy the whole hierarchy, then use
         ProcessCopyFileTask to independently copy just the files that have to
         be processed through the namespace.
         
    The arguments are otherwise identical to :py:class:`CopyFileTask`.
    """
    def __init__(self, *args, **kwargs):
        if "src" not in kwargs and "content" not in kwargs:
            raise ExecutionException("ProcessCopyFileTask must be given either "
                                     "the 'src' or 'content' keyword arguments")
        super(ProcessCopyFileTask, self).__init__(*args, **kwargs)
        
    def _get_content(self):
        return self._get_arg_value(self._content)


class LocalCommandTask(ConfigTask):
    """
    Runs some command on the local host in a subprocess. A shell is not
    invoked so shell metachars are NOT expanded (use :py:class:`LocalShellCommandTask` if metachar
    support is required).

    Var replacement in the command is performed.
    """
    def __init__(self, name, command=None, **kwargs):
        """
        :param name: logical name for the task
        :param command: Command string to run. The string may have Var replacement expressions but must
            not contain any shell metacharacters.
        :param kwargs: the other available keyword arguments for
            :py:class:`ConfigTask`
        """
        super(LocalCommandTask, self).__init__(name, **kwargs)
        self._command = command
        self.command = None

    @narrate(lambda s: "...so we asked {} task {} for its init "
                       "args".format(s.__class__.__name__, s.name))
    def get_init_args(self):
        args, kwargs = super(LocalCommandTask, self).get_init_args()
        kwargs["command"] = self._command
        return args, kwargs

    @narrate(lambda s: "...so we asked {} task {} to fix "
                       "its arguments".format(s.__class__.__name__, s.name))
    def _fix_arguments(self):
        super(LocalCommandTask, self)._fix_arguments()
        self.command = self._get_arg_value(self._command)


class LocalShellCommandTask(LocalCommandTask):
    """
    Like :py:class:`LocalCommandTask` except that the command is run in a shell and hence
    shell metacharacters are allowed in the `command`. See :py:class:`LocalCommandTask` for
    details.
    """
    pass


class WaitForTaskTask(ConfigTask):
    """"""
    def __init__(self, name, awaited_task, **kwargs):
        """"""
        super(WaitForTaskTask, self).__init__(name, **kwargs)
        self._awaited_task = awaited_task
        self.awaited_task = None

    def _fix_arguments(self):
        super(WaitForTaskTask, self)._fix_arguments()
        self.awaited_task = self._get_arg_value(self._awaited_task)

    def get_init_args(self):
        args, kwargs = super(WaitForTaskTask, self).get_init_args()
        args += (self._awaited_task,)
        return args, kwargs

    def _perform(self, engine):
        while not engine.stop:
            if self.awaited_task.performance_status != self.UNSTARTED:
                time.sleep(0.2)
