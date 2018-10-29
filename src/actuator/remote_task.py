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

"""
This module contains the foundation for all Actuator models that involve the remote execution
of tasks; that is, running specific commands on remote hosts, as opposed to invoking some kind
of web service request for a particular service.
"""
import itertools
from collections import Iterable
from errator import narrate, narrate_cm
import six
import networkx as nx
from actuator.modeling import (AbstractModelReference, ModelComponent, ModelReference,
                               ModelBaseMeta, ModelBase, _Nexus, ModelInstanceReference)
from actuator.namespace import _ComputableValue, NamespaceModel
from actuator.task import (TaskException, Task, _Cloneable, GraphableModelMixin,
                           TaskEventHandler, _Unpackable, _Dependency)
from actuator.utils import (ClassModifier, process_modifiers, _Persistable, _find_class, IPAddressable)


class RemoteTaskException(TaskException):
    pass


_searchpath = "__searchpath__"


@ClassModifier
def with_searchpath(cls, *args, **_):
    """
    Currently unused
    """
    searchpath = cls.__dict__.get(_searchpath)
    if searchpath is None:
        searchpath = []
        setattr(cls, _searchpath, searchpath)
    searchpath.extend(list(args))


_dependencies = "__dependencies__"


@ClassModifier
def with_dependencies(cls, *args, **_):
    """
    Express dependencies between tasks to ensure their proper execution order

    This function takes dependency expressions involving tasks and captures
    them in the current model class. These dependencies are respected
    when it comes time to execute the tasks against a particular
    namespace model.

    The '|' operator defines a dependency where the task on the LHS must
    successfully complete before the task on the RHS starts.

    The '&' operator explicitly states two tasks that can be performed in
    parallel. Tasks that aren't subject to explicit '|' dependencies are
    implicitly treated as being able to be performed in parallel.

    For tasks t1, t2, t3, the following operators generate the following
    dependencies:

    t1 | t2  #perform t1 and then t2
    t1 | (t2 & t3)    #perform t1, then perform t2 and t3 in parallel
    t1 | t2, t1 | t3  #same as above
    t1 | t2, t2 | t3  #perform t1, then t2, then t3
    t1 | t2 | t3      #same as above
    (t1 & t2) | t3    #perform t1 and t2 in parallel, when both are done do t3

    So, for example, express the third dependency from the above list:

    with_dependencies(t1 | t2, t2 | t3)

    Similarly, the other expressions above can be directly used as arguments
    to the with_dependencies function.

    Expressions can be arbitrarily nested. Multiple calls to with_dependencies()
    are allowed; the dependencies are simply collected and interpreted as a whole.
    This allows complex expressions to be broken down into simpler ones.
    """
    deps = cls.__dict__.get(_dependencies)
    if deps is None:
        deps = []
        setattr(cls, _dependencies, deps)
    for arg in args:
        if not isinstance(arg, _Cloneable):
            raise RemoteTaskException("Argument %s is not a dependency" % str(arg))
    deps.extend(list(args))


_remote_task_options = "__remote_options__"
_default_task_role = "default_task_role"
_remote_user = "remote_user"
_private_key_file = "private_key_file"
_default_run_from = "default_run_from"
_legal_options = {_default_task_role, _remote_user, _private_key_file,
                  _default_run_from}


@ClassModifier
def with_remote_options(cls, *_, **kwargs):
    """
    Set up options to apply to the model as a whole

    Use this function to establish options on the overall operation of the
    model. Options are all keyword arguments with an appropriate
    value. Recognized keywords are:

    @keyword default_task_role: Reference to a Role. This can be either a
        model reference or an instance reference, but it must be a reference
        to a Role. This is the Role that will be used for tasks if no other
        explicit role has been identified, and there is no default_run_from
        Role for the model.
    @keyword remote_user: String. Provides a default user to utilize when
        running tasks. Used when no other user has been identified for the task.
        If no explicit user has been identified then the current user will
        be used for remote task execution.
    @keyword private_key_file: String. Path to the private part of an ssh
        keypair. This will be used with whatever user has been determined in
        effect for a particular task. If a task doesn't supply a specific
        private_key_file, then this will be the fallback one used.
    @keyword default_run_from: Reference to a Role. This value indicates where
        a task is to be executed from, regardless of the value of task_role.
        This allows tasks to be run with respect to a particular Role (task_role),
        but executed from a different Role's host. This allows tasks to run on
        a host but have access to another Role's Vars.
    """
    opts = cls.__dict__.get(_remote_task_options)
    if opts is None:
        opts = {}
        setattr(cls, _remote_task_options, opts)
    for k, v in kwargs.items():
        if k not in _legal_options:
            raise RemoteTaskException("Unrecognized option: {}".format(k))
        opts[k] = v


_node_dict = "_node_dict"
#
# @FIXME at the moment, this capability doesn't make sense in the larger scheme of
# task models; this is because although you could theoretically add a bunch of
# tasks from some task library, you won't have access to the objects to enter
# them into dependency expressions in any easy way. Even if you added the expressions
# in the same library module and just added them with "with_dependencies", you
# would still have an awkward time knintting those in to the overall dependency
# structure of the model. So until that gets figured out this functionality
# is off. Besides, it isn't working properly anyway, as the base metaclass
# expects things to be dumped into the "__components" dict in the class,
# not '_node_dict'
#
# @ClassModifier
# def with_tasks(cls, *args, **kwargs):
#     task_nodes = cls.__dict__.get(_node_dict)
#     if task_nodes is None:
#         task_nodes = {}
#         setattr(cls, _node_dict, task_nodes)
#     task_nodes.update({v:k for k, v in kwargs.items()})


