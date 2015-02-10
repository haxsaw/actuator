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

from actuator import (InfraModel, MultiResource, MultiResourceGroup, ctxt,
                      with_roles, NamespaceModel, Role, Var, with_variables,
                      with_resources, ResourceGroup)
from actuator.provisioners.openstack.resources import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway,
                                                         RouterInterface)

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
# provisioner.provision_infra_spec(inst)
  

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
