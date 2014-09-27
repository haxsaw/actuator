'''
Created on 7 Sep 2014

@author: tom
'''
import itertools
import networkx as nx
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
    deps.extend(list(args))
    

class Orable(object):
    def _or_result_class(self):
        return Orable
    
    def __or__(self, other):
        if isinstance(other, Orable):
            return self._or_result_class()(self, other)
        else:
            raise ConfigException("RHS is not 'orable': %s" % str(other))
        
    def entry_nodes(self):
        return []
    
    def exit_nodes(self):
        return []


class _ConfigTask(Orable):
    def _or_result_class(self):
        return _Dependency
    
    def entry_nodes(self):
        return [self]
    
    def exit_nodes(self):
        return [self]
    
        
class ConfigSpecMeta(type):
    def __new__(cls, name, bases, attr_dict):
        all_tasks = {v:k for k, v in attr_dict.items() if isinstance(v, _ConfigTask)}
        attr_dict["_node_dict_"] = all_tasks
        newbie = super(ConfigSpecMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(newbie)
        graph = nx.DiGraph()
        graph.add_nodes_from(newbie._node_dict_.keys())
        if hasattr(newbie, _dependencies):
            deps = newbie.get_dependencies()
            graph.add_edges_from( [d.edge() for d in deps] )
            try:
                _ = nx.topological_sort(graph)
            except nx.NetworkXUnfeasible, _:
                raise ConfigException("Task dependency graph contains a cycle")
        return newbie
    

class ConfigSpec(object):
    __metaclass__ = ConfigSpecMeta
    
    @classmethod
    def get_dependencies(cls):
        if hasattr(cls, _dependencies):
            deps = list(itertools.chain(*[d.unpack() for d in getattr(cls, _dependencies)]))
        else:
            deps = []
        return deps
    
    
class TaskGroup(Orable):
    def _or_result_class(self):
        return _Dependency

    def __init__(self, *args):
        for arg in args:
            if not isinstance(arg, Orable):
                raise ConfigException("argument %s is not a recognized TaskGroup arg type" % str(arg))
        self.args = list(args)
        
    def unpack(self):
        return list(itertools.chain(*[arg.unpack()
                                      for arg in self.args
                                      if isinstance(arg, (_Dependency, TaskGroup))]))
    
    def entry_nodes(self):
        return list(itertools.chain(*[arg.entry_nodes() for arg in self.args]))
    
    def exit_nodes(self):
        return list(itertools.chain(*[arg.exit_nodes() for arg in self.args]))
    

class _Dependency(Orable):
    def _or_result_class(self):
        return _Dependency

    def __init__(self, from_task, to_task):
        if not isinstance(from_task, Orable):
            raise ConfigException("from_task is not a kind of _ConfigTask")
        if not isinstance(to_task, Orable):
            raise ConfigException("to_task is not a kind of _ConfigTask")
        self.from_task = from_task
        self.to_task = to_task
        
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
    

class MakeDir(_ConfigTask):
    def __init__(self, path=""):
        self.path = path


class Template(_ConfigTask):
    pass


class CopyAssets(_ConfigTask):
    pass


class ConfigJob(_ConfigTask):
    pass

