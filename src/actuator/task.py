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
try:
    import Queue
except ImportError:
    import queue as Queue
import random
import sys
import threading
import time
import traceback

from errator import narrate, get_narration, narrate_cm, reset_narration

from actuator import ActuatorException
from actuator.utils import root_logger, LOG_INFO, _Persistable, LOG_DEBUG, _Performable
from actuator.modeling import ModelComponent


class TaskException(ActuatorException):
    pass


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
    # internal
    def _or_result_class(self):
        return Orable
    
    def _and_result_class(self):
        return TaskGroup
    
    def __nonzero__(self):
        # everything needs to return False as otherwise expression
        # short-circuiting may cause some of the expression to get skipped
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
    
    
class Task(Orable, ModelComponent, _Performable):
    """
    Base class for all tasks
    
    This class provides the base protocol for all tasks; it deals with
    dependencies, cloning, embedded tasks, task performance and unwinding.
    """

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
        self.performance_status = self.UNSTARTED
        
    def _get_attrs_dict(self):
        d = super(Task, self)._get_attrs_dict()
        d.update({"repeat_til_success": self.repeat_til_success,
                  "repeat_count": self.repeat_count,
                  "repeat_interval": self.repeat_interval,
                  "performance_status": self.performance_status})
        return d

    def info(self):
        """
        Derived class should override; returns a string that should contain some info about
        the task within parenthesis ()
        :return: string containing parenthesized info about the task
        """
        return "()"
        
    def perform(self, engine):
        """
        Perform the task.

        Do no override this method! Instead, override
        L{Task._perform); this is the method for specializing functionality.

        @param engine: an instance of a L{TaskEngine}; this will get passed as the
            sole argument to self._perform()
        """
        if self.get_performance_status() == self.UNSTARTED:
            self._perform(engine)
            self.set_performance_status(self.PERFORMED)

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
        if self.get_performance_status() == self.PERFORMED:
            self._reverse(engine)
            self.set_performance_status(self.REVERSED)

    def _reverse(self, engine):
        """
        "undo" whatever was done in perform.

        Subclasses should override this method to provide a way to "undo" what
        was done in perform. If there is no need to "undo", this method may
        be ignored. The default implementation does nothing.
        """
        return
        
    def _embedded_exittask_attrnames(self):
        # internal
        return []
    
    def get_init_args(self):
        __doc__ = ModelComponent.__doc__
        return (self.name,), {"repeat_til_success": self._repeat_til_success,
                              "repeat_count": self._repeat_count,
                              "repeat_interval": self._repeat_interval
                              }
        
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
    
        
class TaskGroup(Orable, _Cloneable, _Unpackable, _Persistable):
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
        
    def _get_attrs_dict(self):
        d = super(TaskGroup, self)._get_attrs_dict()
        d['args'] = self.args
        return d
    
    def _find_persistables(self):
        for p in super(TaskGroup, self)._find_persistables():
            yield p
        for t in self.args:
            for p in t.find_persistables():
                yield p
        
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
    

class _Dependency(Orable, _Cloneable, _Unpackable, _Persistable):
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
        
    def __hash__(self):
        return (id(self.from_task) << 2) ^ id(self.to_task)
    
    def __eq__(self, other):
        return self.from_task is other.from_task and self.to_task is other.to_task
        
    def _get_attrs_dict(self):
        d = super(_Dependency, self)._get_attrs_dict()
        d["from_task"] = self.from_task
        d["to_task"] = self.to_task
        return d
    
    def _find_persistables(self):
        for p in super(_Dependency, self)._find_persistables():
            yield p
        for p in self.from_task.find_persistables():
            yield p
        for p in self.to_task.find_persistables():
            yield p
        
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
    def get_event_handler(self):
        """
        returns and instance of task.TaskEventHandler. derived class should override
        to return an actual instance
        :return: None; derived class should return an actual instance
        """
        return None

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
        deps, external_independents = self.get_dependencies()
        graph = nx.DiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from([d.edge() for d in deps])
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


