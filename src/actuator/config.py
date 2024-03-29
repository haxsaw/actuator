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

'''
Support for creating Actuator configuration models.
'''

import getpass
import itertools
from collections import Iterable
import networkx as nx
from actuator.modeling import (ModelComponent, ModelReference,
                               AbstractModelReference, ModelInstanceReference,
                               ModelBase, ModelBaseMeta)
from actuator.namespace import _ComputableValue, NamespaceModel
from actuator.utils import ClassModifier, process_modifiers
from actuator.infra import IPAddressable

class ConfigException(Exception): pass

_searchpath = "__searchpath__"
@ClassModifier
def with_searchpath(cls, *args, **kwargs):
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
def with_dependencies(cls, *args, **kwargs):
    """
    Express dependencies between tasks to ensure their proper execution order
    
    This function takes dependency expressions involving tasks and captures
    them in the current config model class. These dependencies are respected
    when it comes time to execute the config tasks against a particular
    namespace model. NOTE: this function can *only* be used within a config
    model class statement.
    
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
            raise ConfigException("Argument %s is not a dependency" % str(arg))
    deps.extend(list(args))
    
_config_options = "__config_options__"
_default_task_role = "default_task_role"
_remote_user = "remote_user"
_private_key_file = "private_key_file"
_default_run_from = "default_run_from"
_legal_options = set([_default_task_role, _remote_user, _private_key_file,
                      _default_run_from])
@ClassModifier
def with_config_options(cls, *args, **kwargs):
    """
    Set up options to apply to the config model as a whole
    
    Use this function to establish options on the overall operation of the
    config model. Options are all keyword arguments with an appropriate
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
    opts = cls.__dict__.get(_config_options)
    if opts is None:
        opts = {}
        setattr(cls, _config_options, opts)
    for k, v in kwargs.items():
        if k not in _legal_options:
            raise ConfigException("Unrecognized option: {}".format(k))
        opts[k] = v
    
_node_dict = "_node_dict"
#
#@FIXME at the moment, this capability doesn't make sense in the larger scheme of
#config models; this is because although you could theoretically add a bunch of
#tasks from some task library, you won't have access to the objects to enter
#them into dependency expressions in any easy way. Even if you added the expressions
#in the same library module and just added them with "with_dependencies", you
#would still have an awkward time knintting those in to the overall dependency
#structure of the config. So until that gets figured out this functionality
#is off. Besides, it isn't working properly anyway, as the base metaclass
#expects things to be dumped into the "__components" dict in the class,
#not '_node_dict'
#
# @ClassModifier
# def with_tasks(cls, *args, **kwargs):
#     task_nodes = cls.__dict__.get(_node_dict)
#     if task_nodes is None:
#         task_nodes = {}
#         setattr(cls, _node_dict, task_nodes)
#     task_nodes.update({v:k for k, v in kwargs.items()})
    

class Orable(object):
    #internal
    def _or_result_class(self):
        return Orable
    
    def _and_result_class(self):
        return TaskGroup
    
    def __nonzero__(self):
        #everything needs to return False as otherwise expression
        #short-circuiting may cause some of the expression to get skipped
        return False
    
    def __and__(self, other):
        if isinstance(other, Orable):
            return self._and_result_class()(self, other)
        else:
            raise ConfigException("RHS is not 'andable': %s" % str(other))
    
    def __or__(self, other):
        if isinstance(other, Orable):
            return self._or_result_class()(self, other)
        else:
            raise ConfigException("RHS is not 'orable': %s" % str(other))
        
    def entry_nodes(self):
        return []
    
    def exit_nodes(self):
        return []
    
    
