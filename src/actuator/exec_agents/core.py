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
Base classes for bindings to execution agents.
'''
import Queue
import threading
import time
import sys
import traceback
import random

from actuator import ConfigModel, NamespaceModel, InfraModel, ActuatorException
from actuator.utils import LOG_INFO, root_logger
from actuator.modeling import AbstractModelReference


class ExecutionException(ActuatorException):
    def __init__(self, message=None, response="None available"):
        super(ExecutionException, self).__init__(message)
        self.response = response


class ConfigRecord(object):
    """
    Returned by the execution agent; a record of the tasks that have been
    performed as part of the orchestration.
    """
    def __init__(self):
        """
        Sets up a record container for tasks as they complete. The attribute
        completed_tasks is a public list of the tasks that have successfully
        completed during orchestration. It is a list of 2-tuples,
        (task, completion time.ctime).
        """
        self.completed_tasks = []
        
    def record_completed_task(self, task):
        """
        Captures the completion of a single task. Adds the 2-tuple
        (task, time.ctime()) to the completed_tasks list.
        """
        self.completed_tasks.append((task, time.ctime()))
        
    def is_completed(self, task):
        return task in set([r[0] for r in self.completed_tasks])


class ExecutionAgent(object):
    """
    Base class for execution agents. The mechanics of actually executing a task
    are left to the derived class; this class takes care of all the business of
    managing the task dependency graph and deciding what tasks should be run
    when.
    """
    exception_class = ExecutionException
    exec_agent = "exec_agent"
    def __init__(self, exec_model_instance=None, config_model_instance=None,
                 namespace_model_instance=None, infra_model_instance=None,
                 num_threads=5, do_log=False, no_delay=False, log_level=LOG_INFO):
        """
        Make a new ExecutionAgent
        
        @keyword exec_model_instance: Reserved for latter use
        @keyword config_model_instance: an instance of a derived class of
            ConfigModel
        @keyword namespace_model_instance: an instance of a derived class of
            NamespaceModel
        @keyword infra_model_instance: UNUSED; an instance of a derived class of
            InfraModel
        @keyword num_threads: Integer, default 5. The number of worker threads
            to spin up to perform tasks.
        @keyword do_log: boolean, default False. If True, creates a log file
            that contains more detailed logs of the activities carried out.
            Independent of log_level (see below).
        @keyword no_delay: booleand, default False. The default causes a short
            pause of up to 2.5 seconds to be taken before a task is started.
            This keeps a single host from being bombarded with too many ssh
            requests at the same time in the case where a number of different
            tasks can all start in parallel on the same Role's host.
        @keyword log_level: Any of the symbolic log levels in the actuator root
            package, LOG_CRIT, LOG_DEBUG, LOG_ERROR, LOG_INFO, or LOG_WARN
        """
        #@TODO: need to add a test for the type of the exec_model_instance 
        self.exec_mi = exec_model_instance
        if config_model_instance is not None and not isinstance(config_model_instance, ConfigModel):
            raise ExecutionException("config_model_instance argument isn't an instance of ConfigModel")
        self.config_mi = config_model_instance
        
        if namespace_model_instance is not None and not isinstance(namespace_model_instance, NamespaceModel):
            raise ExecutionException("namespace_model_instance isn't an instance of NamespaceModel")
        self.namespace_mi = namespace_model_instance
        
        if self.config_mi is not None:
            self.config_mi.set_namespace(self.namespace_mi)
        
        if infra_model_instance is not None and not isinstance(infra_model_instance, InfraModel):
            raise ExecutionException("infra_model_instance isn't an instance of InfraModel")
        self.infra_mi = infra_model_instance
        
        root_logger.setLevel(log_level)
        self.task_queue = Queue.Queue()
        self.node_lock = threading.Lock()
        self.stop = False
        self.aborted_tasks = []
        self.num_tasks_to_perform = None
        self.config_record = None
        self.num_threads = num_threads
        self.do_log = do_log
        self.no_delay = no_delay
        
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
        
    def perform_task(self, graph, task):
        """
        Internal, used to perform a task in graph. Derived classes implement
        _perform_task() to supply the actual mechanics of for the underlying
        task execution system.
        
        @param graph: an NetworkX DiGraph; needed to find the next tasks
            to queue when the current one is done
        @param task: The actual task to perform
        """
        add_suffix = lambda t, sfx: ("task %s named %s id %s->%s" %
                                     (t.__class__.__name__, t.name, t._id, sfx))
        logger = root_logger.getChild(self.exec_agent)
        try:
            role_name = task.get_task_role().name
            if isinstance(role_name, AbstractModelReference):
                role_name = role_name.value()
            role_id = task.get_task_role()._id
        except Exception, _:
            role_name = "NO_ROLE"
            role_id = ""
        logger.info(add_suffix(task, "processing started for role %s(%s)"
                               % (role_name, role_id)))
        if not self.no_delay:
            time.sleep(random.uniform(0.2, 2.5))
        try_count = 0
        success = False
        while try_count < task.repeat_count and not success:
            try_count += 1
            if self.do_log:
                logfile=open("{}.{}-try{}.txt".format(task.name, str(task._id)[-4:], try_count), "w")
            else:
                logfile=None
            try:
                logger.info(add_suffix(task, "start performing task for role %s(%s)"
                                       % (role_name, role_id)))
                self._perform_task(task, logfile=logfile)
                logger.info(add_suffix(task, "task succeeded for role %s(%s)"
                                       % (role_name, role_id)))
                success = True
            except Exception, e:
                logger.warning(add_suffix(task, "task failed for role %s(%s)"
                                          % (role_name, role_id)))
                msg = ">>>Task Exception for {}!".format(task.name)
                if logfile:
                    logfile.write("{}\n".format(msg))
                tb = sys.exc_info()[2]
                if try_count < task.repeat_count:
                    retry_wait = try_count * task.repeat_interval
                    logger.warning(add_suffix(task, "retrying after %d secs" % retry_wait))
                    msg = "Retrying {} again in {} secs".format(task.name, retry_wait)
                    if logfile:
                        logfile.write("{}\n".format(msg))
                        traceback.print_exception(type(e), e, tb, file=logfile)
                    time.sleep(retry_wait)
                else:
                    logger.error(add_suffix(task, "max tries exceeded; task aborting"))
                    self.record_aborted_task(task, type(e), e, tb)
                del tb
                sys.exc_clear()
            else:
                self.node_lock.acquire()
                self.num_tasks_to_perform -= 1
                if self.num_tasks_to_perform == 0:
                    self.stop = True
                else:
                    for successor in graph.successors_iter(task):
                        graph.node[successor]["ins_traversed"] += 1
                        if graph.in_degree(successor) == graph.node[successor]["ins_traversed"]:
                            logger.debug(add_suffix(successor, "queueing up for performance"))
                            self.task_queue.put((graph, successor))
                self.node_lock.release()
            if logfile:
                logfile.flush()
                logfile.close()
                del logfile
        if not success:
#             print "ABORTING"
            self.abort_process_tasks()
        
    def _perform_task(self, task, logfile=None):
        """
        Actually do the task; the default asks the task to perform itself,
        which usually means that it does nothing.
        """
        task.perform()
        
    def abort_process_tasks(self):
        """
        The the agent to abort performing any further tasks.
        """
        self.stop = True
        
    def process_tasks(self):
        """
        Tell the agent to start performing tasks; results in calls to
        self.perform_task()
        """
        while not self.stop:
            try:
                graph, task = self.task_queue.get(block=True, timeout=0.2)
                if not self.stop:
                    self.perform_task(graph, task)
            except Queue.Empty, _:
                pass
        
    def perform_config(self, completion_record=None):
        """
        Start the agent working on the configuration tasks. This is the method
        the outside world calls when it wants the agent to start the config
        processing process.
        
        @keyword completion_record: currently unused
        """
        logger = root_logger.getChild(self.exec_agent)
        logger.info("Agent starting task processing")
        if self.namespace_mi and self.config_mi:
            self.config_mi.update_nexus(self.namespace_mi.nexus)
            graph = self.config_mi.get_graph(with_fix=True)
            self.num_tasks_to_perform = len(graph.nodes())
            for n in graph.nodes():
                graph.node[n]["ins_traversed"] = 0
                n.fix_arguments()
            self.stop = False
            #start the workers
            logger.info("Starting workers...")
            for _ in range(self.num_threads):
                worker = threading.Thread(target=self.process_tasks)
                worker.start()
            logger.info("...workers started")
            #queue the initial tasks
            for task in (t for t in graph.nodes() if graph.in_degree(t) == 0):
                logger.debug("Queueing up %s named %s id %s for performance" %
                             (task.__class__.__name__, task.name, str(task._id)))
                self.task_queue.put((graph, task))
            logger.info("Initial tasks queued; waiting for completion")
            #now wait to be signaled it finished
            while not self.stop:
                time.sleep(0.2)
            logger.info("Agent task processing complete")
            if self.aborted_tasks:
                raise self.exception_class("Tasks aborted causing config to abort; see the execution agent's aborted_tasks list for details")
        else:
            raise ExecutionException("either namespace_model_instance or config_model_instance weren't specified")