class TaskExecControl(object):
    UNPERFORMED = 0
    PERFORMING = 1
    SUCCESS = 2
    FAIL_RETRY = 3
    FAIL_FINAL = 4
    ABORT = 5

    def __init__(self, task):
        assert isinstance(task, Task)
        self.status = self.UNPERFORMED
        self.fail_time = None
        self.try_count = 0
        self.task = task


class TaskEventHandler(object):
    """
    Base class for user-defined task event handling classes

    This class establishes the protocol for notifications to be delivered to external code of
    various events generated by the task engine and task performance. It provides a way for a
    derived class to know:

    - when a task engine is staring graph processing for a particular model instance
    - when a task starts
    - when a task ends
    - when a task fails and awaits retry
    - when a task permanently fails
    - when a task engine has completed processing for a model instance

    If an instance of a derived class is passed to the engine, the engine will call specific
    methods in specific circumstances to allow external code know about the progress being made
    in processing a task.

    The event handler can be used on single models, all models in an orchestration, or an
    orchestration itself. The event handler interface is meant to convey events from a single
    orchestration, not across multiple orchestrations. Hence, there should be an instance of
    this interface's implementation per orchestration.

    NOTE: derived class methods should be prepared to operate in a re-entrant fashion, as
    task operation may occur in different threads and hence it is possible for any method to
    be invoked from different threads.
    """

    # no __init__; supplied by derived class

    def orchestration_starting(self, orchestrator):
        """
        Called to signal that an overall orchestration is starting.
        :param orchestrator: an instance of L{actuator.ActuatorOrchestration}
        """
        pass

    def orchestration_finished(self, orchestration, result):
        """
        Called to signal that an overall orchestration has finished.
        :param orchestration:  an instance of L{actuator.ActuatorOrchestration}
        :param result: integer; one of the numeric status codes defined in L{actuator.ActuatorOrchestration}
        """
        pass

    def engine_starting(self, model, graph):
        """
        Called to signal that an engine is about to start processing tasks.

        This method must return in order for task processing to proceed.

        :param model: An instance of a task-processing model such as InfraModel or ConfigModel
        :param graph: a networkx DiGraph object that contains instances of various derived classes
            of Task that the engine will be performing. graph.nodes() returns the Task objects in
            the graphs, and graph.edges() returns an sequence of 2-tuples of Tasks that represent
            the from-to nodes in the directed graph
        """
        return

    def task_starting(self, model, tec):
        """
        Called to signal the engine is about to attempt to perform a task

        :param model: the model object that the task comes from; derived from both L{modeling.ModelBase}
            and L{task.GraphableModelMixin}
        :param tec: a L{TaskExecControl} object
        """
        return

    def task_finished(self, model, tec):
        """
        Called to signal that the engine has successfully performed the task

        :param model: the model object that the task comes from; derived from both L{modeling.ModelBase}
            and L{task.GraphableModelMixin}
        :param tec: a TaskExecControl object
        """
        return

    def task_failed(self, model, tec, errtext):
        """
        Called to signal that the engine fatally failed to successfully perfrom the task

        :param model: the model object that the task comes from; derived from both L{modeling.ModelBase}
            and L{task.GraphableModelMixin}
        :param tec: a TaskExecControl object
        :param errtext: a list of strings that describe the error that occurred
        """
        return

    def task_retry(self, model, tec, errtext):
        """
        Called to signal that the engine failed to perform a task but will retry it

        :param model: the model object that the task comes from; derived from both L{modeling.ModelBase}
            and L{task.GraphableModelMixin}
        :param tec: a TaskExecControl object
        :param errtext: a list of strings that describe the error that occurred
        """
        return

    def engine_finished(self, model):
        """
        Called to signal that the engine has completed the task graph

        :param model: an instance of a task-backed model such as InfraModel or ConfigModel
        """


