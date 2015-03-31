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

import os.path
from actuator import (InfraModel, MultiResource, MultiResourceGroup, ctxt,
                      with_roles, NamespaceModel, Role, Var, with_variables,
                      with_resources, ResourceGroup, MultiRole,
                      ConfigModel, CopyFileTask, CommandTask, with_dependencies,
                      MultiTask, ConfigClassTask)
from actuator.provisioners.openstack.resources import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway,
                                                         RouterInterface)
import actuator

# Simple Openstack example
class SingleOpenstackServer(InfraModel):
    server = Server("actuator1", "Ubuntu 13.10", "m1.small",
                    nics=[ctxt.model.net])  # @UndefinedVariable
    net = Network("actuator_ex1_net")
    fip = FloatingIP("actuator_ex1_float",
                     ctxt.model.server,  # @UndefinedVariable
                     ctxt.model.server.iface0.addr0,  # @UndefinedVariable
                     pool="external")
    subnet = Subnet("actuator_ex1_subnet", ctxt.model.net,  # @UndefinedVariable
                    "192.168.23.0/24",
                    dns_nameservers=['8.8.8.8'])
    router = Router("actuator_ex1_router")
    gateway = RouterGateway("actuator_ex1_gateway",
                            ctxt.model.router,  # @UndefinedVariable
                            "external")
    rinter = RouterInterface("actuator_ex1_rinter",
                             ctxt.model.router,  # @UndefinedVariable
                             ctxt.model.subnet)  # @UndefinedVariable
    
# if you get some credentials on an Openstack instance you can try out the following:
# from actuator.provisioners.openstack.openstack import OpenstackProvisioner
# inst = SingleOpenstackServer("actuator_ex1")
# provisioner = OpenstackProvisioner(uid, pwd, uid, url)
# provisioner.provision_infra_model(inst)
  

#repeat of first example with common components factored out
gateway_components = {"net":Network("actuator_ex1_net"),
                      "subnet":Subnet("actuator_ex1_subnet",
                                      ctxt.model.net,  # @UndefinedVariable
                                      "192.168.23.0/24",
                                      dns_nameservers=['8.8.8.8']),
                      "router":Router("actuator_ex1_router"),
                      "gateway":RouterGateway("actuator_ex1_gateway",
                                              ctxt.model.router,  # @UndefinedVariable
                                              "external"),
                      "rinter":RouterInterface("actuator_ex1_rinter",
                                               ctxt.model.router,  # @UndefinedVariable
                                               ctxt.model.subnet)}  # @UndefinedVariable

class SingleOpenstackServer2(InfraModel):
    with_resources(**gateway_components)
    server = Server("actuator1", "Ubuntu 13.10", "m1.small",
                    nics=[ctxt.model.net])  # @UndefinedVariable
    fip = FloatingIP("actuator_ex1_float", ctxt.model.server,  # @UndefinedVariable
                     ctxt.model.server.iface0.addr0,  # @UndefinedVariable
                     pool="external")
  
  
# MultipleServers tutorial example
class MultipleServers(InfraModel):
    #
    #First, declare the common networking components with with_infra_components
    #
    with_resources(**gateway_components)
    #
    #now declare the "foreman"; this will be the only server the outside world can
    #reach, and it will pass off work requests to the workers. It will need a
    #floating ip for the outside world to see it
    #
    foreman = Server("foreman", "Ubuntu 13.10", "m1.small",
                     nics=[ctxt.model.net])  # @UndefinedVariable
    fip = FloatingIP("actuator_ex2_float", ctxt.model.foreman,  # @UndefinedVariable
                     ctxt.model.foreman.iface0.addr0,  # @UndefinedVariable
                     pool="external")
    #
    #finally, declare the workers MultiComponent
    #
    workers = MultiResource(Server("worker", "Ubuntu 13.10", "m1.small",
                                    nics=[ctxt.model.net]))  # @UndefinedVariable
  

# Resource groups example
gateway_component = ResourceGroup("gateway", net=Network("actuator_ex1_net"),
                                   subnet=Subnet("actuator_ex1_subnet",
                                                 ctxt.comp.container.net,
                                                 "192.168.23.0/24",
                                                 dns_nameservers=['8.8.8.8']),
                                   router=Router("actuator_ex1_router"),
                                   gateway=RouterGateway("actuator_ex1_gateway",
                                                         ctxt.comp.container.router,
                                                         "external"),
                                   rinter=RouterInterface("actuator_ex1_rinter",
                                                          ctxt.comp.container.router,
                                                          ctxt.comp.container.subnet))

class SingleOpenstackServer3(InfraModel):
    gateway = gateway_component
    server = Server("actuator1", "Ubuntu 13.10", "m1.small",
                    nics=[ctxt.model.gateway.net])  # @UndefinedVariable
    fip = FloatingIP("actuator_ex1_float", ctxt.model.server,  # @UndefinedVariable
                     ctxt.model.server.iface0.addr0,  # @UndefinedVariable
                     pool="external")
  

class MultipleGroups(InfraModel):
    #
    #First, declare the common networking components
    #
    with_resources(**gateway_components)
    #
    #now declare the "foreman"; this will be the only server the outside world can
    #reach, and it will pass off work requests to the leaders of clusters. It will need a
    #floating ip for the outside world to see it
    #
    foreman = Server("foreman", "Ubuntu 13.10", "m1.small",
                     nics=[ctxt.model.net])  # @UndefinedVariable
    fip = FloatingIP("actuator_ex3_float", ctxt.model.server,  # @UndefinedVariable
                     ctxt.model.server.iface0.addr0,  # @UndefinedVariable
                     pool="external")
    #
    #finally, declare a "cluster"; a leader that coordinates the workers in the
    #cluster, which operate under the leader's direction
    #
    cluster = MultiResourceGroup("cluster",
                                  leader=Server("leader", "Ubuntu 13.10", "m1.small",
                                                nics=[ctxt.model.net]),  # @UndefinedVariable
                                  workers=MultiResource(Server("cluster_node",
                                                                "Ubuntu 13.10",
                                                                "m1.small",
                                                                nics=[ctxt.model.net])))  # @UndefinedVariable
  
  