class RemoteTask(Task):
    """
    Base class for all tasks that represent running commands on a remote machine.

    This class establishes the base instantiation and operational protocol
    for all tasks.
    """

    def __init__(self, name, task_role=None, run_from=None,
                 remote_user=None, remote_pass=None, private_key_file=None,
                 repeat_til_success=True, repeat_count=1, repeat_interval=15,
                 delegate=None):
        """
        Initialize a new RemoteTask

        @param name: String. Logical name for the task.
        @keyword task_role: A reference to a Role in the namespace model. This
            can be a model reference, context expression, or callable that takes
            an L{actuator.modeling.CallContext} and returns a model instance
            reference. The role determines the view of the namespace that is to be
            used; the Vars visible from the perspective of this Role are what will
            govern the operation of the task. If no task_role has been identified,
            one may still be assigned due to the actions of the task container
            classes (such as MultiTask). If a task_role can't be determined, then
            the model's default_task_role is used. If that can't be determined
            then an exception is raised.

            In the absence of a run_from Role, the task_role also determines where
            the task is to run (it is run on the host associated with the Role).
        @keyword run_from: A reference to a Role in the namespace model. This can
            a model reference, context expression, or a callable that takes an
            L{actuator.modeling.CallContext} and returns model instance reference
            to a Role. The host associated with this role is where the task will
            be run, however the Vars used be those associated with the Role
            identified as the task_role.
        @keyword remote_user: String, defaults to None. Identifies the user name
            to use when logging into a remote machine to perform this task. If not
            specified, the current user's user name is used.
        @keyword remote_pass: String, defaults to None. Password to use for the
            remote user. NOTE: I have yet to see this work! Ansible gets a BROKEN
            PIPE error trying to use sshpass to send the password on to ssh. This
            may be an Ubuntu-related problem, but I haven't figured out how to
            make it work.
        @keyword private_key_file: String, default None. Path to private key file
            for the remote user, as generated by ssh-keygen. This is the key file
            that will be used for whatever remote user has been determined.
        @keyword delegate: internal use

        See L{actuator.task.Task.__init__} for info on the remaining arguments
        """
        super(RemoteTask, self).__init__(name, repeat_til_success=repeat_til_success,
                                         repeat_count=repeat_count,
                                         repeat_interval=repeat_interval)
        self.task_role = None
        self._task_role = task_role
        self.run_from = None
        self._run_from = run_from
        self.remote_user = None
        self._remote_user = remote_user
        self.remote_pass = None
        self._remote_pass = remote_pass
        self.private_key_file = None
        self._private_key_file = private_key_file
        self.delegate = delegate

    def info(self):
        try:
            task_role = self.get_task_role()
            if task_role is not None:
                if isinstance(task_role.name, AbstractModelReference):
                    role = task_role.name.value()
                else:
                    role = str(task_role.name)
            else:
                role = "sysrole"
        except RemoteTaskException as _:
            role = "sysrole"
        try:
            task_host = self.get_task_host()
            if task_host:
                if isinstance(task_host, AbstractModelReference):
                    host = task_host.value()
                else:
                    host = str(task_host)
            else:
                host = "N/A"
        except (RemoteTaskException, AttributeError) as _:
            host = "N/A"

        return "(r:%s,h:%s)" % (role, host)

    def _get_attrs_dict(self):
        d = super(RemoteTask, self)._get_attrs_dict()
        d.update({"task_role": self.task_role,
                  "run_from": self.run_from,
                  "remote_user": self.remote_user,
                  "remote_pass": self.remote_pass,
                  "private_key_file": self.private_key_file,
                  "delegate": self.delegate})
        return d

    def _find_persistables(self):
        for p in super(RemoteTask, self)._find_persistables():
            yield p
        if self.task_role and isinstance(self.task_role, _Persistable):
            for p in self.task_role.find_persistables():
                yield p
        if self.run_from and isinstance(self.run_from, _Persistable):
            for p in self.run_from.find_persistables():
                yield p
        if self.delegate and isinstance(self.delegate, _Persistable):
            for p in self.delegate.find_persistables():
                yield p

    @narrate(lambda s, for_env=False: "...which requires getting all the Vars that apply to task {} for "
                                      "a specific host".format(s.name))
    def task_variables(self, for_env=False):
        """
        Return a dict with all the Vars that apply to this task according to
        the task_role for the task.

        This method returns a dict of Vars that represent the view of the Var
        space from the perspective of the task's Role (task_role). This will
        be the Vars expanded from the perspective of that role.

        @keyword for_env: boolean, default False. Governs if the full set of
            Vars are returned from the method. The default, False, means that
            the intention is to not use the Vars as part of environment for
            a task, and so sensitive Vars can be returned (those for which
            in_env was False). If for_env is True, then the method won't
            include Vars for which in_env is False.
        """
        the_vars = {}
        task_role = self.get_task_role()
        if task_role is not None:
            with narrate_cm(lambda tr: "-and that role being '{}'".format(tr.name), task_role):
                the_vars = {k: v.get_value(task_role)
                            for k, v in task_role.get_visible_vars().items()
                            if not for_env or (for_env and v.in_env)}
        return the_vars

    def set_task_role(self, task_role):
        """
        Used internally; sets the Role to use as the task_role for the task.
        """
        self._task_role = task_role

    def set_run_from(self, run_from):
        """
        Used internally; sets the Role to use as the run_from Role for the task.
        """
        self._run_from = run_from

    def _set_delegate(self, delegate):
        # internal
        self.delegate = delegate

    @narrate(lambda s, _=None: "...which requires task %s (%s) to determine what remote user name to use" %
                               (s.name, s.__class__.__name__))
    def get_remote_user(self, for_task=None):
        """
        Return the effective remote user to use for this task.
        """
        remote_user = (self.remote_user
                       if self.remote_user is not None
                       else (self.delegate.get_remote_user(self if for_task is None else for_task)
                             if self.delegate is not None
                             else None))
        return remote_user

    @narrate(lambda s, _=None: "...which requires task %s (%s) to determine what password to use" %
                               (s.name, s.__class__.__name__))
    def get_remote_pass(self, for_task=None):
        """
        Return the effective remote password to use for this user.
        """
        remote_pass = (self.remote_pass
                       if self.remote_pass is not None
                       else (self.delegate.get_remote_pass(self if for_task is None else for_task)
                             if self.delegate is not None
                             else None))
        return remote_pass

    @narrate(lambda s, _=None: "...which requires task %s (%s) to determine what private key file to use" %
                               (s.name, s.__class__.__name__))
    def get_private_key_file(self, for_task=None):
        """
        Return the effective private key file to use for this task.
        """
        private_key_file = (self.private_key_file
                            if self.private_key_file is not None
                            else (self.delegate.get_private_key_file(self if for_task is None else for_task)
                                  if self.delegate is not None
                                  else None))
        return private_key_file

    @narrate(lambda s: "...which requires task %s (%s) to determine what host to run on" %
                       (s.name, s.__class__.__name__))
    def get_task_host(self):
        """
        Return the host associated with the task_role for this task.
        """
        host = self.get_raw_task_host()
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host

    def get_raw_task_host(self):
        comp = self.get_task_role()
        host = (comp.host_ref
                if isinstance(comp.host_ref, six.string_types)
                else comp.host_ref.value())
        return host

    @narrate(lambda s: "...which requires task %s (%s) to determine what role the task is associated with" %
                       (s.name, s.__class__.__name__))
    def get_task_role(self):
        """
        Return the Role associated with this task.
        """
        self.fix_arguments()
        if self.task_role is not None:
            comp = self.task_role
        else:
            mi = self.get_model_instance()
            if mi is not None:
                # fetch the default task role for the entire model
                # this can raise an exception if there isn't a
                # default task role defined for the model
                comp = mi.get_task_role()
            else:
                raise RemoteTaskException("Can't find a task role for task {}".format(self.name))
        return comp

    @narrate(lambda s: "...which requires task %s (%s) to determine what role's perspective "
                       "the task should be run from" % (s.name, s.__class__.__name__))
    def get_run_from(self):
        """
        Return the Role associated with the run_from Role for this task
        """
        self.fix_arguments()
        if self.run_from is not None:
            comp = self.run_from
        else:
            mi = self.get_model_instance()
            comp = mi.get_run_from() if mi is not None else None
        return comp

    @narrate(lambda s: "...which required determining where {} task {} "
                       "should run from".format(s.__class__.__name__, s.name))
    def raw_run_task_where(self):
        # NOTE about task_role and run_from:
        # the task role provides the focal point for tasks to be performed
        # in a system, but it is NOT necessarily the place where the task
        # runs. by default the task_role identifies where to run the task,
        # but the task supports an optional arg, run_from, that determines
        # where to actually execute the task. In this latter case, the
        # task_role anchors the task to a role in the namespace, hence
        # defining where to get its Var values, but looks elsewhere for
        # a place to run the task. Any Vars attached to the run_from role
        # aren't used.
        run_role = self.get_run_from()
        if run_role is not None:
            run_role.fix_arguments()
            run_host = self.get_raw_run_host()
        else:
            try:
                run_role = self.get_task_role()
            except RemoteTaskException as _:
                run_role = None
            if run_role is not None:
                run_role.fix_arguments()
                run_host = self.get_raw_task_host()
                if hasattr(run_host, "fix_arguments"):
                    run_host.fix_arguments()
            else:
                run_host = None
        return run_host

    def run_task_where(self):
        run_host = self.raw_run_task_where()

        if isinstance(run_host, IPAddressable):
            run_host.fix_arguments()
            run_host = run_host.get_ip()
        return run_host

    @narrate(lambda s: "...which requires task %s (%s) to determine what host the task should be run from" %
                       (s.name, s.__class__.__name__))
    def get_run_host(self):
        """
        Return the host IP associated with the run_from Role for this task.
        """
        host = self.get_raw_run_host()
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host

    def get_raw_run_host(self):
        """
        This returns whatever kind of object is set up as the return of get_run_from(); this means that
        you might get just a string with an IP in it, or your might get an IPAddressable of some kind
        :return: string or IPAddressable
        """
        comp = self.get_run_from()
        host = None
        if comp is not None:
            host = (comp.host_ref
                    if isinstance(comp.host_ref, six.string_types)
                    else comp.host_ref.value())
        return host

    def get_init_args(self):
        __doc__ = ModelComponent.__doc__  # @ReservedAssignment
        args, kwargs = super(RemoteTask, self).get_init_args()
        kwargs.update({"task_role": self._task_role,
                       "run_from": self._run_from,
                       "remote_user": self._remote_user,
                       "remote_pass": self._remote_pass,
                       "private_key_file": self._private_key_file
                       })
        return args, kwargs

    def _get_arg_value(self, arg):
        val = super(RemoteTask, self)._get_arg_value(arg)
        if isinstance(val, six.string_types):
            # check if we have a variable to resolve
            cv = _ComputableValue(val)
            try:
                var_context = self.get_task_role()
            except RemoteTaskException as _:
                mi = self.get_model_instance()
                if mi is None:
                    raise RemoteTaskException("Can't find a model to get a default var context")
                var_context = mi.namespace_model_instance
                if var_context is None:
                    raise RemoteTaskException("Can't find a namespace to use as a var context")
            val = cv.expand(var_context)
        elif isinstance(val, ModelReference):
            mi = self.get_model_instance()
            val = mi.get_namespace().get_inst_ref(val) if mi is not None else val
        return val

    def _fix_arguments(self):
        super(RemoteTask, self)._fix_arguments()
        self.task_role = self._get_arg_value(self._task_role)
        self.run_from = self._get_arg_value(self._run_from)
        self.remote_user = self._get_arg_value(self._remote_user)
        self.remote_pass = self._get_arg_value(self._remote_pass)
        self.private_key_file = self._get_arg_value(self._private_key_file)

    @narrate(lambda s, e: "...which leads to actually performing task %s" % s.name)
    def _perform(self, engine):
        """
        Perform the task. Must be overridden to actually work. Typically,
        tasks have helper objects that actually do the work; they don't do
        the work themselves.
        """
        raise TypeError("Derived class must implement")

    @narrate(lambda s, e: "...which leads to 'reversing' task %s" % s.name)
    def _reverse(self, engine):
        """
        Undo whatever was done during the perform() method.

        This allows the task author to provide a means to undo the work that
        was done during perform. This is so that when a system is being
        de-provisioned/decomissioned, any cleanup or wrap-up tasks can be
        performed before the system goes away. It also can provide the means to
        define tasks that only do work during wrap-up; by not defining any
        activity in perform, but defining work in wrap-up, a model can then
        contain nodes that only do meaningful work during the deco lifecycle
        phase of a system.

        Unlike perform(), the default implementation silently does nothing.
        """
        return


