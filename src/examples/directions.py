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

This isn't guaranteed to work; it's a file of musings about how Actuator might
work. The actual operation and names may be somewhat different
'''
from actuator import *
from actuator.provisioners.example_components import Server, Queue

class System(InfraModel):
    compute_req_handler = Server("req_handler")
    workq = Queue("workq")
    grid = MultiComponent(Server("grid-Node"))
    

class GridComponent(Component):
    pass


class NS(NamespaceSpec):
    with_variables(Var("REQ_HOST", System.compute_req_handler.provisionedName),
                   Var("REQ_PORT", "3000"),
                   Var("WORK_Q", System.workq.provisionedName),
                   Var("WORK_Q_MGR", System.workq.qmanager),
                   Var("NODE_ID", "node-!{ID}"))
    grid = {}
    for i in range(5):
        name = "grid_%d" % i
        grid[name] = GridComponent(name, host_ref=System.grid[i]).add_variable(Var("ID", str(i)))
    with_components(**grid)
    del name, i, grid
    req_handler = Component("req_handler", host_ref=System.compute_req_handler)
    
    
class SystemConfig(ConfigSpec):
    #set up a template search path
    with_searchpath("some", "list", "of", "directory", "paths", "to", "find", "templates")
    target_dir = "/some/dir/path/where/software/will/be/set/up"
    
    #set-up tasks for the req handler
    req_run_dir = MakeDir(target_dir, component=NS.req_handler)
    req_handler_run_script = Template("fileName", target_dir, component=NS.req_handler)
    req_handler_setup_script = Template("filename", target_dir, component=NS.req_handler)
    move_req_assets = CopyAssets("someSource", target_dir, component=NS.req_handler)
    do_req_setup = ConfigJob(req_handler_setup_script, component=NS.req_handler)
    
    #setup tasks for all grid nodes
    grid_run_dir = MakeDir(target_dir, component_class=GridComponent)
    move_grid_assets = CopyAssets("someSource", target_dir, component_class=GridComponent)
    
    #simple edge and node notation
    with_dependencies(req_run_dir | TaskGroup(req_handler_run_script, move_req_assets,
                                              req_handler_setup_script),
                      TaskGroup(req_handler_setup_script, move_req_assets) | do_req_setup,
                      grid_run_dir | move_grid_assets)
    

class DynNS(NamespaceSpec):
    with_variables(Var("REQ_HOST", System.compute_req_handler.provisionedName),
                   Var("REQ_PORT", "3000"),
                   Var("WORK_Q", System.workq.provisionedName),
                   Var("WORK_Q_MGR", System.workq.qmanager),
                   Var("NODE_ID", "node-!{ID}"))
    MultiComponent(GridComponent("grid-node", host_ref=System.grid[ctxt.comp.name.val])
                        .add_variable(Var("ID", str(ctxt.comp.name.val))))
    req_handler = Component("req_handler", host_ref=System.compute_req_handler)

    
    
# class Integration1(CompositeSpec):
#     trade_cap_sys = SystemComponentWrapper(TradeCaptureInfra, TradeCaptureNamespace,
#                                            TradeCaptureConfig, TradeCaptureExec)
#     subledger_sys = SystemComponentWrapper(SubledgerInfra, SubledgerNamespace,
#                                            SubledgerConfig, SubledgerExec)
#     settlement_sys = SystemComponentWrapper(SettlementInfra, SettlementNamespace,
#                                             SettlementConfig, SettlementExec)
#     
#     cap_to_ledger_q = Queue("subledgerInput")
#     trade_cap_sys.downstream = cap_to_ledger_q
#     subledger_sys.upstream = cap_to_ledger_q
#     
#     subledger_to_settlement_q = Queue("settlementInput")
#     subledger_sys.downstream = subledger_to_settlement_q
#     settlement_sys.upstream = subledger_to_settlement_q
    
