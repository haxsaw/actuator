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
Created on 7 Sep 2014
'''
import itertools
import networkx as nx
from actuator.modeling import ModelComponent, ModelReference
from actuator.namespace import _ComputableValue
from actuator.utils import ClassModifier, process_modifiers

class ConfigException(Exception): pass

_searchpath = "__searchpath__"
@ClassModifier
def with_searchpath(cls, *args, **kwargs):
    searchpath = cls.__dict__.get(_searchpath)
    if searchpath is None:
        searchpath = []
        setattr(cls, _searchpath, searchpath)
    searchpath.extend(list(args))

_dependencies = "__dependencies__"
@ClassModifier
def with_dependencies(cls, *args, **kwargs):
    deps = cls.__dict__.get(_dependencies)
    if deps is None:
        deps = []
        setattr(cls, _dependencies, deps)
    for arg in args:
        if not isinstance(arg, _Cloneable):
            raise ConfigException("Argument %s is not a dependency: %s" % str(arg))
    deps.extend(list(args))
    
_node_dict = "_node_dict"
@ClassModifier
def with_tasks(cls, *args, **kwargs):
    task_nodes = cls.__dict__.get(_node_dict)
    if task_nodes is None:
        task_nodes = {}
        setattr(cls, _node_dict, task_nodes)
    task_nodes.update({v:k for k, v in kwargs.items()})
    

class Orable(object):
    def _or_result_class(self):
        return Orable
    
    def _and_result_class(self):
        return TaskGroup
    
    def __nonzero__(self):
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
    def __init__(self, name, task_component=None, run_from=None, repeat_til_success=False,
                 repeat_count=1, repeat_interval=5):
        super(_ConfigTask, self).__init__(name)
        self.task_component = None
        self._task_component = task_component
        self.run_from = None
        self._run_from = run_from
        self.repeat_til_success = None
        self._repeat_til_success = repeat_til_success
        self.repeat_count = None
        self._repeat_count = repeat_count
        self.repeat_interval = None
        self._repeat_interval = repeat_interval
        
    def get_task_host(self):
        if self.task_component:
            host = (self.task_component.host_ref
                    if isinstance(self.task_component.host_ref, basestring)
                    else self.task_component.host_ref.value())
        else:
            host = None
        return host
        
    def get_init_args(self):
        return ((self.name,), {"task_component":self._task_component,
                              "run_from":self._run_from,
                              "repeat_til_success":self._repeat_til_success,
                              "repeat_count":self._repeat_count,
                              "repeat_interval":self._repeat_interval})
        
    def _get_arg_value(self, arg):
        val = super(_ConfigTask, self)._get_arg_value(arg)
        if isinstance(val, basestring):
            #check if we have a variable to resolve
            cv = _ComputableValue(val)
            val = cv.expand(self.task_component)
        elif isinstance(val, ModelReference) and self._model_instance:
            val = self._model_instance.namespace_model_instance.get_inst_ref(val)
        return val
            
    def _fix_arguments(self):
        self.task_component = self._get_arg_value(self._task_component)
        self.run_from = self._get_arg_value(self._run_from)
        self.repeat_til_success = self._get_arg_value(self._repeat_til_success)
        self.repeat_count = self._get_arg_value(self._repeat_count)
        self.repeat_interval = self._get_arg_value(self._repeat_interval)
        
    def _or_result_class(self):
        return _Dependency
    
    def entry_nodes(self):
        return [self]
    
    def exit_nodes(self):
        return [self]
    
    def perform(self):
        raise TypeError("Derived class must implement")
    
    
class ConfigSpecMeta(type):
    def __new__(cls, name, bases, attr_dict):
        all_tasks = {v:k for k, v in attr_dict.items() if isinstance(v, _ConfigTask)}
        attr_dict[_node_dict] = all_tasks
        newbie = super(ConfigSpecMeta, cls).__new__(cls, name, bases, attr_dict)
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
    

class ConfigSpec(object):
    __metaclass__ = ConfigSpecMeta
    
    def __init__(self, namespace_model_instance=None):
        self.namespace_model_instance = namespace_model_instance
        clone_dict = {}
        for v, k in self._node_dict.items():
            if not isinstance(v, _ConfigTask):
                raise ConfigException("'%s' is not a task" % k)
            clone = v.clone()
            clone._set_model_instance(self)
            clone_dict[v] = clone
            setattr(self, k, clone)
        self.dependencies = [d.clone(clone_dict)
                             for d in self.get_class_dependencies()]
            
    def set_namespace(self, namespace):
        self.namespace_model_instance = namespace
        
    def get_dependencies(self):
        return list(self.dependencies)
    
    @classmethod
    def get_class_dependencies(cls):
        if hasattr(cls, _dependencies):
            deps = list(itertools.chain(*[d.unpack() for d in getattr(cls, _dependencies)]))
        else:
            deps = []
        return deps
    
    def get_tasks(self):
        return [getattr(self, k) for k in self._node_dict.values()]


class _Cloneable(object):
    def clone(self, clone_dict):
        raise TypeError("Derived class must implement")
                    
    
class TaskGroup(Orable, _Cloneable):
    def __init__(self, *args):
        for arg in args:
            if not isinstance(arg, Orable):
                raise ConfigException("argument %s is not a recognized TaskGroup arg type" % str(arg))
        self.args = list(args)
        
    def clone(self, clone_dict):
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
        return list(itertools.chain(*[arg.unpack()
                                      for arg in self.args
                                      if isinstance(arg, (_Dependency, TaskGroup))]))
    
    def entry_nodes(self):
        return list(itertools.chain(*[arg.entry_nodes() for arg in self.args]))
    
    def exit_nodes(self):
        return list(itertools.chain(*[arg.exit_nodes() for arg in self.args]))
    

class _Dependency(Orable, _Cloneable):
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
        if isinstance(self.from_task, (_Dependency, TaskGroup)):
            deps.extend(self.from_task.unpack())
        if isinstance(self.to_task, (_Dependency, TaskGroup)):
            deps.extend(self.to_task.unpack())
        entries = self.from_task.exit_nodes()
        exits = self.to_task.entry_nodes()
        deps.extend([_Dependency(entry, eXit) for entry in entries for eXit in exits])
        return deps
    

class NullTask(_ConfigTask):
    def __init__(self, name, path="", **kwargs):
        super(NullTask, self).__init__(name, **kwargs)
        self.path = path
        
        
class MakeDir(_ConfigTask):
    def __init__(self, name, path="", **kwargs):
        super(MakeDir, self).__init__(name, **kwargs)
        self.path = path


class Template(_ConfigTask):
    def __init__(self, name, path="", **kwargs):
        super(Template, self).__init__(name, **kwargs)
        self.path = path


class CopyAssets(_ConfigTask):
    def __init__(self, name, path="", **kwargs):
        super(CopyAssets, self).__init__(name, **kwargs)
        self.path = path


class ConfigJob(_ConfigTask):
    def __init__(self, name, path="", **kwargs):
        super(ConfigJob, self).__init__(name, **kwargs)
        self.path = path

