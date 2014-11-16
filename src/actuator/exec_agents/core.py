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
Created on Oct 20, 2014
'''
import Queue
import threading
import time
import sys

import networkx as nx
from actuator import ConfigSpec, NamespaceSpec, InfraSpec, ActuatorException


class ExecutionException(ActuatorException): pass


class ConfigRecord(object):
    def __init__(self):
        self.completed_tasks = []
        
    def record_completed_task(self, task):
        self.completed_tasks.append((task, time.ctime()))
        
    def is_completed(self, task):
        return task in self.completed_tasks


class ExecutionAgent(object):
    def __init__(self, exec_model_instance=None, config_model_instance=None,
                 namespace_model_instance=None, infra_model_instance=None,
                 num_threads=5, do_log=False):
        #@TODO: need to add a test for the type of the exec_model_instance 
        self.exec_mi = exec_model_instance
        if config_model_instance is not None and not isinstance(config_model_instance, ConfigSpec):
            raise ExecutionException("config_model_instance argument isn't an instance of ConfigSpec")
        self.config_mi = config_model_instance
        
        if namespace_model_instance is not None and not isinstance(namespace_model_instance, NamespaceSpec):
            raise ExecutionException("namespace_model_instance isn't an instance of NamespaceSpec")
        self.namespace_mi = namespace_model_instance
        
        if infra_model_instance is not None and not isinstance(infra_model_instance, InfraSpec):
            raise ExecutionException("infra_model_instance isn't an instance of InfraSpec")
        self.infra_mi = infra_model_instance
        
        self.task_queue = Queue.Queue()
        self.node_lock = threading.Lock()
        self.stop = False
        self.num_tasks_to_perform = None
        self.config_record = None
        self.num_threads = num_threads
        self.do_log = do_log
        self.retry_wait = 20
        
    def perform_task(self, graph, task):
        try_count = 0
        success = False
        while try_count < task.repeat_count and not success:
            try_count += 1
            if self.do_log:
                logfile=open("{}-try{}.txt".format(task.name, try_count), "w")
            else:
                logfile=None
            try:
                self._perform_task(task, logfile=logfile)
                success = True
            except Exception, _:
                msg = ">>>Task Exception for {}!".format(task.name)
                if logfile:
                    logfile.write("{}\n".format(msg))
#                 print msg
                if try_count < task.repeat_count:
                    msg = "Retrying {} again in {} secs".format(task.name, self.retry_wait)
                    if logfile:
                        logfile.write("{}\n".format(msg))
#                     print msg
                    time.sleep(self.retry_wait)
            else:
                self.node_lock.acquire()
                self.num_tasks_to_perform -= 1
                if self.num_tasks_to_perform == 0:
                    self.stop = True
                else:
                    for successor in graph.successors_iter(task):
                        graph.node[successor]["ins_traversed"] += 1
                        if graph.in_degree(successor) == graph.node[successor]["ins_traversed"]:
                            self.task_queue.put((graph, successor))
                self.node_lock.release()
            if logfile:
                logfile.flush()
                logfile.close()
                del logfile
        if not success:
#             print "ABORTING"
            self.abort_process_tasks()
        
    def _perform_task(self, task):
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
        if self.namespace_mi and self.config_mi:
            self.config_mi.update_nexus(self.namespace_mi.nexus)
            nodes = self.config_mi.get_tasks()
            for n in nodes:
                n.fix_arguments()
            deps = self.config_mi.get_dependencies()
            graph = nx.DiGraph()
            graph.add_nodes_from(nodes)
            graph.add_edges_from( [d.edge() for d in deps] )
            self.num_tasks_to_perform = len(graph.nodes())
            for n in graph.nodes():
                graph.node[n]["ins_traversed"] = 0
            self.stop = False
            #start the workers
            for _ in range(self.num_threads):
                worker = threading.Thread(target=self.process_tasks)
                worker.start()
            #queue the initial tasks
            for task in (t for t in nodes if graph.in_degree(t) == 0):
                self.task_queue.put((graph, task))
            #now wait to be signaled it finished
            while not self.stop:
                time.sleep(0.2)
        else:
            raise ExecutionException("either namespace_model_instance or config_model_instance weren't specified")