class StructuralTask(object):
    """
    Flag mixin class to indicate a task that that is only for structuring
    other tasks.
    """
    pass


class RendezvousTask(RemoteTask, StructuralTask):
    """
    Internally used task for some of the container tasks; allows a common
    exit point to be identified for all tasks in the container.
    """

    def _perform(self, engine):
        return


class RemoteTaskModelMeta(ModelBaseMeta):
    _allowed_task_class = RemoteTask

    def __new__(mcs, name, bases, attr_dict):
        attr_dict["_allowed_task_class"] = mcs._allowed_task_class
        all_tasks = {v: k for k, v in attr_dict.items() if isinstance(v, mcs._allowed_task_class)}
        attr_dict[_node_dict] = all_tasks
        if _remote_task_options not in attr_dict:
            attr_dict[_remote_task_options] = {}
        newbie = super(RemoteTaskModelMeta, mcs).__new__(mcs, name, bases, attr_dict)
        process_modifiers(newbie)
        for v, k in getattr(newbie, _node_dict).items():
            setattr(newbie, k, v)
        graph = nx.DiGraph()
        graph.add_nodes_from(newbie._node_dict.keys())
        if hasattr(newbie, _dependencies):
            deps = newbie.get_class_dependencies()
            graph.add_edges_from([d.edge() for d in deps])
            try:
                _ = list(nx.topological_sort(graph))
            except nx.NetworkXUnfeasible as _:
                raise RemoteTaskException("Task dependency graph contains a cycle")
        return newbie


