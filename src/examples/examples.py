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

@author: tom
'''
from actuator import (InfraSpec, with_variables, Var, Component, NamespaceSpec,
                      MultiComponent, with_components, MultiComponentGroup)
from actuator.provisioners.example_components import Database, Server, Queue

class System1(InfraSpec):
    web_server = Server("webServer", mem="16GB")
    database = Database("db")
    app_server = Server("appServer")
    req_queue = Queue("req_q")
    reply_queue = Queue("reply_q")
    

class NS1(NamespaceSpec):
    with_variables(Var("WEB_SRVR_HOST", System1.web_server.provisionedName),
                   Var("WEB_SRVR_PORT", "8080"),
                   Var("DATABASE_HOST", System1.database.provisionedName),
                   Var("APP_SRVR_HOST", System1.app_server.provisionedName),
                   Var("APP_SRVR_PORT", "4000"),
                   Var("REQ_Q", System1.req_queue.provisionedName),
                   Var("REQ_Q_MGR", System1.reply_queue.qmanager),
                   Var("REP_Q", System1.reply_queue.provisionedName),
                   Var("REP_Q_MGR", System1.reply_queue.qmanager)
                   )
    app_server = Component("app_server", host_ref=System1.app_server)
    web_server = Component("web_server", host_ref=System1.web_server)
    
#-------------------------------------------------------------------------

class System2(InfraSpec):
    compute_req_handler = Server("req_handler")
    workq = Queue("workq")
    grid = MultiComponent(Server("grid-Node"))
    
    
class NS2(NamespaceSpec):
    with_variables(Var("REQ_HOST", System2.compute_req_handler.provisionedName),
                   Var("REQ_PORT", "3000"),
                   Var("WORK_Q", System2.workq.provisionedName),
                   Var("WORK_Q_MGR", System2.workq.qmanager),
                   Var("NODE_ID", "node-!ID!"))
    grid = {}
    for i in range(5):
        name = "grid_%d" % i
        grid[name] = Component(name, host_ref=System2.grid[i]).add_variable(Var("ID", str(i)))
    with_components(**grid)
    del name, i, grid
    req_handler = Component("req_handler", host_ref=System2.compute_req_handler)
    
    
def NS2_factory(grid_size=5):
    class NS2(NamespaceSpec):
        with_variables(Var("REQ_HOST", System2.compute_req_handler.provisionedName),
                       Var("REQ_PORT", "3000"),
                       Var("WORK_Q", System2.workq.provisionedName),
                       Var("WORK_Q_MGR", System2.workq.qmanager),
                       Var("NODE_ID", "node-!ID!"))
        grid = {}
        for i in range(grid_size):
            name = "grid_%d" % i
            grid[name] = Component(name, host_ref=System2.grid[i]).add_variable(Var("ID", str(i)))
        with_components(**grid)
        del name, i, grid
        req_handler = Component("req_handler", host_ref=System2.compute_req_handler)
    inst = NS2()
    return NS2, inst

#------------------------------------------------------------------------------------

class System3(InfraSpec):
    req_handler = Server("req_handler")
    database = Database("db")
    grid = MultiComponentGroup("grid",
                               req_q=Queue("req_q"), compute=Server("compute"),
                               reply_q=Queue("reply_q"))

