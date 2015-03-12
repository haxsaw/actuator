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
import networkx as nx
import Queue
import random
import sys
import threading
import time
import traceback

from actuator import ActuatorException
from actuator.utils import root_logger, LOG_INFO
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
    
    
class Task(Orable, ModelComponent):
    """
    Base class for all tasks
    
    This class provides the base protocol for all tasks; it deals with
    dependencies, cloning, embedded tasks, task performance and unwinding.
    """
    UNSTARTED = 1
    PERFORMED = 2
    REVERSED = 3
    def __init__(self, name, repeat_til_success=True, repeat_count=1,
                 repeat_interval=15):
        """
        Create a new Task
        
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
        self.name = name
        super(Task, self).__init__(name)
        self.repeat_til_success = None
        self._repeat_til_success = repeat_til_success
        self.repeat_count = None
        self._repeat_count = repeat_count
        self.repeat_interval = None
        self._repeat_interval = repeat_interval
        self.status = self.UNSTARTED
        
    def perform(self, engine):
        """
        Perform the task.
        
        Do no override this method! Instead, override
        L{Task._perform); this is the method for specializing functionality.
                
        @param engine: an instance of a L{TaskEngine}; this will get passed as the
            sole argument to self._perform()
        """
        if self.status == self.UNSTARTED:
            self._perform(engine)
            self.status = self.PERFORMED
            
    def _perform(self, engine):
        """
        Does the actual work in performing the task.
        
        Specific task classes must override this method (and not call super())
        and in their implemention perform the work needed for the task.
        
        The default implementation just raises TypeError
        
        @raise TypeError: Raised by the default implementation; method must
            be overridden.
        """
        raise TypeError("Derived class must implement")
    
    def reverse(self, engine):
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
        
        Don't override this method; instead, override L{Task._reverse}
        
        @param engine: an instance of L{TaskEngine}. this will passed as the sole
            argument to self._reverse()
        """
        if self.status == self.PERFORMED:
            self._reverse(engine)
            self.status = self.REVERSED
            
    def _reverse(self, engine):
        """
        "undo" whatever was done in perform.
        
        Subclasses should override this method to provide a way to "undo" what
        was done in perform. If there is no need to "undo", this method may
        be ignored. The default implementation does nothing.
        """
        return
        
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
                if isinstance(arg, Task):
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
            raise TaskException("from_task is not a kind of Task")
        if not isinstance(to_task, Orable):
            raise TaskException("to_task is not a kind of Task")
        self.from_task = from_task
        self.to_task = to_task
        
    def clone(self, clone_dict):
        from_task = (clone_dict[self.from_task]
                     if isinstance(self.from_task, Task)
                     else self.from_task.clone(clone_dict))
        to_task = (clone_dict[self.to_task]
                   if isinstance(self.to_task, Task)
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
    
    
class GraphableModelMixin(object):
    """
    This mixin class provides a way to flag models that contain graphable
    Tasks and acquire graphs of the Tasks they contain.
    """
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
    
    def get_tasks(self):
        """
        Returns an iterable of Task objects that will be nodes in the graph
        
        This method should return an iterable of Tasks (derived classes fine)
        that will be the nodes in the graph. Classes that use this mixin need
        to provide their own implementation; the default raises a TypeError.
        
        @raise TypeError: Derived class must override this method
        """
        raise TypeError("Derived class must implement get_tasks()")
    
    def get_dependencies(self):
        """
        Returns an iterable of _Dependency objects for the tasks
        
        This method returns an iterable of _Dependency objects for the tasks
        involved named in get_tasks(). Note that while it is allowable for a
        Task not to appear in a _Dependency, all Tasks that are part of
        _Dependencies must be be in the set of things returned by get_tasks().
        Classes that use this mixin need to provide their own implementation;
        the default raises a TypeError.
        
        @raise TypeError: Derived class must override this method
        """
        raise TypeError("Derived class must implement get_tasks()")

        
class TaskEngine(object):
    """
    Base class for execution agents. The mechanics of actually executing a task
    are left to the derived class; this class takes care of all the business of
    managing the task dependency graph and deciding what tasks should be run
    when.
    """
    exception_class = TaskException
    exec_agent = "task_engine"
    def __init__(self, name, model, num_threads=5, do_log=False, no_delay=False,
                 log_level=LOG_INFO):
        """
        Make a new TaskEngine
        
        @param model: some kind of L{actuator.modeling.ModelBase} and
            L{GraphableModelMixin}
        @keyword num_threads: Integer, default 5. The number of worker threads
            to spin up to perform tasks.
        @keyword do_log: boolean, default False. If True, creates a log file
            that contains more detailed logs of the activities carried out.
            Independent of log_level (see below).
        @keyword no_delay: boolean, default False. The default causes a short
            pause of up to 2.5 seconds to be taken before a task is started.
            This keeps a single host from being bombarded with too many ssh
            requests at the same time in the case where a number of different
            tasks can all start in parallel on the same Role's host.
        @keyword log_level: Any of the symbolic log levels in the actuator root
            package, LOG_CRIT, LOG_DEBUG, LOG_ERROR, LOG_INFO, or LOG_WARN
        """
        if not isinstance(model, GraphableModelMixin):
            raise TaskException("TaskEngine was not passed a kind "
                                "of GraphableModelMixin; %s" % str(model))
        root_logger.setLevel(log_level)
        self.model = model
        self.name = name
        self.task_queue = Queue.Queue()
        self.node_lock = threading.Lock()
        self.stop = False
        self.aborted_tasks = []
        self.num_tasks_to_perform = None
        self.config_record = None
        self.num_threads = num_threads
        self.do_log = do_log
        self.no_delay = no_delay
        self.graph = None
        
    def record_aborted_task(self, task, etype, value, tb):
        """
        Internal; used by a worker thread to report that it is giving up on
        performing a task.
        
        @param task: The task that is aborting
        @param etype: The aborting exception type
        @param value: The exception value
        @param tb: The exception traceback object, as returned by sys.exc_info()
        """
        self.aborted_tasks.append( (task, etype, value, tb) )
        
    def has_aborted_tasks(self):
        """
        Test to see if there are any aborted tasks
        """
        return len(self.aborted_tasks) > 0
    
    def get_aborted_tasks(self):
        """
        Returns a list of 4-tuples: the task that aborted, the exception type, the exception
        value, and the traceback.
        """
        return list(self.aborted_tasks)
    
    def make_format_func(self, task):
        ref = task.get_ref()
        path = ".".join(ref.get_path()) if ref is not None else "CAN'T.DETERMINE"
        def fmtmsg(msg):
            return "|".join([task.__class__.__name__, task.name, path,
                             str(task._id), msg])
        return fmtmsg
        
    def _reverse_task(self, task, logfile=None):
        #Actually reverse the task; the default asks the task to reverse itself
        task.reverse(self)
        
    def reverse_task(self, graph, task):
        """
        Internal, used to reverse a task in graph. Derived classes implement
        _reverse_task() to supply the actual mechanics for the underlying
        task execution system.
        
        @param graph: an NetworkX DiGraph; needed to find the next tasks
            to queue when the current one is done
        @param task: The actual task to perform
        
        LOGGING FORMAT:
        Some logging in this method embeds a sub-message in the log message. The
        fields in the sub message a separated by '|', and are as follows:
        - task type name
        - task name
        - task path in the model (or CAN'T.DETERMINE if a path can't be computed)
        - task id
        - name of the role the task is for (or NO_ROLE if there isn't a role)
        - id of the role (or empty if there is no role)
        - free-form text message
        """
        self._task_runner(task, "reverse", task.REVERSED)
    
    def _perform_task(self, task, logfile=None):
        #Actually do the task; the default asks the task to perform itself.
        task.perform(self)
        
    def perform_task(self, graph, task):
        """
        Internal, used to perform a task in graph. Derived classes implement
        _perform_task() to supply the actual mechanics of for the underlying
        task execution system.
        
        @param graph: an NetworkX DiGraph; needed to find the next tasks
            to queue when the current one is done
        @param task: The actual task to perform
        
        LOGGING FORMAT:
        Some logging in this method embeds a sub-message in the log message. The
        fields in the sub message a separated by '|', and are as follows:
        - task type name
        - task name
        - task path in the model (or CAN'T.DETERMINE if a path can't be computed)
        - task id
        - name of the role the task is for (or NO_ROLE if there isn't a role)
        - id of the role (or empty if there is no role)
        - free-form text message
        """
        self._task_runner(task, "perform", task.PERFORMED)
        
    def _task_runner(self, task, direction, success_status):
        fmtmsg = self.make_format_func(task)
        meth = getattr(self, "".join(["_", direction, "_task"]))
            
        logger = root_logger.getChild(self.exec_agent)
        logger.info(fmtmsg("processing started"))
        if not self.no_delay:
            time.sleep(random.uniform(0.2, 2.5))
        try_count = 0
        success = False
        if not task.fixed:
            task.fix_arguments()
        while try_count < task.repeat_count and not success:
            try_count += 1
            if self.do_log:
                logfile=open("{}.{}-try{}.txt".format(task.name, str(task._id)[-4:],
                                                      try_count), "w")
            else:
                logfile=None
            try:
                logger.info(fmtmsg("start %s-ing task" % direction))
#                 self._perform_task(task, logfile=logfile)
                meth(task, logfile=logfile)
#                 task.status = task.PERFORMED
                task.status = success_status
                logger.info(fmtmsg("task successfully %s-ed" % direction))
                success = True
            except Exception, e:
                logger.warning(fmtmsg("task %s failed" % direction))
                msg = ">>>Task {} Exception for {}!".format(direction, task.name)
                if logfile:
                    logfile.write("{}\n".format(msg))
                tb = sys.exc_info()[2]
                if try_count < task.repeat_count:
                    retry_wait = try_count * task.repeat_interval
                    logger.warning(fmtmsg("retrying after %d secs" % retry_wait))
                    msg = "Retrying {} again in {} secs".format(task.name, retry_wait)
                    if logfile:
                        logfile.write("{}\n".format(msg))
                        traceback.print_exception(type(e), e, tb, file=logfile)
                    time.sleep(retry_wait)
                else:
                    logger.error(fmtmsg("max tries exceeded; task aborting"))
                    self.record_aborted_task(task, type(e), e, tb)
                del tb
                sys.exc_clear()
            if logfile:
                logfile.flush()
                logfile.close()
                del logfile
#         if not success and try_count >= task.repeat_count:
        if not success:
            logger.error(fmtmsg("Could not be %s-ed; "
                         "aborting further task processing" % direction))
            self.abort_process_tasks()
    
    def abort_process_tasks(self):
        """
        The the agent to abort performing any further tasks.
        """
        self.stop = True
        
    def process_perform_task_queue(self):
        """
        Tell the agent to start performing tasks; results in calls to
        self.perform_task()
        """
        logger = root_logger.getChild("%s.process_perform_tasks" % self.exec_agent)
        while not self.stop:
            try:
                graph, task = self.task_queue.get(block=True, timeout=0.2)
                if not self.stop:
                    self.perform_task(graph, task)
                    if task.status == task.PERFORMED:
                        with self.node_lock:
                            self.num_tasks_to_perform -= 1
                            logger.debug("Remaining tasks to perform: %s" %
                                         self.num_tasks_to_perform)
                            if self.num_tasks_to_perform == 0:
                                self.stop = True
                            else:
                                for successor in graph.successors_iter(task):
                                    graph.node[successor]["ins_traversed"] += 1
                                    if graph.in_degree(successor) == graph.node[successor]["ins_traversed"]:
                                        logger.debug("queueing up %s for performance"
                                                            % successor.name)
                                        self.task_queue.put((graph, successor))
            except Queue.Empty, _:
                pass
            
    def process_reverse_task_queue(self):
        """
        Tell the agent to start reverse processing tasks; re
        """
        logger = root_logger.getChild("%s.process_reverse_tasks" % self.exec_agent)
        while not self.stop:
            try:
                graph, task = self.task_queue.get(block=True, timeout=0.2)
                if not self.stop:
                    self.reverse_task(graph, task)
                    if task.status == task.REVERSED:
                        with self.node_lock:
                            self.num_tasks_to_perform -= 1
                            logger.debug("Remaining tasks to reverse: %s" %
                                         self.num_tasks_to_perform)
                            if self.num_tasks_to_perform == 0:
                                self.stop = True
                            else:
                                for predecessor in graph.predecessors_iter(task):
                                    graph.node[predecessor]["outs_traversed"] += 1
                                    if graph.out_degree(predecessor) == graph.node[predecessor]["outs_traversed"]:
                                        logger.debug("queuing up %s for performance" %
                                                     predecessor.name)
                                        self.task_queue.put((graph, predecessor))
            except Queue.Empty, _:
                pass
            
    def perform_tasks(self, completion_record=None):
        fmtmsg = lambda msg: "Task engine %s: %s" % (self.name, msg)
        logger = root_logger.getChild(self.exec_agent)
        logger.info(fmtmsg("starting task processing"))
        self.aborted_tasks = []
        if self.graph is None:
            self.graph = self.model.get_graph(with_fix=True)
        self.num_tasks_to_perform = len(self.graph.nodes())
        for n in self.graph.nodes():
            self.graph.node[n]["ins_traversed"] = 0
        self.stop = False
        #start the workers
        logger.info(fmtmsg("Starting workers..."))
        for _ in range(self.num_threads):
            worker = threading.Thread(target=self.process_perform_task_queue)
            worker.start()
        logger.info(fmtmsg("...workers started"))
        #queue the initial tasks
        for task in (t for t in self.graph.nodes() if self.graph.in_degree(t) == 0):
            logger.debug(fmtmsg("Queueing up %s named %s id %s for performance" %
                         (task.__class__.__name__, task.name, str(task._id))))
            self.task_queue.put((self.graph, task))
        logger.info(fmtmsg("Initial tasks queued; waiting for completion"))
        #now wait to be signaled it finished
        while not self.stop:
            time.sleep(0.2)
        logger.info(fmtmsg("Agent task processing complete"))
        if self.aborted_tasks:
            raise self.exception_class("Task(s) aborted causing engine to abort; "
                                       "see the engine's aborted_tasks list for details")

    def perform_reverses(self, completion_record=None):
        """
        Traverses the graph in reverse to "unperform" the tasks.
        
        This method traverses the graph in reverse order so that dependents have
        a change to "reverse" whatever they did in task performance before the
        tasks they depend on do their own reversing work.
        
        Reversing can only be done of something already performed, including
        partial performance.
        
        @keyword completion_record: currently unused
        """
        del self.aborted_tasks[:]
        logger = root_logger.getChild(self.exec_agent)
        logger.info("Agent starting reverse processing of tasks")
        if self.graph is None:
            self.graph = self.model.get_graph(with_fix=True)
        self.num_tasks_to_perform = len(self.graph.nodes())
        for n in self.graph.nodes():
            self.graph.node[n]["outs_traversed"] = 0
        self.stop = False
        #start the workers
        logger.info("Starting workers...")
        for _ in range(self.num_threads):
            worker = threading.Thread(target=self.process_reverse_task_queue)
            worker.start()
        logger.info("...workers started")
        #queue the initial tasks
        for task in (t for t in self.graph.nodes() if self.graph.out_degree(t) == 0):
            logger.debug("Queueing up %s named %s id %s for reversing" %
                         (task.__class__.__name__, task.name, str(task._id)))
            self.task_queue.put((self.graph, task))
        logger.info("Initial tasks queued; waiting for completion")
        #now wait to be signaled it finished
        while not self.stop:
            time.sleep(0.2)
        logger.info("Agent task reversing complete")
        if self.aborted_tasks:
            raise self.exception_class("Tasks aborted causing reverse to abort; see the execution agent's aborted_tasks list for details")