class RemoteTaskModel(six.with_metaclass(RemoteTaskModelMeta, ModelBase, GraphableModelMixin)):
    """
    Base class for all remote task models.

    This class is used to define Actuator remote task models. Instances of the class
    will be married to a namespace such that the model can find the Roles
    associated with each task. Once an instance is made and associated with
    a namespace the tasks in the model can be performed.
    """
    ref_class = ModelInstanceReference
    _allowed_task_class = None

    def __init__(self, name, namespace_model_instance=None, nexus=None,
                 remote_user=None, remote_pass=None, private_key_file=None,
                 delegate=None, default_task_role=None, default_run_from=None,
                 event_handler=None, cloud_creds=None, **kwargs):
        """
        Create a new RemoteTaskModel instance.

        Create an instance of a remote task model. You may override this method as
        long as you call super().__init__() in your init and pass along all the
        keyword arguments that were passed into your derived class.

        @keyword namespace_model_instance: Default None, otherwise an instance
            of a class derived from L{NamespaceModel}. You don't need to pass
            the namespace to the model if you're using Actuator's
            orchestrator to drive the model; the orchestrator will take
            care of it for you. You normally never need to provide this argument.
        @keyword nexus: Internal
        @keyword remote_user: String; default is None. This value provides the
            default remote_user for tasks that don't otherwise have their own
            remote_user set. Task remote_users take precedence over this value,
            but this value has precedence over the value supplied in
            with_remote_options(). If the user can't be determined any other
            way, the current user name is used for remote access
        @keyword remote_pass: String; default is None. This arg provides the
            password to use with the remote user as determined by above.
            Task's remote_pass takes precedence over this value, but this value
            takes precedence over the remote_pass supplied in
            with_remote_options(). NOTE: this has yet to be observed to actually
            work; Ansible always reports a BROKEN PIPE when trying to use
            sshpass to make use of this argument. Use key pairs instead.
        @keyword private_key_file: String; path to the private part of an ssh
            keypair. The full path to the key file is needed.
        @keyword delegate: internal. Next object to check for a task_role or a
            run_from role.
        @keyword default_task_role: Default None. This identifies the Role to
            use for a task if the task doesn't specify a task_role of its own.
            The Role identifies the Vars and their values to use for the task,
            and if there is no 'run_from' role the host where the task is to run.
            This can be reference to a Role, a context expression for a Role,
            or a callable that takes a L{CallContext} argument and returns
            a reference to a Role. If a task_role can't be determined for a task
            an exception is raised at orchestration time.
        @keyword default_run_from: Default None. This identifies the Role to use
            for running a task; this is independent of the task_role. The
            task_role identifies the the set of Vars and their values from the
            namespace, and in the absence of a run_from Role, where to run the
            task as well. If a default_run_from is supplied, then the task will
            be run from that named Role's host, but with the Vars for the
            task_role. This can be a reference to a Role, a context expression,
            or a callable that takes a L{CallContext} and returns a reference
            to a Role.
        @keyword event_handler: if supplied, a derived class of task.TaskEventHandler
        @keyword cloud_creds: dict, default None. If supplied, this is a dict of cloud
            credentials. The keys are names of clouds such as were supplied to the
            'cloud' argument on InfraModel resources. The value is a nested dict
            whose keys are the previously described credentials arguments (remote_user,
            remote_pass, private_key_file) for that specific cloud. Keys may be missing
            in the inner dict and they will be treated as if they were missing from the
            call to the model class. If a needed key is missing for a cloud, then
            the corresponding keyword argument is checked for the model instance.
            For example, if the 'remote_user' key is missing for the 'citycloud' cloud
            entry, then the remote_user keyword arg is checked. If that is empty, then
            delegates are checked as appropriate. If there is no cloud associated with
            the task's resource, then only the keyword args for the model are checked.

        """
        if event_handler and not isinstance(event_handler, TaskEventHandler):
            raise RemoteTaskException("event_handler is not a kind of TaskEventHandler")
        super(RemoteTaskModel, self).__init__(name, nexus=nexus, **kwargs)
        self.event_handler = event_handler
        self.namespace_model_instance = namespace_model_instance
        self.remote_user = remote_user
        self.remote_pass = remote_pass
        self.private_key_file = private_key_file
        self.default_task_role = default_task_role
        self.default_run_from = default_run_from
        self.delegate = delegate
        self.cloud_creds = cloud_creds if cloud_creds is not None else {}
        clone_dict = {}
        # NOTE! _node_dict is an inverted dictionary (the string keys are
        # stored as values; it is added in the metaclass
        for v, k in self._node_dict.items():
            if not isinstance(v, self._allowed_task_class):
                raise RemoteTaskException("'%s' is not a task" % k)
            clone = v.clone()
            clone._set_delegate(self)
            clone._set_model_instance(self)
            clone_dict[v] = clone
            for etan in v._embedded_exittask_attrnames():
                clone_dict[getattr(v, etan)] = getattr(clone, etan)
            setattr(self, k, clone)
            _ = getattr(self, k)  # this primes the reference machinery
        self.dependencies = [d.clone(clone_dict)
                             for d in self.get_class_dependencies()]
        # default option values
        opts = object.__getattribute__(self, _remote_task_options)
        for k, v in opts.items():
            if k == _default_task_role and self.default_task_role is None:
                self.default_task_role = v
            elif k == _remote_user and self.remote_user is None:
                self.remote_user = v
            elif k == _private_key_file and self.private_key_file is None:
                self.private_key_file = v
            elif k == _default_run_from and self.default_run_from is None:
                self.default_run_from = v

    def set_cloud_creds(self, cloud_creds):
        self.cloud_creds = cloud_creds

    def get_event_handler(self):
        return self.event_handler

    def set_event_handler(self, handler):
        self.event_handler = handler

    def _get_attrs_dict(self):
        d = super(RemoteTaskModel, self)._get_attrs_dict()
        d.update(namespace_model_instance=self.namespace_model_instance,
                 remote_user=self.remote_user,
                 remote_pass=self.remote_pass,
                 private_key_file=self.private_key_file,
                 default_task_role=self.default_task_role,
                 default_run_from=self.default_run_from,
                 delegate=self.delegate,
                 dependencies=self.dependencies,
                 event_handler=None,
                 cloud_creds=None)  # persisting cloud_creds could be a security leak, so leave them behind
        d.update({k: v for k, v in self._comp_source().items()})
        return d

    def _find_persistables(self):
        for p in super(RemoteTaskModel, self)._find_persistables():
            yield p
        for o in itertools.chain(self.dependencies,
                                 [self.namespace_model_instance,
                                  self.default_run_from,
                                  self.default_task_role,
                                  self.delegate],
                                 self._comp_source().values()):
            if isinstance(o, _Persistable):
                for p in o.find_persistables():
                    yield p

    def _set_delegate(self, delegate):
        self.delegate = delegate

    def _comp_source(self):
        # remember, self._node_dict is an inverted dict
        d = {}
        for k in self._node_dict.values():
            v = getattr(self, k)
            if isinstance(v, AbstractModelReference):
                v = v.value()
            d[k] = v
        return d

    def set_task_role(self, task_role):
        """
        Internal; sets the default_task_role for the model. Users generally
        don't need to use this method.
        """
        if not isinstance(task_role, AbstractModelReference):
            task_role = AbstractModelReference.find_ref_for_obj(task_role)
            if not isinstance(task_role, AbstractModelReference):
                raise RemoteTaskException("A default task role was supplied that isn't some kind of "
                                          "model reference, and no reference can be found: %s" % str(task_role))
        self.default_task_role = task_role

    @narrate(lambda s, with_fix=False: "...and that led to asking the model %s for the "
                                       "task graph" % s.__class__.__name__)
    def get_graph(self, with_fix=False):
        """
        Returns a NetworkX DiGraph object consisting of the tasks that are
        in the model.

        The graph returned is a clean instance of the graph that governs the
        operation of the model under the orchestrator. That means it
        has none of the additional information added by the orchestration
        system, such as what nodes have been performed or not. This method simply
        provides a means to acquire the graph for visualization or other
        information purposes.

        @keyword with_fix: boolean; default False. Indicates whether or not
            the nodes in the graph should have fix_arguments called on them
            prior to asking for their dependencies.
        """
        nodes = self.get_tasks()
        if with_fix:
            for n in nodes:
                n.fix_arguments()
        deps, _ = self.get_dependencies()
        graph = nx.DiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from([d.edge() for d in deps])
        return graph

    @narrate(lambda s, _=None: "...which requires the remote task model %s to acquire the default remote "
                               "user for a task" % s.__class__.__name__)
    def get_remote_user(self, for_task=None):
        """
        Compute the remote user to use for a task.

        This returns the remote_user specified on this object, or returns
        the remote_user from the delegate if there is no remote_user and there
        is a delegate. If a remote_user can't be determined, the current user
        is used for the remote user.
        """
        if for_task is None:
            return self._base_remote_user_lookup(for_task)

        host_ref = for_task.raw_run_task_where()
        if host_ref is None or isinstance(host_ref, six.string_types):
            return self._base_remote_user_lookup(for_task)

        cloud = host_ref.cloud
        if cloud is None:
            return self._base_remote_user_lookup(for_task)

        creds = self.cloud_creds.get(cloud)
        if creds is None:
            # we can't tell here if they forgot the credentials for the cloud or just put them in the
            # model level. We'll look to the model for the remote_user and go with that.
            remote_user = self._base_remote_user_lookup(for_task)
        else:
            remote_user = creds.get("remote_user")
            if remote_user is None:
                remote_user = self._base_remote_user_lookup(for_task)

        return remote_user

    def _base_remote_user_lookup(self, for_task):
        remote_user = (self.remote_user
                       if self.remote_user is not None
                       else (self.delegate.get_remote_user(for_task)
                             if self.delegate is not None
                             else None))
        return remote_user

    @narrate(lambda s, _=None: "...which requires the remote task model %s to acquire the remote user's default "
                               "password for a task" % s.__class__.__name__)
    def get_remote_pass(self, for_task=None):
        """
        Compute the remote_pass to use for the remote_user.

        Return the remote_pass on this object, or if there isn't one and there
        is a delegate, return the delegate's remote_user. NOTE: I have yet
        to see Ansible process this option properly even with sshpass installed;
        Ansible fails with a BROKEN PIPE error on the sshpass command. For the
        time being use the private_key_file option for login credentials instead.
        """
        if for_task is None:
            return self._base_remote_pass_lookup(for_task)

        host_ref = for_task.raw_run_task_where()
        if host_ref is None or isinstance(host_ref, six.string_types):
            return self._base_remote_pass_lookup(for_task)

        cloud = host_ref.cloud
        if cloud is None:
            return self._base_remote_pass_lookup(for_task)

        creds = self.cloud_creds.get(cloud)
        if creds is None:
            # we can't tell here if they forgot the credentials for the cloud or just put them in the
            # model level. We'll look to the model for the remote_user and go with that.
            remote_pass = self._base_remote_pass_lookup(for_task)
        else:
            remote_pass = creds.get("remote_pass")
            if remote_pass is None:
                remote_pass = self._base_remote_pass_lookup(for_task)

        return remote_pass

    def _base_remote_pass_lookup(self, for_task):
        remote_pass = (self.remote_pass
                       if self.remote_pass is not None
                       else (self.delegate.get_remote_pass(for_task)
                             if self.delegate is not None
                             else None))

        return remote_pass

    @narrate(lambda s, _=None: "...which requires the remote task model %s to acquire the name of "
                               "the default key file to use for a task" % s.__class__.__name__)
    def get_private_key_file(self, for_task=None):
        """
        Compute the private_key_file to use for the remote_user.

        Return the private_key_file on this object, or if there isn't one and
        there is a delegate, return the delegate's private_key_file.
        """
        if for_task is None:
            return self._base_private_key_file_lookup(for_task)

        host_ref = for_task.raw_run_task_where()
        if host_ref is None or isinstance(host_ref, six.string_types):
            return self._base_private_key_file_lookup(for_task)

        cloud = host_ref.cloud
        if cloud is None:
            return self._base_private_key_file_lookup(for_task)

        creds = self.cloud_creds.get(cloud)
        if creds is None:
            # we can't tell here if they forgot the credentials for the cloud or just put them in the
            # model level. We'll look to the model for the remote_user and go with that.
            private_key_file = self._base_private_key_file_lookup(for_task)
        else:
            private_key_file = creds.get("private_key_file")
            if private_key_file is None:
                private_key_file = self._base_private_key_file_lookup(for_task)

        return private_key_file

    def _base_private_key_file_lookup(self, for_task):
        private_key_file = (self.private_key_file
                            if self.private_key_file is not None
                            else (self.delegate.get_private_key_file(for_task)
                                  if self.delegate is not None
                                  else None))

        return private_key_file

    @narrate(lambda s: "...which results in asking the remote task model %s for the default host for the task" %
                       s.__class__.__name__)
    def get_task_host(self):
        """
        Compute the IP address of the host for the task.

        This method takes the value returned by L{get_task_role}. and returns
        a string that is the IP address for the value returned, if any. This
        does not take into account and run_from value.
        """
        comp = self.get_task_role()
        host = (comp.host_ref
                if isinstance(comp.host_ref, six.string_types)
                else comp.host_ref.value())
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host

    @narrate(lambda s: "...requiring remote task model %s to provide the default task role" % s.__class__.__name__)
    def get_task_role(self):
        """
        Compute the L{Role} to use for as the default task_role for this model.

        This method computes the task_role, either from this model or from
        the model's delegate, and returns the actual Role object to use.
        """
        if self.default_task_role is None and self.delegate is None:
            raise RemoteTaskException("No default task role defined on the remote task model")

        if self.namespace_model_instance is None:
            raise RemoteTaskException(
                "RemoteTaskModel instance can't get a default task role from a Namespace model reference without an "
                "instance of that model")

        comp_ref = self.namespace_model_instance.get_inst_ref(self.default_task_role)
        comp_ref.fix_arguments()
        return comp_ref.value()

    @narrate(lambda s: "...requiring the remote task model %s to provide the default run from role for a task" %
                       s.__class__.__name__)
    def get_run_from(self):
        """
        Compute the L{Role} to use as the default run_from Role for this model.

        This method computes the run_from Role to use for any tasks that don't
        have their own. If it can't determine a run_from and it has a delegate,
        it returns the delegates notion of the run_from Role. This returns an
        actual Role object, not a reference.
        """
        comp = None
        if self.default_run_from is not None:
            if self.namespace_model_instance is None:
                raise RemoteTaskException("RemoteTaskModel can't get a namespace instance to acquire the default "
                                          "run_from")
            comp_ref = self.namespace_model_instance.get_inst_ref(self.default_run_from)
            comp_ref.fix_arguments()
            comp = comp_ref.value()
        return comp

    @narrate(lambda s: "...resulting in the remote task model %s providing the default run host for a task" %
                       s.__class__.__name__)
    def get_run_host(self):
        """
        Return the host IP associated with the run_from Role for this task.
        """
        host = self.get_raw_run_host()
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host

    # def get_run_host(self):
    #     """
    #     Compute the IP address of the host where the task is to run from.
    #
    #     This method computes the IP address of the IP address of the host for
    #     the Role returned by L{get_run_from}, if there is one. If none, it
    #     returns None.
    #     """
    #     comp = self.get_run_from()
    #     host = (comp.host_ref
    #             if isinstance(comp.host_ref, six.string_types)
    #             else comp.host_ref.value())
    #     if isinstance(host, IPAddressable):
    #         host.fix_arguments()
    #         host = host.get_ip()
    #     return host

    def get_raw_run_host(self):
        """
        This returns whatever kind of object is set up as the return of get_run_from(); this means that
        you might get just a string with an IP in it, or your might get an IPAddressable of some kind
        :return: string or IPAddressable
        """
        comp = self.get_run_from()
        host = None
        if comp is not None:
            host = (comp.host_ref
                    if isinstance(comp.host_ref, six.string_types)
                    else comp.host_ref.value())
        return host

    def set_namespace(self, namespace):
        """
        Internal; sets the namespace to use for this remote task model so the
        model can determine what tasks to run where.

        @param namespace: An instance of a L{NamespaceModel} subclass.
        """
        if not isinstance(namespace, NamespaceModel):
            raise RemoteTaskException("given an object that is not "
                                      "a kind of NamespaceModel: %s" % str(namespace))
        self.namespace_model_instance = namespace
        self.namespace_model_instance.nexus.merge_from(self.nexus)
        self.nexus = self.namespace_model_instance.nexus

    def get_namespace(self):
        """
        Returns the namespace model instance for this remote task model.
        """
        if not self.namespace_model_instance:
            self.namespace_model_instance = self.nexus.find_instance(NamespaceModel)
        return self.namespace_model_instance

    @narrate(lambda s: "...and this required the remote task model %s to compute its task dependencies" %
                       s.__class__.__name__)
    def get_dependencies(self):
        """
        Returns a list of _Dependency objects that captures all the task
        dependency pairs in the remote task model.
        """
        inst_nodes = [getattr(self, name).value() for name in self._node_dict.values()]
        return list(set(itertools.chain(list(itertools.chain(*[n.unpack()
                                                               for n in inst_nodes
                                                               if isinstance(n, _Unpackable)])),
                                        *[d.unpack() for d in self.dependencies]))), {}

    @classmethod
    def get_class_dependencies(cls):
        """
        This method returns a list of _Dependency objects as defined on the
        remote task model object, *not* an instance of the remote task model. This means
        that there may be few dependencies than in an instance as there won't
        be a namespace yet to influence the number of tasks to perform.
        """
        if hasattr(cls, _dependencies):
            deps = list(itertools.chain(*[d.unpack() for d in getattr(cls, _dependencies)]))
        else:
            deps = []
        return deps

    @narrate(lambda s: "...which required getting the remote tasks from the %s model" %
                       s.__class__.__name__)
    def get_tasks(self):
        """
        Returns a list of the L{RemoteTask} objects in the model.
        """
        return [getattr(self, k).value() for k in self._node_dict.values()]