class _ConfigTask(Orable, ModelComponent):
    """
    Base class for all config model tasks.
    
    This class establishes the base instantiation and operational protocol
    for all tasks.
    
    @param name: String. Logical name for the task.
    @keyword task_role: A reference to a Role in the namespace model. This
        can be a model reference, context expression, or callable that takes
        an L{actuator.modeling.CallContext} and returns a model instance
        reference. The role determines the view of the namespace that is to be
        used; the Vars visible from the perspective of this Role are what will
        govern the operation of the task. If no task_role has been identified,
        one may still be assigned due to the actions of the task container
        classes (such as MultiTask). If a task_role can't be determined, then
        the config model's default_task_role is used. If that can't be determined
        then an exception is raised.
        
        In the absence of a run_from Role, the task_role also determines where
        the task is to run (it is run on the host associated with the Role).
    @keyword run_from: A reference to a Role in the namespace model. This can
        a model reference, context expression, or a callable that takes an
        L{actuator.modeling.CallContext} and returns model instance reference
        to a Role. The host associated with this role is where the task will
        be run, however the Vars used be those associated with the Role
        identified as the task_role.
    @keyword repeat_count: Integer, defaults to 1. Identifies the number of times
        to allow the task to fail before admitting defeat and aborting the 
        task's execution (potentially aborting the config as well). A delay is
        inserted between each attempt in order to give a system a chance to
        stabilize before another attempt is made. The delay is the attempt
        number times the repeat_interval (see below), so each attempt has a
        longer delay before the next attempt.
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
    @keyword delegate: internal
    """
    def __init__(self, name, task_role=None, run_from=None,
                 repeat_til_success=True, repeat_count=1, repeat_interval=15,
                 remote_user=None, remote_pass=None, private_key_file=None,
                 delegate=None):
        super(_ConfigTask, self).__init__(name)
        self.task_role = None
        self._task_role = task_role
        self.run_from = None
        self._run_from = run_from
        self.repeat_til_success = None
        self._repeat_til_success = repeat_til_success
        self.repeat_count = None
        self._repeat_count = repeat_count
        self.repeat_interval = None
        self._repeat_interval = repeat_interval
        self.remote_user = None
        self._remote_user = remote_user
        self.remote_pass = None
        self._remote_pass = remote_pass
        self.private_key_file = None
        self._private_key_file = private_key_file
        self.delegate = delegate
        
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
            the_vars = {k:v.get_value(task_role)
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
        
    def _embedded_exittask_attrnames(self):
        #internal
        return []
    
    def _set_delegate(self, delegate):
        #internal
        self.delegate = delegate
    
    def get_remote_user(self):
        """
        Return the effective remote user to use for this task.
        """
        remote_user = (self.remote_user
                       if self.remote_user is not None
                       else (self.delegate.get_remote_user()
                             if self.delegate is not None
                             else None))
        return remote_user
    
    def get_remote_pass(self):
        """
        Return the effective remote password to use for this user.
        """
        remote_pass = (self.remote_pass
                       if self.remote_pass is not None
                       else (self.delegate.get_remote_pass()
                             if self.delegate is not None
                             else None))
        return remote_pass
    
    def get_private_key_file(self):
        """
        Return the effective private key file to use for this task.
        """
        private_key_file = (self.private_key_file
                            if self.private_key_file is not None
                            else (self.delegate.get_private_key_file()
                                  if self.delegate is not None
                                  else None))
        return private_key_file
        
    def get_task_host(self):
        """
        Return the host associated with the task_role for this task.
        """
        comp = self.get_task_role()
        host = (comp.host_ref
                if isinstance(comp.host_ref, basestring)
                else comp.host_ref.value())
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host
    
    def get_task_role(self):
        """
        Return the Role associated with this task.
        """
        self.fix_arguments()
        if self.task_role is not None:
            comp = self.task_role
        elif self._model_instance:
            #fetch the default task role for the entire model
            #this can raise an exception if there isn't a
            #default task role defined for the model
            comp = self._model_instance.get_task_role()
        else:
            raise ConfigException("Can't find a task role for task {}".format(self.name))
        return comp
    
    def get_run_from(self):
        """
        Return the Role associated with the run_from Role for this task
        """
        self.fix_arguments()
        if self.run_from is not None:
            comp = self.run_from
        elif self._model_instance:
            comp = self._model_instance.get_run_from()
        else:
            comp = None
        return comp
    
    def get_run_host(self):
        """
        Return the host associated with the run_from Role for this task.
        """
        comp = self.get_run_from()
        host = (comp.host_ref
                if isinstance(comp.host_ref, basestring)
                else comp.host_ref.value())
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host            
        
    def get_init_args(self):
        __doc__ = ModelComponent.__doc__
        return ((self.name,), {"task_role":self._task_role,
                              "run_from":self._run_from,
                              "repeat_til_success":self._repeat_til_success,
                              "repeat_count":self._repeat_count,
                              "repeat_interval":self._repeat_interval,
                              "remote_user":self._remote_user,
                              "remote_pass":self._remote_pass,
                              "private_key_file":self._private_key_file
                              })
        
    def _get_arg_value(self, arg):
        val = super(_ConfigTask, self)._get_arg_value(arg)
        if isinstance(val, basestring):
            #check if we have a variable to resolve
            cv = _ComputableValue(val)
            try:
                var_context = self.get_task_role()
            except ConfigException, _:
                mi = self.get_model_instance()
                if mi is None:
                    raise ConfigException("Can't find a model to get a default var context")
                var_context = mi.namespace_model_instance
                if var_context is None:
                    raise ConfigException("Can't find a namespace to use as a var context")
            val = cv.expand(var_context)
#             val = cv.expand(self.get_task_role())
        elif isinstance(val, ModelReference) and self._model_instance:
            val = self._model_instance.get_namespace().get_inst_ref(val)
        return val
            
    def _fix_arguments(self):
        self.task_role = self._get_arg_value(self._task_role)
        self.run_from = self._get_arg_value(self._run_from)
        self.repeat_til_success = self._get_arg_value(self._repeat_til_success)
        self.repeat_count = self._get_arg_value(self._repeat_count)
        self.repeat_interval = self._get_arg_value(self._repeat_interval)
        self.remote_user = self._get_arg_value(self._remote_user)
        self.remote_pass = self._get_arg_value(self._remote_pass)
        self.private_key_file = self._get_arg_value(self._private_key_file)
        
    def _or_result_class(self):
        return _Dependency
    
    def entry_nodes(self):
        """
        Internal
        """
        return [self]
    
    def exit_nodes(self):
        """
        Internal
        """
        return [self]
    
    def perform(self):
        """
        Perform the task. Must be overridden to actually work. Typically,
        tasks have helper objects that actually do the work; they don't do
        the work themselves.
        """
        raise TypeError("Derived class must implement")
    
    
class StructuralTask(object):
    """
    Flag mixin class to indicate a task that that is only for structuring
    other tasks.
    """
    pass
    
    
class RendezvousTask(_ConfigTask, StructuralTask):
    """
    Internally used task for some of the container tasks; allows a common
    exit point to be identified for all tasks in the container.
    """
    def perform(self):
        return
    

class ConfigModelMeta(ModelBaseMeta):
    def __new__(cls, name, bases, attr_dict):
        all_tasks = {v:k for k, v in attr_dict.items() if isinstance(v, _ConfigTask)}
        attr_dict[_node_dict] = all_tasks
        if _config_options not in attr_dict:
            attr_dict[_config_options] = {}
        newbie = super(ConfigModelMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(newbie)
        for v, k in getattr(newbie, _node_dict).items():
            setattr(newbie, k, v)
        graph = nx.DiGraph()
        graph.add_nodes_from(newbie._node_dict.keys())
        if hasattr(newbie, _dependencies):
            deps = newbie.get_class_dependencies()
            graph.add_edges_from( [d.edge() for d in deps] )
            try:
                _ = nx.topological_sort(graph)
            except nx.NetworkXUnfeasible, _:
                raise ConfigException("Task dependency graph contains a cycle")
        return newbie
    

class ConfigModel(ModelBase):
    """
    Base class for all config models.
    
    This class is used to define Actuator config models. Instances of the class
    will be married to a namespace such that the model can find the Roles
    associated with each task. Once an instance is made and associated with
    a namespace the tasks in the model can be peformed.
    """
    __metaclass__ = ConfigModelMeta
    ref_class = ModelInstanceReference
    
    def __init__(self, namespace_model_instance=None, nexus=None,
                 remote_user=None, remote_pass=None, private_key_file=None,
                 delegate=None, default_task_role=None, default_run_from=None):
        """
        Create a new ConfigModel derived class instance.
        
        Create an instance of a config model. You may override this method as
        long as you call super().__init__() in your init and pass along all the
        keyword arguments that were passed into your derived class.
        
        @keyword namespace_model_instance: Default None, otherwise an instance
            of a class derived from L{NamespaceModel}. You don't need to pass
            the namespace to the config model if you're using Actuator's
            orchestrator to drive the config model; the orchestrator will take
            care of it for you. You normally never need to provide this argument.
        @keyword nexus: Internal
        @keyword remote_user: String; default is None. This value provides the
            default remote_user for tasks that don't otherwise have their own
            remote_user set. Task remote_users take precendence over this value,
            but this value has precedence over the value supplied in
            with_config_options(). If the user can't be determined any other
            way, the current user name is used for remote access
        @keyword remote_pass: String; default is None. This arg provides the
            password to use with the remote user as determined by above.
            Tasks remote_pass takes precendence over this value, but this value
            takes precedence over the remote_pass supplied in
            with_config_options(). NOTE: this has yet to be observed to actually
            work; Ansible always reports a BROKEN PIPE when trying to use
            sshpass to make use of this argument. Use key pairs instead.
        @keyword private_key_file: Striing; path to the private part of an ssh
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
        """
        
        super(ConfigModel, self).__init__(nexus=nexus)
        self.namespace_model_instance = namespace_model_instance
        self.remote_user = remote_user
        self.remote_pass = remote_pass
        self.private_key_file = private_key_file
        self.default_task_role = default_task_role
        self.default_run_from = default_run_from
        self.delegate = delegate
        clone_dict = {}
        #NOTE! _node_dict is an inverted dictionary (the string keys are
        #stored as values
        for v, k in self._node_dict.items():
            if not isinstance(v, _ConfigTask):
                raise ConfigException("'%s' is not a task" % k)
            clone = v.clone()
            clone._set_delegate(self)
            clone._set_model_instance(self)
            clone_dict[v] = clone
            for etan in v._embedded_exittask_attrnames():
                clone_dict[getattr(v, etan)] = getattr(clone, etan)
            setattr(self, k, clone)
            _ = getattr(self, k)  #this primes the reference machinery
        self.dependencies = [d.clone(clone_dict)
                             for d in self.get_class_dependencies()]
        #default option values
        opts = object.__getattribute__(self, _config_options)
        for k, v in opts.items():
            if k == _default_task_role and self.default_task_role is None:
                self.default_task_role = v
            elif k == _remote_user and self.remote_user is None:
                self.remote_user = v
            elif k == _private_key_file and self.private_key_file is None:
                self.private_key_file = v
            elif k == _default_run_from and self.default_run_from is None:
                self.default_run_from = v
                
    def _set_delegate(self, delegate):
        self.delegate = delegate
    
    def get_remote_user(self):
        """
        Compute the remote user to use for a task.
        
        This returns the remote_user specified on this object, or returns
        the remote_user from the delegate if there is no remote_user and there
        is a delegate. If a remote_user can't be determined, the current user
        is used for the remote user.
        """
        remote_user = (self.remote_user
                       if self.remote_user is not None
                       else (self.delegate.get_remote_user()
                             if self.delegate is not None
                             else None))
        return remote_user
    
    def get_remote_pass(self):
        """
        Compute the remote_pass to use for the remote_user.
        
        Return the remote_pass on this object, or if there isn't one and there
        is a delegate, return the delegate's remote_user. NOTE: I have yet
        to see Ansible process this option properly even with sshpass installed;
        Ansible fails with a BROKEN PIPE error on the sshpass command. For the
        time being use the private_key_file option for login credentials instead.
        """
        remote_pass = (self.remote_pass
                       if self.remote_pass is not None
                       else (self.delegate.get_remote_pass()
                             if self.delegate is not None
                             else None))
        return remote_pass
    
    def get_private_key_file(self):
        """
        Compute the private_key_file to use for the remote_user.
        
        Return the private_key_file on this object, or if there isn't one and
        there is a delegate, return the delegate's private_key_file.
        """
        private_key_file = (self.private_key_file
                            if self.private_key_file is not None
                            else (self.delegate.get_private_key_file()
                                  if self.delegate is not None
                                  else None))
        return private_key_file
        
    def set_task_role(self, task_role):
        """
        Internal; sets the default_task_role for the model. Users generally
        don't need to use this method.
        """
        if not isinstance(task_role, AbstractModelReference):
            raise ConfigException("A default task role was supplied that isn't some kind of model reference: %s" %
                                  str(task_role))
        self.default_task_role = task_role
                
    def get_graph(self, with_fix=False):
        """
        Returns a NetworkX DiiGraph object consisting of the tasks that are
        in the model.
        
        The graph returned is a clean instance of the graph that governs the
        operation of configuration under the orchestrator. That means it
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
        deps = self.get_dependencies()
        graph = nx.DiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from( [d.edge() for d in deps] )
        return graph
        
    def get_task_host(self):
        """
        Compute the IP address of the host for the task.
        
        This method takes the value returned by L{get_task_role}. and returns
        a string that is the IP address for the value returned, if any. This
        does not take into account and run_from value.
        """
        comp = self.get_task_role()
        host = (comp.host_ref
                if isinstance(comp.host_ref, basestring)
                else comp.host_ref.value())
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host        
    
    def get_task_role(self):
        """
        Compute the L{Role} to use for as the default task_role for this model.
        
        This method computes the task_role, either from this model or from 
        the model's delegate, and returns the actual Role object to use.
        """
        if self.default_task_role is None and self.delegate is None:
            raise ConfigException("No default task role defined on the config model")

        if self.namespace_model_instance is None:
            raise ConfigException("ConfigModel instance can't get a default task role from a Namespace model reference without an instance of that model")
        
        comp_ref = self.namespace_model_instance.get_inst_ref(self.default_task_role)
        comp_ref.fix_arguments()
        return comp_ref.value()
    
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
                raise ConfigException("ConfigModel can't get a namespace instance to acquire the default run_from")
            comp_ref = self.namespace_model_instance.get_inst_ref(self.default_run_from)
            comp_ref.fix_arguments()
            comp = comp_ref.value()
        return comp
    
    def get_run_host(self):
        """
        Compute the IP address of the host where the task is to run from.
        
        This method computes the IP address of the IP address of the host for
        the Role returned by L{get_run_from}, if there is one. If none, it
        returns None.
        """
        comp = self.get_run_from()
        host = (comp.host_ref
                if isinstance(comp.host_ref, basestring)
                else comp.host_ref.value())
        if isinstance(host, IPAddressable):
            host.fix_arguments()
            host = host.get_ip()
        return host
  
    def set_namespace(self, namespace):
        """
        Internal; sets the namespace to use for this config model so the
        model can determine what tasks to run where.
        
        @param namespace: An instance of a L{NamespaceModel} subclass.
        """
        if not isinstance(namespace, NamespaceModel):
            raise ConfigException("given an object that is not "
                                  "a kind of NamespaceModel: %s" % str(namespace))
        self.namespace_model_instance = namespace
        
    def get_namespace(self):
        """
        Returns the namespace model instance for this config model.
        """
        if not self.namespace_model_instance:
            self.namespace_model_instance = self.nexus.find_instance(NamespaceModel)
        return self.namespace_model_instance
        
    def get_dependencies(self):
        """
        Returns a list of _Dependency objects that captures all the task
        dependency pairs in the config model.
        """
        inst_nodes = [getattr(self, name).value() for name in self._node_dict.values()]
        return list(itertools.chain(list(itertools.chain(*[n.unpack()
                                                           for n in inst_nodes
                                                           if isinstance(n, _Unpackable)])),
                                    *[d.unpack() for d in self.dependencies]))
    
    @classmethod
    def get_class_dependencies(cls):
        """
        This method returns a list of _Dependency objects as defined on the 
        config model object, *not* an instance of the config model. This means
        that there may be few dependencies than in an instance as there won't
        be a namespace yet to influence the number of tasks to perform.
        """
        if hasattr(cls, _dependencies):
            deps = list(itertools.chain(*[d.unpack() for d in getattr(cls, _dependencies)]))
        else:
            deps = []
        return deps
    
    def get_tasks(self):
        """
        Returns a list of the L{_ConfigTask} objects in the model.
        """
        return [getattr(self, k).value() for k in self._node_dict.values()]


class _Cloneable(object):
    def clone(self, clone_dict):
        raise TypeError("Derived class must implement")
    
    
class _Unpackable(object):
    def unpack(self):
        """
        This method instructs the receiving object to represent any high-level constructs that
        represent dependency expression as simply instances of _Dependency objects
        involving tasks alone. This is because the workflow machinery can only operate
        on dependencies involving performable tasks and not the high-level representations
        that are used for dependency expressions.
        """
        return []
                    
    
class TaskGroup(Orable, _Cloneable, _Unpackable):
    """
    This class supplies an alternative to the use of the '&' operator when
    defining dependencies. It allows an arbitrary number of tasks to be noted
    to be run in parallel in the L{with_dependencies} function.
    
    This is an alternative to the use of '&' to indicate tasks that can be
    executed in parallel. For example, suppose we have tasks t1, t2, t3, and t4.
    Task t1 must be done first, then t2 and t3 can be done together, and after
    both are complete t4 can be done. You can use TaskGroup to indicate this
    in a with_dependencies call like so:
    
    with_dependencies(t1 | TaskGroup(t2, t3) | t4)
    
    TaskGroup can take any number of tasks or dependency expressions as
    arguments.
    """
    def __init__(self, *args):
        """
        Create a new TaskGroup with the indicated tasks or dependency expressions.
        
        @param *args: Any number of Tasks or dependency expressions (such as
            t1 | t2) that can be run in parallel.
        """
        for arg in args:
            if not isinstance(arg, Orable):
                raise ConfigException("argument %s is not a recognized TaskGroup arg type" % str(arg))
        self.args = list(args)
        
    def clone(self, clone_dict):
        """
        Internal; create a copy of this TaskGroup. If any of the tasks in the

        @param clone_dict: dict of already cloned tasks; so instead of making
            new copies of the in the group, re-use the copies in the dict. The
            dict has some kind of Orable as a key and the associated clone of
            that Orable as the value.
        """
        new_args = []
        for arg in self.args:
            if arg in clone_dict:
                new_args.append(clone_dict[arg])
            else:
                if isinstance(arg, _ConfigTask):
                    raise ConfigException("Found a task that didn't get cloned properly: %s" % arg.name)
                clone = arg.clone(clone_dict)
                clone_dict[arg] = clone
                new_args.append(clone)
        return TaskGroup(*new_args)
        
    def _or_result_class(self):
        return _Dependency

    def unpack(self):
        """
        Returns a flattened list of dependencies in this TaskGroup
        """
        return list(itertools.chain(*[arg.unpack()
                                      for arg in self.args
                                      if isinstance(arg, _Unpackable)]))
    
    def entry_nodes(self):
        """
        Returns a list of nodes that have no predecessors in the TaskGroup;
        these are the nodes that represent "entering" the group from a 
        dependency graph perspective.
        """
        return list(itertools.chain(*[arg.entry_nodes() for arg in self.args]))
    
    def exit_nodes(self):
        """
        Returns a list of nodes that have no successors in the TaskGroup;
        these are the nodes that represent "exiting" from the group
        from a dependency graph perspective.
        """
        return list(itertools.chain(*[arg.exit_nodes() for arg in self.args]))
    
    
class ConfigClassTask(_ConfigTask, _Unpackable, StructuralTask):
    """
    This class wraps up a ConfigModel and makes the entire model appear as
    a single task. This allows the construction of "models of models". The
    canonical use case is when your system has a number of Role on which a
    number of Tasks much all be performed with specific dependencies.
    ConfigClassTask allows you to create a model of these tasks for a single
    host, and then allows you to reuse that model, either in multiple contexts
    or as a common library of tasks to be performed on multiple Roles.
    """
    def __init__(self, name, cfg_class, init_args=None, **kwargs):
        """
        Create a new ConfigClassTask that wraps another config model
        
        @param name: String; logical name for the task
        @param cfg_class: A ConfigModel derived model class. NOTE: this is not an
            instance of a model class, but the model class itself. This wrapper
            will take care of making an instance when one is needed.
        @keyword init_args: Iterable. The positional arguments to pass to the
            model class when an instance it to be made.
        @keyword **kwargs: See L{_ConfigTask} for the remaining keyword arguments
            available to tasks. These will be available to the instance of the
            wrapped config model as this wrapper serves as the model's delegate.
        """
        if not issubclass(cfg_class, ConfigModel):
            raise ConfigException("The cfg_class parameter isn't a subclass of ConfigModel")
        super(ConfigClassTask, self).__init__(name, **kwargs)
        self.cfg_class = cfg_class
        self.init_args = None
        self._init_args = init_args if init_args else ()
        self.instance = None
        self.dependencies = []
        self.rendezvous = RendezvousTask("{}-rendezvous".format(name))
        self.graph = None
        
    def get_graph(self, with_fix=False):
        """
        Return a new instance of the NetworkX DiGraph that represents the 
        tasks and dependencies for the wrapped config model.
        
        @keyword with_fix: boolean, default False. Indicates whether or not to
            invoke fix_arguments() on the nodes before constructing the graph.
        """
        if with_fix:
            if self.graph:
                graph = self.graph
            elif self.instance is not None:
                graph = self.graph = self.instance.get_graph(with_fix=with_fix)
            else:
                init_args = self.init_args if self.init_args else ()
                instance = self.cfg_class(*init_args)
                graph = instance.get_graph()
        else:
            graph = self.instance.get_graph()
        return graph
    
    def _set_model_instance(self, mi):
        #internal
        super(ConfigClassTask, self)._set_model_instance(mi)
        self.rendezvous._set_model_instance(mi)
        
    def perform(self):
        """
        Null perform method for the wrapper itself.
        """
        return
    
    def _or_result_class(self):
        #internal
        return _Dependency
    
    def get_init_args(self):
        __doc__ = _ConfigTask.get_init_args.__doc__
        args, kwargs = super(ConfigClassTask, self).get_init_args()
        args = args + (self.cfg_class,)
        kwargs["init_args"] = self._init_args
        return args, kwargs
    
    def _fix_arguments(self):
        #internal
        super(ConfigClassTask, self)._fix_arguments()
        self.init_args = self._get_arg_value(self._init_args)
        init_args = self.init_args if self.init_args else ()
        model = self._model_instance
        self.instance = self.cfg_class(*init_args,
                                       namespace_model_instance=model.get_namespace(),
                                       nexus=model.nexus)
        self.instance.set_task_role(self.get_task_role())
        self.instance._set_delegate(self)
        graph = self.get_graph(with_fix=True)
        entry_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
        exit_nodes = [n for n in graph.nodes() if graph.out_degree(n) == 0]
        self.dependencies = itertools.chain(self.instance.get_dependencies(),
                                            [_Dependency(self, c) for c in entry_nodes],
                                            [_Dependency(c, self.rendezvous) for c in exit_nodes])

    def exit_nodes(self):
        """
        Returns the list of nodes that have no successors in the wrapped class.
        
        This is always the internal rendezvous class,
        """
        return [self.rendezvous]
    
    def _embedded_exittask_attrnames(self):
        return ["rendezvous"]
    
    def unpack(self):
        """
        Returns the list of _Dependencies for the nodes in the wrapped config
        model.
        """
        deps = list(self.dependencies)
        graph = self.get_graph(with_fix=True)
        deps.extend(itertools.chain(*[c.unpack() for c in graph.nodes()
                                      if isinstance(c, _Unpackable)]))
        return deps


class MultiTask(_ConfigTask, _Unpackable, StructuralTask):
    """
    This class allows a template task to be run against a list of different
    Roles.
    
    This class takes a template taska and a list of Roles, and creates an
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
            L{ConfigClassTask}, or even another MultiTask
        @param task_role_list: Must either be an explicit iterable of references
            to Roles, a callable that takes a L{CallContext} as an argument
            and returns an iterable of references to Roles, or a RefSelectBuilder
            expression (NamespaceModel.q expression) of the Roles to apply the
            task to
        @keyword **kwargs: keyword arguments as defined on L{_ConfigTask}
        """
        super(MultiTask, self).__init__(name, **kwargs)
        self.template = None
        self._template = template
        self.task_role_list = None
        self._task_role_list = task_role_list
        self.dependencies = []
        self.instances = []
        self.rendezvous = RendezvousTask("{}-rendezvous".format(name))
        
    def _set_model_instance(self, mi):
        super(MultiTask, self)._set_model_instance(mi)
        self.rendezvous._set_model_instance(mi)
        
    def perform(self):
        """
        Empty perform method for the MultiTask itself.
        """
        return
    
    def _embedded_exittask_attrnames(self):
        return ["rendezvous"]
        
    def _or_result_class(self):
        return _Dependency
    
    def get_init_args(self):
        __doc__ = _ConfigTask.get_init_args.__doc__
        args, kwargs = super(MultiTask, self).get_init_args()
        args = args + (self._template, self._task_role_list)
        return args, kwargs
    
    def _fix_arguments(self):
        super(MultiTask, self)._fix_arguments()
        self.rendezvous.fix_arguments()
        self.template = self._get_arg_value(self._template)
        self.task_role_list = self._get_arg_value(self._task_role_list)
        if isinstance(self.task_role_list, AbstractModelReference):
            try:
                keys = self.task_role_list.keys()
                comp_refs = [self.task_role_list[k] for k in keys]
            except TypeError, _:
                raise ConfigException("The value for task_role_list provided to the MultiTask "
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
            clone._set_model_instance(self._model_instance)
            clone.fix_arguments()
            self.instances.append(clone)
        self.dependencies = list(itertools.chain([_Dependency(self, c)
                                                  for c in self.instances],
                                                 [_Dependency(xit, self.rendezvous)
                                                  for c in self.instances
                                                  for xit in c.exit_nodes()]))
        
    def exit_nodes(self):
        return [self.rendezvous]
    
    def unpack(self):
        """
        Unpacks the internal dependencies for the tasks that the MultiTask contains,
        returns a list of _Dependency objects.
        """
        deps = list(self.dependencies)
        deps.extend(itertools.chain(*[c.unpack() for c in self.instances if isinstance(c, _Unpackable)]))
        return deps
        
    
class _Dependency(Orable, _Cloneable, _Unpackable):
    """
    Internal; represents a dependency between two tasks.
    """
    def __init__(self, from_task, to_task):
        if not isinstance(from_task, Orable):
            raise ConfigException("from_task is not a kind of _ConfigTask")
        if not isinstance(to_task, Orable):
            raise ConfigException("to_task is not a kind of _ConfigTask")
        self.from_task = from_task
        self.to_task = to_task
        
    def clone(self, clone_dict):
        from_task = (clone_dict[self.from_task]
                     if isinstance(self.from_task, _ConfigTask)
                     else self.from_task.clone(clone_dict))
        to_task = (clone_dict[self.to_task]
                   if isinstance(self.to_task, _ConfigTask)
                   else self.to_task.clone(clone_dict))
        return _Dependency(from_task, to_task)
        
    def _or_result_class(self):
        return _Dependency

    def entry_nodes(self):
        return self.from_task.entry_nodes()
    
    def exit_nodes(self):
        return self.to_task.exit_nodes()
        
    def edge(self):
        return self.from_task, self.to_task
    
    def unpack(self):
        """
        Since dependencies are "orable", it's entirely possible that a dependency may be
        set up between dependencies rather than between tasks (or a mix of tasks and dependencies).
        
        Actual work lists can only be constructed on dependencies between tasks, so what this 
        method does is unpack a set of nested dependencies and covert them into a proper list of
        dependencies between just tasks.
        """
        deps = []
        if isinstance(self.from_task, _Unpackable):
            deps.extend(self.from_task.unpack())
        if isinstance(self.to_task, _Unpackable):
            deps.extend(self.to_task.unpack())
        entries = self.from_task.exit_nodes()
        exits = self.to_task.entry_nodes()
        deps.extend([_Dependency(entry, eXit) for entry in entries for eXit in exits])
        return deps
    

class NullTask(_ConfigTask):
    """
    Non-functional task that's mostly good for testing
    """
    def __init__(self, name, path="", **kwargs):
        super(NullTask, self).__init__(name, **kwargs)
        self.path = path
        
    def perform(self):
        return
        
