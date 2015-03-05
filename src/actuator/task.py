# 
# Copyright (c) 2015 Tom Carroll
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

import itertools

from actuator import ActuatorException
from actuator.modeling import ModelComponent

class TaskException(ActuatorException): pass


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
            raise TaskException("RHS is not 'andable': %s" % str(other))
    
    def __or__(self, other):
        if isinstance(other, Orable):
            return self._or_result_class()(self, other)
        else:
            raise TaskException("RHS is not 'orable': %s" % str(other))
        
    def entry_nodes(self):
        return []
    
    def exit_nodes(self):
        return []
    
    
class _Task(Orable, ModelComponent):
    """
    Base class for all config model tasks.
    
    This class establishes the base instantiation and operational protocol
    for all tasks.
    
    @param name: String. Logical name for the task.
    @param repeat_til_success: Optional. Boolean, default True. Indicates if
        the task should only be run once, or repeated until it succeeds.
    @param repeat_count: Optional. Integer, default 1. If the task is to
        be repeated until it finally succeeds, this is the upper bound on how
        many times to repeat it. Exceeding this value causes the task to abort,
        as it is considered to possible to be successful.
    @param repeat_interval: Optional. Integer, default 15. This is the number of
        seconds to wait between attempts to perform the task. This value is
        multiplied by the attempt count, so that longer and longer pauses
        between attempts occur, giving the surrounding conditions time to
        stabilize or corrective measures to be taken before the maximum number
        of attempts are made.
    """
    def __init__(self, name, repeat_til_success=True, repeat_count=1,
                 repeat_interval=15):
        self.name = name
        super(_Task, self).__init__(name)
        self.repeat_til_success = None
        self._repeat_til_success = repeat_til_success
        self.repeat_count = None
        self._repeat_count = repeat_count
        self.repeat_interval = None
        self._repeat_interval = repeat_interval
        
    def _embedded_exittask_attrnames(self):
        #internal
        return []
    
    def get_init_args(self):
        __doc__ = ModelComponent.__doc__
        return ((self.name,), {"repeat_til_success":self._repeat_til_success,
                              "repeat_count":self._repeat_count,
                              "repeat_interval":self._repeat_interval,
                              })
        
    def _fix_arguments(self):
        self.repeat_til_success = self._get_arg_value(self._repeat_til_success)
        self.repeat_count = self._get_arg_value(self._repeat_count)
        self.repeat_interval = self._get_arg_value(self._repeat_interval)
        
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
    
    def reverse(self):
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
                raise TaskException("argument %s is not a recognized TaskGroup arg type" % str(arg))
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
                if isinstance(arg, _Task):
                    raise TaskException("Found a task that didn't get cloned properly: %s" % arg.name)
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
    

class _Dependency(Orable, _Cloneable, _Unpackable):
    """
    Internal; represents a dependency between two tasks.
    """
    def __init__(self, from_task, to_task):
        if not isinstance(from_task, Orable):
            raise TaskException("from_task is not a kind of _Task")
        if not isinstance(to_task, Orable):
            raise TaskException("to_task is not a kind of _Task")
        self.from_task = from_task
        self.to_task = to_task
        
    def clone(self, clone_dict):
        from_task = (clone_dict[self.from_task]
                     if isinstance(self.from_task, _Task)
                     else self.from_task.clone(clone_dict))
        to_task = (clone_dict[self.to_task]
                   if isinstance(self.to_task, _Task)
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
    