class RemoteTaskClass(RemoteTask, _Unpackable, StructuralTask, GraphableModelMixin):
    """
    This class wraps up a RemoteTaskModel and makes the entire model appear as
    a single task. This allows the construction of "models of models". The
    canonical use case is when your system has a number of Role on which a
    number of Tasks much all be performed with specific dependencies.
    RemoteTaskClass allows you to create a model of these tasks for a single
    host, and then allows you to reuse that model, either in multiple contexts
    or as a common library of tasks to be performed on multiple Roles.
    """
    _sep = "+=+=+=+"

    def __init__(self, name, rtask_class, init_args=None, **kwargs):
        """
        Create a new RemoteTaskClass that wraps another remote task model

        @param name: String; logical name for the task
        @param rtask_class: A RemoteTaskModel derived model class. NOTE: this is not an
            instance of a model class, but the model class itself. This wrapper
            will take care of making an instance when one is needed.
        @keyword init_args: Iterable. The positional arguments to pass to the
            model class when an instance is to be made.
        @keyword **kwargs: See L{RemoteTask} for the remaining keyword arguments
            available to tasks. These will be available to the instance of the
            wrapped remote task model as this wrapper serves as the model's delegate.
        """
        if not issubclass(rtask_class, RemoteTaskModel):
            raise RemoteTaskException("The rtask_class parameter isn't a subclass of RemoteTaskModel")
        super(RemoteTaskClass, self).__init__(name, **kwargs)
        self.rtask_class = rtask_class
        self.init_args = None
        self._init_args = init_args if init_args else ()
        self.instance = None
        self.dependencies = []
        self.rendezvous = RendezvousTask("{}-rendezvous".format(name))
        self.graph = None

    @narrate(lambda s: "...so we started to gather the base attrs for "
                       "{} task {}".format(s.__class__.__name__, s.name))
    def _get_attrs_dict(self):
        d = super(RemoteTaskClass, self)._get_attrs_dict()
        d.update(rtask_class="%s%s%s" % (self.rtask_class.__name__, self._sep,
                                         self.rtask_class.__module__),
                 init_args=self.init_args,
                 instance=self.instance,
                 dependencies=self.dependencies,
                 rendezvous=self.rendezvous.name,
                 graph=None)
        return d

    @narrate(lambda s: "...which led to finding all persistables contained in "
                       "{} task {}".format(s.__class__.__name__, s.name))
    def _find_persistables(self):
        for p in super(RemoteTaskClass, self)._find_persistables():
            yield p
        if self.init_args:
            for a in self.init_args:
                if isinstance(a, _Persistable):
                    for p in a.find_persistables():
                        yield p
        if self.instance:
            for p in self.instance.find_persistables():
                yield p
        for d in self.dependencies:
            for p in d.find_persistables():
                yield p

    @narrate(lambda s: "...and then we set out to finish reanimating "
                       "{} task {}".format(s.__class__.__name__, s.name))
    def finalize_reanimate(self):
        super(RemoteTaskClass, self).finalize_reanimate()
        self.rendezvous = RendezvousTask(self.rendezvous)
        klassname, modname = self.rtask_class.split(self._sep)
        self.rtask_class = _find_class(modname, klassname)

    @narrate(lambda s, **kw: "...requiring the task graph for remote task class {}".format(s.name))
    def get_graph(self, with_fix=False):
        """
        Return a new instance of the NetworkX DiGraph that represents the
        tasks and dependencies for the wrapped model.

        @keyword with_fix: boolean, default False. Indicates whether or not to
            invoke fix_arguments() on the nodes before constructing the graph.
        """
        if with_fix:
            if self.graph:
                graph = self.graph
            elif self.instance is not None:
                graph = self.graph = self.instance.get_graph(with_fix=with_fix)
            else:
                init_args = self._get_arg_value(self._init_args)
                if not init_args:
                    init_args = ()
                model = self.get_model_instance()
                instance = self.rtask_class(*init_args, delegate=model)
                instance._set_delegate(self)
                graph = instance.get_graph()
        else:
            graph = self.instance.get_graph()
        return graph

    def _set_model_instance(self, mi):
        # internal
        super(RemoteTaskClass, self)._set_model_instance(mi)
        self.rendezvous._set_model_instance(mi)

    def _perform(self, engine):
        """
        Null perform method for the wrapper itself.
        """
        return

    def _or_result_class(self):
        # internal
        return _Dependency

    @narrate(lambda s: "...requiring {} task {} to provide its init args".format(s.__class__.__name__,
                                                                                 s.name))
    def get_init_args(self):
        __doc__ = RemoteTask.get_init_args.__doc__  # @ReservedAssignment
        args, kwargs = super(RemoteTaskClass, self).get_init_args()
        args = args + (self.rtask_class,)
        kwargs["init_args"] = self._init_args
        return args, kwargs

    @narrate(lambda s: "...leading to the remote task class {} to fix its arguments".format(s.name))
    def _fix_arguments(self):
        # internal
        super(RemoteTaskClass, self)._fix_arguments()
        self.init_args = self._get_arg_value(self._init_args)
        self.init_args = init_args = self.init_args if self.init_args else ()
        model = self.get_model_instance()
        self.instance = self.rtask_class(*init_args,
                                         namespace_model_instance=model.get_namespace(),
                                         nexus=model.nexus,
                                         delegate=model)
        self.instance.set_task_role(self.get_task_role())
        self.instance._set_delegate(self)
        graph = self.get_graph(with_fix=True)
        entry_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
        exit_nodes = [n for n in graph.nodes() if graph.out_degree(n) == 0]
        self.dependencies = list(itertools.chain(self.instance.get_dependencies()[0],
                                                 [_Dependency(self, c) for c in entry_nodes],
                                                 [_Dependency(c, self.rendezvous) for c in exit_nodes]))

    def exit_nodes(self):
        """
        Returns the list of nodes that have no successors in the wrapped class.

        This is always the internal rendezvous class,
        """
        return [self.rendezvous]

    def _embedded_exittask_attrnames(self):
        return ["rendezvous"]

    @narrate("...requiring the dependencies in the inner remote task model")
    def unpack(self):
        """
        Returns the list of _Dependencies for the nodes in the wrapped remote task
        model.
        """
        deps = list(self.dependencies)
        graph = self.get_graph(with_fix=True)
        deps.extend(itertools.chain(*[c.unpack() for c in graph.nodes()
                                      if isinstance(c, _Unpackable)]))
        return deps


