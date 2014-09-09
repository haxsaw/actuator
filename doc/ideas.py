class MySystemIndentities(IdentSpec):
    my_system_id = SystemIdent("MySystem", version="1.5", external_keys={})
    
    req_queue_writer = SystemAgent("wotzis")
    req_queue_reader = SystemAgent('summat')
    compute = SystemAgent("compute")
    

class MySystemInfra(InfraSpec):
    comp_grid = VariableInfra(Server(cores=2, gmem=4, niface=1))
    qmgr = QueueMgr()
    #should entitlement be factored out separately into another model? useful to config, infra, cond, exec
    read_ent = Entitlement(kind="read", sysid="summat")
    write_ent = Entitlement(kind="write", sysid="wotzis")
    req_handler_spec = VariableInfraGroup(req_handler=Server(cores=3, gmem=4, niface=2),
                                          req_queue=Queue(qmgr=qmgr, max_msg_mb=1, read=read_ent, write=write_ent))
    f5 = Demultiplexor("wibble", port=80, dest=req_handler_spec.req_queue)
    
    
class MyNamespace(Namespace):
    globals = GlobalVariables(Variable("QMGR_NAME", MySystemInfra.qmgr.name),
                              Variable("DEMUX_HOST", MySystemInfra.f5.name),
                              Variable("LOG_BASE", "/var/tmp/log"))
#    demux = 
    for i in range(20):
        exec "grid_%d = " % i
    
    
class MyModel(Components):
    demux = Component("demux", host=MySystemInfra.f5)
    
    
class MyEnvironment(Environment):
    