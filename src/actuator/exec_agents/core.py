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
                 num_threads=5):
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
        self.completion_lock = threading.Lock()
        self.stop = False
        self.num_tasks_to_perform = None
        self.config_record = None
        self.num_threads = num_threads
        self.error_details = None
        
    def perform_task(self, graph, task):
        try:
            self._perform_task(task)
        except Exception, _:
            self.error_details = sys.exc_info()
            self.abort_process_tasks()
        else:
            
            self.node_lock.acquire()
            self.num_tasks_to_perform -= 1
            if self.num_tasks_to_perform == 0:
                self.stop = True
                self.completion_lock.release()
            else:
                for successor in graph.successors_iter(task):
                    graph.node[successor]["ins_traversed"] += 1
                    if graph.in_degree(successor) == graph.node[successor]["ins_traversed"]:
                        self.task_queue.put((graph, successor))
            self.node_lock.release()
        
    def _perform_task(self, task):
        task.perform()
        
    def abort_process_tasks(self):
        self.stop = True
        self.completion_lock.release()
        
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
            self.config_mi.set_namespace(self.namespace_mi)
            nodes = self.config_mi.get_tasks()
            self.num_tasks_to_perform = len(nodes)
            deps = self.config_mi.get_dependencies()
            graph = nx.DiGraph()
            graph.add_nodes_from(nodes, ins_traversed=0)
            graph.add_edges_from( [d.edge() for d in deps] )
            self.stop = False
            self.error_details = None
            #start the workers
            for _ in range(self.num_threads):
                worker = threading.Thread(target=self.process_tasks)
                worker.start()
            #queue the initial tasks
            for task in (t for t in nodes if graph.in_degree(t) == 0):
                self.task_queue.put((graph, task))
            self.completion_lock.acquire()
            #now wait to be signaled it finished
            self.completion_lock.acquire()
            if self.error_details:
                raise self.error_details[1], None, self.error_details[2]
        else:
            raise ExecutionException("either namespace_model_instance or config_model_instance weren't specified")