class MultiTask(RemoteTask, _Unpackable, StructuralTask):
    """
    This class allows a template task to be run against a list of different
    Roles.

    This class takes a template task and a list of Roles, and creates an
    instance of the task for each Role in the list.

    The list can be an explicit list of Role references, a selection
    expression (that is, a NamespaceModel.q expression), or a callable that
    takes a single L{CallContext} argument and returns a list of references
    to Roles.
    """

    def __init__(self, name, template, task_role_list, **kwargs):
        """
        Creates a new MultiTask object.

        @param name: String; the logical name for the MultiTask
        @param template: Any kind of task object instance, including
            L{RemoteClassTask}, or even another MultiTask
        @param task_role_list: Must either be an explicit iterable of references
            to Roles, a callable that takes a L{CallContext} as an argument
            and returns an iterable of references to Roles, or a RefSelectBuilder
            expression (NamespaceModel.q expression) of the Roles to apply the
            task to
        @keyword **kwargs: keyword arguments as defined on L{RemoteTask}
        """
        super(MultiTask, self).__init__(name, **kwargs)
        self.template = None
        self._template = template
        self.task_role_list = None
        self._task_role_list = task_role_list
        self.dependencies = []
        self.instances = []
        self.rendezvous = RendezvousTask("{}-rendezvous".format(name))

    def __len__(self):
        return len(self.instances)

    @narrate(lambda s: "...and so the attrs dict for multitask {} was requested".format(s.name))
    def _get_attrs_dict(self):
        d = super(MultiTask, self)._get_attrs_dict()
        d.update(template=self.template,
                 task_role_list=list(self.task_role_list),
                 dependencies=self.dependencies,
                 instances=self.instances,
                 rendezvous=self.rendezvous.name)
        return d

    def _find_persistables(self):
        with narrate_cm(lambda s: "---so the persistables in multitask {} were "
                                  "yielded".format(s.name), self):
            for p in super(MultiTask, self)._find_persistables():
                yield p
            for p in self.template.find_persistables():
                yield p
            if self.task_role_list:
                for tr in self.task_role_list:
                    for p in tr.find_persistables():
                        yield p
            for d in self.dependencies:
                for p in d.find_persistables():
                    yield p
            for i in self.instances:
                for p in i.find_persistables():
                    yield p

    def finalize_reanimate(self):
        self.rendezvous = RendezvousTask(self.rendezvous)
        self.task_role_list = set(self.task_role_list)

    def _set_model_instance(self, mi):
        super(MultiTask, self)._set_model_instance(mi)
        self.rendezvous._set_model_instance(mi)

    def _perform(self, engine):
        """
        Empty perform method for the MultiTask itself.
        """
        return

    def _embedded_exittask_attrnames(self):
        return ["rendezvous"]

    def _or_result_class(self):
        return _Dependency

    @narrate(lambda s: "...so multitask {} was asked to return its init args".format(s.name))
    def get_init_args(self):
        __doc__ = RemoteTask.get_init_args.__doc__  # @ReservedAssignment
        args, kwargs = super(MultiTask, self).get_init_args()
        args = args + (self._template, self._task_role_list)
        return args, kwargs

    @narrate(lambda s: "...so multitask {} was asked to fix its args".format(s.name))
    def _fix_arguments(self):
        super(MultiTask, self)._fix_arguments()
        self.rendezvous.fix_arguments()
        self.template = self._get_arg_value(self._template)
        self.task_role_list = self._get_arg_value(self._task_role_list)
        comp_refs = []
        if isinstance(self.task_role_list, AbstractModelReference):
            try:
                keys = self.task_role_list.keys()
                comp_refs = [self.task_role_list[k] for k in keys]
            except TypeError as _:
                raise RemoteTaskException("The value for task_role_list provided to the MultiTask "
                                          "role named {} does not support 'keys()', "
                                          "and so can't be used to acquire a list of roles "
                                          "that the task should be run against".format(self.name))
        elif isinstance(self.task_role_list, Iterable):
            comp_refs = self.task_role_list
        for ref in comp_refs:
            clone = self.template.clone()
            clone._set_delegate(self)
            clone.name = "{}-{}".format(clone.name, ref.name.value())
            clone._task_role = ref
            clone._set_model_instance(self.get_model_instance())
            clone.fix_arguments()
            self.instances.append(clone)
        self.dependencies = list(itertools.chain([_Dependency(self, c)
                                                  for c in self.instances],
                                                 [_Dependency(xit, self.rendezvous)
                                                  for c in self.instances
                                                  for xit in c.exit_nodes()]))

    def exit_nodes(self):
        return [self.rendezvous]

    @narrate(lambda s: "...requiring unpacking the dependencies of the tasks in multitask {}".format(s.name))
    def unpack(self):
        """
        Unpacks the internal dependencies for the tasks that the MultiTask contains,
        returns a list of _Dependency objects.
        """
        deps = list(self.dependencies)
        deps.extend(itertools.chain(*[c.unpack() for c in self.instances if isinstance(c, _Unpackable)]))
        return deps


class NullTask(RemoteTask):
    """
    Non-functional task that's mostly good for testing
    """

    def __init__(self, name, path="", **kwargs):
        super(NullTask, self).__init__(name, **kwargs)
        self.path = path

    def _perform(self, engine):
        return
