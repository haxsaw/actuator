'''
Created on 7 Sep 2014

@author: tom
'''
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


class _ConfigTask(object):
    def __rshift__(self, other):
        if isinstance(other, _ConfigTask):
            return _Dependency(self, other)
        else:
            raise ConfigException("Unrecognized type on RHS of dependency operator: %s" % str(type(other)))
        
        
class ConfigSpecMeta(type):
    def __new__(cls, name, bases, attr_dict):
        all_tasks = {v:k for k, v in attr_dict.items() if isinstance(v, _ConfigTask)}
        attr_dict["_node_dict_"] = all_tasks
        newbie = super(ConfigSpecMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(newbie)
        graph = nx.DiGraph()
        graph.add_nodes_from(newbie._node_dict_.keys())
        if hasattr(newbie, _dependencies):
            graph.add_edges_from( [d.edge() for d in newbie.__dependencies__] )
            try:
                _ = nx.topological_sort(graph)
            except nx.NetworkXUnfeasible, _:
                raise ConfigException("Task dependency graph contains a cycle")
        return newbie
    

class ConfigSpec(object):
    __metaclass__ = ConfigSpecMeta
    
    
class _Dependency(object):
    def __init__(self, from_task, to_task):
        if not isinstance(from_task, _ConfigTask):
            raise ConfigException("from_task is not a kind of _ConfigTask")
        if not isinstance(to_task, _ConfigTask):
            raise ConfigException("to_task is not a kind of _ConfigTask")
        self.from_task = from_task
        self.to_task = to_task
        
    def edge(self):
        return self.from_task, self.to_task
    

class MakeDir(_ConfigTask):
    pass


class Template(_ConfigTask):
    pass


class CopyAssets(_ConfigTask):
    pass


class ConfigJob(_ConfigTask):
    pass

