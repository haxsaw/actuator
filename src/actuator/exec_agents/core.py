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
from IPython.lib.deepreload import add_submodule

'''
Created on Oct 20, 2014
'''
import Queue
import threading
import time
import sys
import traceback
import random

from actuator import ConfigModel, NamespaceModel, InfraModel, ActuatorException
from actuator.utils import LOG_INFO, root_logger


class ExecutionException(ActuatorException): pass


class ConfigRecord(object):
    def __init__(self):
        self.completed_tasks = []
        
    def record_completed_task(self, task):
        self.completed_tasks.append((task, time.ctime()))
        
    def is_completed(self, task):
        return task in self.completed_tasks


class ExecutionAgent(object):
    exception_class = ExecutionException
    exec_agent = "exec_agent"
    def __init__(self, exec_model_instance=None, config_model_instance=None,
                 namespace_model_instance=None, infra_model_instance=None,
                 num_threads=5, do_log=False, no_delay=False, log_level=LOG_INFO):
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
        self.aborted_tasks.append( (task, etype, value, tb) )
        
    def has_aborted_tasks(self):
        return len(self.aborted_tasks) > 0
    
    def get_aborted_tasks(self):
        """
        Returns a list of 4-tuples: the task that aborted, the exception type, the exception
        value, and the traceback.
        """
        return list(self.aborted_tasks)
        
    def perform_task(self, graph, task):
        #start with a small random wait to try to avoid too many things going to the
        #same machine at the same time
        add_suffix = lambda t, sfx: ("task %s named %s id %s->%s" %
                                     (t.__class__.__name__, t.name, t._id, sfx))
        logger = root_logger.getChild(self.exec_agent)
        logger.info(add_suffix(task, "processing started"))
        if not self.no_delay:
            logger.info(add_suffix(task, "start commencement delay"))
            time.sleep(random.uniform(0.2, 2.5))
            logger.info(add_suffix(task, "end commencement delay"))
        try_count = 0
        success = False
        while try_count < task.repeat_count and not success:
            try_count += 1
            if self.do_log:
                logfile=open("{}.{}-try{}.txt".format(task.name, str(task._id)[-4:], try_count), "w")
            else:
                logfile=None
            try:
                logger.info(add_suffix(task, "start performing task"))
                self._perform_task(task, logfile=logfile)
                logger.info(add_suffix(task, "task succeeded"))
                success = True
            except Exception, _:
                logger.warning(add_suffix(task, "task failed!"))
                msg = ">>>Task Exception for {}!".format(task.name)
                if logfile:
                    logfile.write("{}\n".format(msg))
                etype, value, tb = sys.exc_info()
                if try_count < task.repeat_count:
                    retry_wait = try_count * task.repeat_interval
                    logger.warning(add_suffix(task, "retrying after %d secs" % retry_wait))
                    msg = "Retrying {} again in {} secs".format(task.name, retry_wait)
                    if logfile:
                        logfile.write("{}\n".format(msg))
                        traceback.print_exception(etype, value, tb, file=logfile)
                    time.sleep(retry_wait)
                else:
                    logger.error(add_suffix(task, "max tries exceeded; task aborting"))
                    self.record_aborted_task(task, etype, value, tb)
                del etype, value, tb
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
        task.perform()
        
    def abort_process_tasks(self):
        self.stop = True
        
    def process_tasks(self):
        while not self.stop:
            try:
                graph, task = self.task_queue.get(block=True, timeout=0.2)
                if not self.stop:
                    self.perform_task(graph, task)
            except Queue.Empty, _:
                pass
        
    def perform_config(self, completion_record=None):
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