class TaskEngine(object):
    """
    Base class for execution agents. The mechanics of actually executing a task
    are left to the derived class; this class takes care of all the business of
    managing the task dependency graph and deciding what tasks should be run
    when.
    """
    exception_class = TaskException
    exec_agent = "task_engine"

    def __init__(self, name, model, num_threads=5, do_log=False, no_delay=False, log_level=LOG_INFO):
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
            raise TaskException("TaskEngine was not passed a kind of GraphableModelMixin; %s" % str(model))

        self.log_level = log_level
        self.model = model
        self.name = name
        self.num_threads = num_threads
        self.node_lock = threading.Lock()
        self.config_record = None
        self.do_log = do_log
        self.no_delay = no_delay
        self.graph = None
        
        self.task_queue = Queue.Queue()
        self.stop = False
        self.aborted_tasks = []
        self.num_tasks_to_perform = None
        self.threads = set()
        self._reset()
        self.logger = root_logger.getChild(self._logger_name())
        self.logger.setLevel(self.log_level)
        self.event_handler = model.get_event_handler()

    def _logger_name(self):
        return "TaskEngine"
        
    def _reset(self):
        # used to reset the processing state of the system so resumes/reverses
        # don't get weird results
        while not self.task_queue.empty():
            try:
                self.task_queue.get(False)
            except Queue.Empty as _:
                break
        self.aborted_tasks = []
        self.num_tasks_to_perform = None
        # just to ensure no threads continue to work while we reset
        self.stop = True
        self._reap_threads()
        self.stop = False
        
    def _reap_threads(self):
        for t in list(self.threads):
            t.join()
            self.threads.remove(t)
        
    def record_aborted_task(self, task, etype, value, tb, story):
        """
        Internal; used by a worker thread to report that it is giving up on
        performing a task.
        
        @param task: The task that is aborting
        @param etype: The aborting exception type
        @param value: The exception value
        @param tb: The exception traceback object, as returned by sys.exc_info()
        @param story: a list of strings, usually from from get_narration(), that gives the human readable
            version of the exception
        """
        self.aborted_tasks.append((task, etype, value, tb, story))
        
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
        path = ".".join(ref.get_path()) if ref is not None else "-system-"

        def fmtmsg(msg):
            return "|".join([task.__class__.__name__, task.name, task.info(), path,
                             str(task._id), msg])
        return fmtmsg
        
    def _reverse_task(self, task, logfile=None):
        # Actually reverse the task; the default asks the task to reverse itself
        task.reverse(self)

    @narrate(lambda s, g, t: "...which has caused the base task engine to start reversing task {}".format(t.task.name))
    def reverse_task(self, graph, tec):
        """
        Internal, used to reverse a task in graph. Derived classes implement
        _reverse_task() to supply the actual mechanics for the underlying
        task execution system.

        @param graph: an NetworkX DiGraph; needed to find the next tasks
            to queue when the current one is done
        @param tec: The TaskExecControl object containing the task to perform

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
        self._task_runner(tec, "reverse", Task.REVERSED)

    def _perform_task(self, task, logfile=None):
        # Actually do the task; the default asks the task to perform itself.
        task.perform(self)

    @narrate(lambda s, g, t: "...which caused the base task engine to begin performing task {}".format(t.task.name))
    def perform_task(self, _, tec):
        """
        Internal, used to perform a task in graph. Derived classes implement
        _perform_task() to supply the actual mechanics of for the underlying
        task execution system.
        
        @param _: an NetworkX DiGraph; needed to find the next tasks
            to queue when the current one is done
        @param tec: The L{TaskExecControl} object wrapping the task to perform
        
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
        self._task_runner(tec, "perform", Task.PERFORMED)

    def _task_runner(self, tec, direction, success_status):
        assert isinstance(tec, TaskExecControl)
        task = tec.task
        fmtmsg = self.make_format_func(task)
        meth = getattr(self, "".join(["_", direction, "_task"]))
            
        logger = root_logger.getChild(self.exec_agent)
        logger.info(fmtmsg("processing started"))
        if not self.no_delay:
            time.sleep(random.uniform(0.2, 1.5))
        if not task.fixed:
            task.fix_arguments()

        if tec.status == TaskExecControl.FAIL_RETRY:
            delay = tec.try_count * task.repeat_interval
            now = time.time()
            wait_until = (tec.try_count * task.repeat_interval) + tec.fail_time
            logger.warning(fmtmsg("Completing {} sec delay before retrying task (now:{}, until:{})"
                                  .format(delay, now, wait_until)))
            while now < wait_until and not self.stop:
                time.sleep(0.2)
                now = time.time()
            if self.stop:
                tec.status = TaskExecControl.ABORT
                return
            logger.warning(fmtmsg("Completed waiting; retrying"))

        tec.try_count += 1
        if self.do_log:
            logfile = open("{}.{}-try{}.txt".format(task.name, str(task._id)[-4:],
                                                    tec.try_count), "w")
        else:
            logfile = None
        try:
            logger.info(fmtmsg("start %s-ing task" % direction))
            with narrate_cm(lambda n, d: "-which resulted in the task engine performing task {} in the {} direction"
                            .format(n, d), task.name, direction):
                tec.status = TaskExecControl.PERFORMING
                if self.event_handler:
                    try:
                        self.event_handler.task_starting(self.model, tec)
                    except Exception as e:
                        logger.error("event_handler.task_starting method raised %s; "
                                     "continuing task processing" % str(e))
                meth(task, logfile=logfile)

            task.set_performance_status(success_status)
            tec.status = TaskExecControl.SUCCESS
            if self.event_handler:
                try:
                    self.event_handler.task_finished(self.model, tec)
                except Exception as e:
                    logger.error("event_handler.task_finished method raised %s: continuing task processing" % str(e))
            logger.info(fmtmsg("task successfully %s-ed" % direction))
        except Exception as e:
            tec.fail_time = time.time()
            logger.warning(fmtmsg("task %s failed" % direction))
            msg = ">>>Task {} Exception for {}!".format(direction, task.name)
            if logfile:
                logfile.write("{}\n".format(msg))
            tb = sys.exc_info()[2]
            try:
                story = get_narration(from_here=True)
            except Exception as x:
                story = ["FETCHING STORY FAILED WITH: %s" % str(x)]
            reset_narration(from_here=True)
            if tec.try_count < task.repeat_count:
                tec.status = TaskExecControl.FAIL_RETRY
                retry_wait = tec.try_count * task.repeat_interval
                logger.warning(fmtmsg("will retry after a %d sec delay" % retry_wait))
                msg = "Retrying {} again after a {} sec delay".format(task.name, retry_wait)
                if logfile:
                    logfile.write("{}\n".format(msg))
                    traceback.print_exception(type(e), e, tb, file=logfile)
                if self.event_handler:
                    try:
                        self.event_handler.task_retry(self.model, tec, story)
                    except Exception as e:
                        logger.error("event_handler.task_retry raised %s; continuing task processing" % str(e))
            else:
                tec.status = TaskExecControl.FAIL_FINAL
                logger.error(fmtmsg("max tries exceeded; task aborting"))
                logger.error("The failure story is: {}".format("\n".join(story)))
                self.record_aborted_task(task, type(e), e, tb, story)
                if self.event_handler:
                    try:
                        self.event_handler.task_failed(self.model, tec, story)
                    except Exception as e:
                        logger.error("event_handler.task_failed raised %s; continuing task processing" % str(e))
                self.abort_process_tasks()
            del tb
            try:
                sys.exc_clear()
            except Exception as _:
                pass

        if logfile:
            logfile.flush()
            logfile.close()

    def abort_process_tasks(self):
        """
        The the agent to abort performing any further tasks.
        """
        self.stop = True

    @narrate(lambda s: "...which started the task engine {} to "
                       "process the perform queue".format(s.name))
    def process_perform_task_queue(self):
        """
        Tell the agent to start performing tasks; results in calls to
        self.perform_task()
        """
        logger = root_logger.getChild("%s.process_perform_tasks" % self.exec_agent)
        while not self.stop:
            try:
                graph, tec = self.task_queue.get(block=True, timeout=0.2)
                assert isinstance(tec, TaskExecControl)
                task = tec.task
                if not self.stop:
                    self.perform_task(graph, tec)
                    if tec.status == TaskExecControl.FAIL_RETRY:
                        # this means the task failed but hasn't reached its retry limit yet;
                        # we'll push the task back onto the task queue so it gets a chance
                        # to be performed again, as it may very well have an implicit dependency
                        # on something else
                        self.task_queue.put((graph, tec))
                    elif task.get_performance_status() == task.PERFORMED:
                        with self.node_lock:
                            self.num_tasks_to_perform -= 1
                            logger.info("Remaining tasks to perform: %s" % self.num_tasks_to_perform)
                            if self.num_tasks_to_perform == 0:
                                self.stop = True
                            else:
                                for successor in (graph.successors_iter(task)  # for networkx 1/2 compatibility
                                                  if hasattr(graph, "successors_iter")
                                                  else graph.successors(task)):
                                    graph.node[successor]["ins_traversed"] += 1
                                    if graph.in_degree(successor) == graph.node[successor]["ins_traversed"]:
                                        logger.debug("queueing up %s for performance" % successor.name)
                                        self.task_queue.put((graph, TaskExecControl(successor)))
            except Queue.Empty as _:
                pass

    @narrate(lambda s: "...and then the task engine {} began to process the "
                       "reverse task queue".format(s.name))
    def process_reverse_task_queue(self):
        """
        Tell the agent to start reverse processing tasks; re
        """
        logger = root_logger.getChild("%s.process_reverse_tasks" % self.exec_agent)
        while not self.stop:
            try:
                graph, tec = self.task_queue.get(block=True, timeout=0.2)
                assert isinstance(tec, TaskExecControl)
                task = tec.task
                if not self.stop:
                    self.reverse_task(graph, tec)
                    if tec.status == TaskExecControl.FAIL_RETRY:
                        # this means the task failed but hasn't reached its retry limit yet;
                        # we'll push the task back onto the task queue so it get's a chance
                        # to be performed again, as it may very well have an implicit dependency
                        # on something else
                        self.task_queue.put((graph, tec))
                    elif task.get_performance_status() == task.REVERSED:
                        with self.node_lock:
                            self.num_tasks_to_perform -= 1
                            logger.debug("Remaining tasks to reverse: %s" %
                                         self.num_tasks_to_perform)
                            if self.num_tasks_to_perform == 0:
                                self.stop = True
                            else:
                                for predecessor in (graph.predecessors_iter(task)  # networkx 1/2 compatibility
                                                    if hasattr(graph, "predecessors_iter")
                                                    else graph.predecessors(task)):
                                    graph.node[predecessor]["outs_traversed"] += 1
                                    if graph.out_degree(predecessor) == graph.node[predecessor]["outs_traversed"]:
                                        logger.debug("queuing up %s for performance" %
                                                     predecessor.name)
                                        self.task_queue.put((graph, TaskExecControl(predecessor)))
            except Queue.Empty as _:
                pass

    @narrate(lambda s, **kw: "...which started the base task engine {} in performing "
                             "tasks".format(s.name))
    def perform_tasks(self, completion_record=None):
        self._reset()

        def fmtmsg(msg):
            return "Task engine %s: %s" % (self.name, msg)

        logger = root_logger.getChild(self.exec_agent)
        logger.info(fmtmsg("starting task processing"))
        if self.graph is None:
            self.graph = self.model.get_graph(with_fix=True)

        if self.event_handler:
            try:
                self.event_handler.engine_starting(self.model, self.graph)
            except Exception as e:
                logger.error("event_handler raised an exception in engine_starting: %s. Processing continuing" % str(e))

        self.num_tasks_to_perform = len(self.graph.nodes())
        for n in self.graph.nodes():
            self.graph.node[n]["ins_traversed"] = 0
        # start the workers
        logger.info(fmtmsg("Starting workers..."))
        for _ in range(self.num_threads):
            worker = threading.Thread(target=self.process_perform_task_queue)
            worker.start()
            self.threads.add(worker)
        logger.info(fmtmsg("...workers started"))
        if len(self.graph.nodes()) > 0:
            # queue the initial tasks
            for task in (t for t in self.graph.nodes() if self.graph.in_degree(t) == 0):
                logger.debug(fmtmsg("Queueing up %s named %s id %s for performance" %
                             (task.__class__.__name__, task.name, str(task._id))))
                tec = TaskExecControl(task)
                self.task_queue.put((self.graph, tec))
            logger.info(fmtmsg("Initial tasks queued; waiting for completion"))
        else:
            logger.info("No tasks to perform; completed processing")
            self.stop = True
        # now wait to be signaled it finished
        while not self.stop:
            time.sleep(0.2)
        logger.info(fmtmsg("Reaping threads; this may take a minute"))
        self._reap_threads()
        logger.info(fmtmsg("Agent task processing complete"))
        if self.event_handler:
            try:
                self.event_handler.engine_finished(self.model)
            except Exception as _:
                pass
        if self.aborted_tasks:
            raise self.exception_class("Task(s) aborted causing engine to abort; "
                                       "see the engine's aborted_tasks list for details")

    @narrate(lambda s, **kw: "...causing the task engine {} to start "
                             "reverse processing the tasks".format(s.name))
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
        self._reset()
        fmtmsg = lambda msg: "Task engine %s: %s" % (self.name, msg)
        logger = root_logger.getChild(self.exec_agent)
        logger.info(fmtmsg("Agent starting reverse processing of tasks"))
        if self.graph is None:
            self.graph = self.model.get_graph(with_fix=True)

        if self.event_handler:
            try:
                self.event_handler.engine_starting(self.model, self.graph)
            except Exception as e:
                logger.error("event_handler raised an exception in engine_starting: %s. Processing continuing" % str(e))

        self.num_tasks_to_perform = len(self.graph.nodes())
        for n in self.graph.nodes():
            self.graph.node[n]["outs_traversed"] = 0
        # start the workers
        logger.info(fmtmsg("Starting workers..."))
        for _ in range(self.num_threads):
            worker = threading.Thread(target=self.process_reverse_task_queue)
            worker.start()
            self.threads.add(worker)
        logger.info(fmtmsg("...workers started"))
        if len(self.graph.nodes()) > 0:
            # queue the initial tasks
            for task in (t for t in self.graph.nodes() if self.graph.out_degree(t) == 0):
                logger.debug(fmtmsg("Queueing up %s named %s id %s for reversing" %
                             (task.__class__.__name__, task.name, str(task._id))))
                self.task_queue.put((self.graph, TaskExecControl(task)))
            logger.info(fmtmsg("Initial tasks queued; waiting for completion"))
        else:
            logger.info("No tasks to reverse; completed processing")
            self.stop = True
        # now wait to be signaled it finished
        while not self.stop:
            time.sleep(0.2)
        logger.info(fmtmsg("Reaping threads; this may take a minute"))
        self._reap_threads()
        logger.info(fmtmsg("Agent task reversing complete"))
        if self.aborted_tasks:
            raise self.exception_class("Tasks aborted causing reverse to abort; see the execution agent's"
                                       " aborted_tasks list for details")