class SOSNamespace(NamespaceModel):
    with_variables(Var("COMP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0),
                   Var("COMP_SERVER_PORT", '8081'),
                   Var("EXTERNAL_APP_SERVER_IP", SingleOpenstackServer.fip.ip),
                   Var("APP_SERVER_PORT", '8080'))
                   
    app_server = (Role("app_server", host_ref=SingleOpenstackServer.server)
                    .add_variable(Var("APP_SERVER_HOST",
                                      SingleOpenstackServer.server.iface0.addr0)))
                                  
    compute_server = Role("compute_server", host_ref=SingleOpenstackServer.server)
  

# First approach for dynamic Namespaces
def grid_namespace_factory(num_workers=10):
    class GridNamespace(NamespaceModel):
        with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                       Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                       Var("FOREMAN_EXTERNAL_PORT", "3000"),
                       Var("FOREMAN_WORKER_PORT", "3001"))
       
        foreman = Role("foreman", host_ref=MultipleServers.foreman)
      
        role_dict = {}
        namer = lambda x: "worker_{}".format(x)
        for i in range(num_workers):
            role_dict[namer(i)] = Role(namer(i), host_ref=MultipleServers.workers[i])
          
        with_roles(**role_dict)
        
        del role_dict, namer
      
    return GridNamespace()


# Second approach for dynamic namespaces
class GridNamespace(NamespaceModel):
    with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                   Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                   Var("FOREMAN_EXTERNAL_PORT", "3000"),
                   Var("FOREMAN_WORKER_PORT", "3001"))
    
    foreman = Role("foreman", host_ref=MultipleServers.foreman)
    
    grid = MultiRole(Role("node",
                          host_ref=ctxt.nexus.inf.workers[ctxt.name]))  # @UndefinedVariable


# Var examples
class VarExample(NamespaceModel):
    with_variables(Var("NODE_NAME", "!{BASE_NAME}-!{NODE_ID}"))
    grid = (MultiRole(Role("worker", variables=[Var("NODE_ID", ctxt.name)]))
             .add_variable(Var("BASE_NAME", "Grid")))


# Namespace for ConfigExamples
class SimpleNamespace(NamespaceModel):
    with_variables(Var("DEST", "/tmp"),
                   Var("PKG", "actuator"),
                   Var("CMD_TARGET", "127.0.0.1"))
    copy_target = Role("copy_target", host_ref="!{CMD_TARGET}")


# SimpleConfig example
#find the path to actuator; if it is under our cwd, the it won't be at an absolute path
actuator_path = actuator.__file__
if not os.path.isabs(actuator_path):
  actuator_path = os.path.join(os.getcwd(), "!{PKG}")

class SimpleConfig(ConfigModel):
    cleanup = CommandTask("clean", "/bin/rm -f !{PKG}", chdir="!{DEST}",
                          task_role=SimpleNamespace.copy_target)
    copy = CopyFileTask("copy-file", "!{DEST}", src=actuator_path,
                        task_role=SimpleNamespace.copy_target)
  
  
# SimpleConfig again but with dependencies this time
class SimpleConfig2(ConfigModel):
    cleanup = CommandTask("clean", "/bin/rm -f !{PKG}", chdir="!{DEST}",
                          task_role=SimpleNamespace.copy_target)
    copy = CopyFileTask("copy-file", "!{DEST}", src=actuator_path,
                        task_role=SimpleNamespace.copy_target)
    #NOTE: this call must be within the config model, not after it!
    with_dependencies( cleanup | copy )


# Auto-scaling example
class GridInfra(InfraModel):  #needed to add this
    with_resources(**gateway_components)
    grid = MultiResource(Server("grid_node", "Ubuntu 13.10", "m1.small",
                                nics=[ctxt.model.net]))  # @UndefinedVariable
    
class GridNamespace2(NamespaceModel):
    grid = MultiRole(Role("grid-node", host_ref=GridInfra.grid[ctxt.name]))


class GridConfig(ConfigModel):
    reset = MultiTask("reset", CommandTask("remove", "/bin/rm -rf /some/path/*"),
                      GridNamespace2.q.grid.all())
    copy = MultiTask("copy", CopyFileTask("copy-tarball", '/some/path/software.tgz',
                                          src='/some/local/path/software.tgz'),
                     GridNamespace2.q.grid.all())
    with_dependencies(reset | copy)


# Config classes as tasks example
#this is the same namespace model as above
class GridNamespace3(NamespaceModel):
    grid = MultiRole(Role("grid-node", host_ref=GridInfra.grid[ctxt.name]))


#this config model is new; it defines all the tasks and dependencies for a single role
#Notice that there is no mention of a 'task_role' within this model
class NodeConfig(ConfigModel):
    reset = CommandTask("remove", "/bin/rm -rf /some/path/*")
    copy = CopyFileTask("copy-tarball", '/some/path/software.tgz',
                        src='/some/local/path/software.tgz')
    with_dependencies(reset | copy)


#this model now uses the NodeConfig model in a MultiTask to define all the tasks that need
#to be carried out on each role
class GridConfig2(ConfigModel):
    setup_nodes = MultiTask("setup-nodes", ConfigClassTask("setup-suite", NodeConfig),
                            GridNamespace3.q.grid.all())
