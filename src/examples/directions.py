'''
Created on 7 Sep 2014

@author: tom
'''
from actuator import *
from actuator.provisioners.example_components import Server, Queue

class System2(InfraSpec):
    compute_req_handler = Server("req_handler")
    workq = Queue("workq")
    grid = MultiComponent(Server("grid-Node"))
    

class GridComponent(Component):
    pass


class NS2(NamespaceSpec):
    with_variables(Var("REQ_HOST", System2.compute_req_handler.provisionedName),
                   Var("REQ_PORT", "3000"),
                   Var("WORK_Q", System2.workq.provisionedName),
                   Var("WORK_Q_MGR", System2.workq.qmanager),
                   Var("NODE_ID", "node-!ID!"))
    grid = {}
    for i in range(5):
        name = "grid_%d" % i
        grid[name] = GridComponent(name, host_ref=System2.grid[i]).add_variable(Var("ID", str(i)))
    with_components(**grid)
    del name, i, grid
    req_handler = Component("req_handler", host_ref=System2.compute_req_handler)
    
    
class Sys2bConfig(ConfigSpec):
    #set up a template search path
    with_searchpath("some", "list", "of", "directory", "paths", "to", "find", "templates")
    target_dir = "/some/dir/path/where/software/will/be/set/up"
    
    req_run_dir = MakeDir(target_dir, component=NS2.req_handler)
    req_handler_run_script = Template("fileName", target_dir, component=NS2.req_handler)
    req_handler_setup_script = Template("filename", target_dir, component=NS2.req_handler)
    move_req_assets = CopyAssets("someSource", target_dir, component=NS2.req_handler)
    do_req_setup = ConfigJob(req_handler_setup_script, component=NS2.req_handler)
    grid_run_dir = MakeDir(target_dir, component_class=GridComponent)
    move_grid_assets = CopyAssets("someSource", target_dir, component_class=GridComponent)
    
    #simple edge and node notation
    with_dependencies( req_run_dir << req_handler_run_script,
                       req_run_dir << move_req_assets,
                       req_run_dir << req_handler_setup_script,
                       req_handler_setup_script << do_req_setup,
                       move_req_assets << do_req_setup,
                       grid_run_dir << move_grid_assets,
                       )
    #either proceeds or depends on notation
    req_run_dir.preceeds(req_handler_run_script,
                         move_req_assets,
                         req_handler_setup_script)
    do_req_setup.depends_on(req_handler_setup_script,
                            move_req_assets)
    grid_run_dir.preceeds(move_grid_assets)
    
    
class Sys2aConfig(ConfigSpec):
    #set up a template search path
    with_searchpath("some", "list", "of", "directory", "paths", "to", "find", "templates")
    target_dir = "/some/dir/path/where/software/will/be/set/up"
    
    req_run_dir = MakeDir(target_dir, component=NS2.req_handler)
    req_handler_run_script = Template("fileName", target_dir, component=NS2.req_handler)
    req_handler_setup_script = Template("filename", target_dir, component=NS2.req_handler)
    move_req_assets = CopyAssets("someSource", target_dir, component=NS2.req_handler)
    do_req_setup = ConfigJob(req_handler_setup_script, component=NS2.req_handler)
    grid_run_dir = MakeDir(target_dir, any_instance_of=System2.grid)
    move_grid_assets = CopyAssets("someSource", target_dir, any_instance_of=System2.grid)
    
    
    with_dependencies( req_run_dir << req_handler_run_script,
                       req_run_dir << move_req_assets,
                       req_run_dir << req_handler_setup_script,
                       req_handler_setup_script << do_req_setup,
                       move_req_assets << do_req_setup,
                       grid_run_dir << move_grid_assets,
                       )
    
    
class Integration1(CompositeSpec):
    trade_cap_sys = SystemComponentWrapper(TradeCaptureInfra, TradeCaptureNamespace,
                                           TradeCaptureConfig, TradeCaptureExec)
    subledger_sys = SystemComponentWrapper(SubledgerInfra, SubledgerNamespace,
                                           SubledgerConfig, SubledgerExec)
    settlement_sys = SystemComponentWrapper(SettlementInfra, SettlementNamespace,
                                            SettlementConfig, SettlementExec)
    
    cap_to_ledger_q = Queue("subledgerInput")
    trade_cap_sys.downstream = cap_to_ledger_q
    subledger_sys.upstream = cap_to_ledger_q
    
    subledger_to_settlement_q = Queue("settlementInput")
    subledger_sys.downstream = subledger_to_settlement_q
    settlement_sys.upstream = subledger_to_settlement_q
    