'''
Created on 9 Sep 2014

@author: Tom Carroll
'''
from actuator import (InfraSpec, MultiComponent, MultiComponentGroup, ctxt,
                      with_components, NamespaceSpec, Component, Var, with_variables,
                      with_infra_components, ComponentGroup)
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

class SingleOpenstackServer(InfraSpec):
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.net])
  net = Network("actuator_ex1_net")
  fip = FloatingIP("actuator_ex1_float", ctxt.infra.server,
                   ctxt.infra.server.iface0.addr0, pool="external")
  subnet = Subnet("actuator_ex1_subnet", ctxt.infra.net, "192.168.23.0/24",
                  dns_nameservers=['8.8.8.8'])
  router = Router("actuator_ex1_router")
  gateway = RouterGateway("actuator_ex1_gateway", ctxt.infra.router, "external")
  rinter = RouterInterface("actuator_ex1_rinter", ctxt.infra.router, ctxt.infra.subnet)
  
  
gateway_components = {"net":Network("actuator_ex1_net"),
                      "subnet":Subnet("actuator_ex1_subnet", ctxt.infra.net,
                                      "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                      "router":Router("actuator_ex1_router"),
                      "gateway":RouterGateway("actuator_ex1_gateway", ctxt.infra.router,
                                              "external"),
                      "rinter":RouterInterface("actuator_ex1_rinter", ctxt.infra.router,
                                               ctxt.infra.subnet)}

class SingleOpenstackServer2(InfraSpec):
  with_infra_components(**gateway_components)
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.infra.server,
                   ctxt.infra.server.iface0.addr0, pool="external")
  
  
gateway_component = ComponentGroup("gateway", net=Network("actuator_ex1_net"),
                              subnet=Subnet("actuator_ex1_subnet", ctxt.comp.container.net,
                                          "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                              router=Router("actuator_ex1_router"),
                              gateway=RouterGateway("actuator_ex1_gateway", ctxt.comp.container.router,
                                                    "external"),
                              rinter=RouterInterface("actuator_ex1_rinter", ctxt.comp.container.router,
                                                     ctxt.comp.container.subnet))


class SingleOpenstackServer3(InfraSpec):
  gateway = gateway_component
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.gateway.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.infra.server,
                   ctxt.infra.server.iface0.addr0, pool="external")
  

class MultipleServers(InfraSpec):
  #
  #First, declare the common networking components with with_infra_components
  #
  with_infra_components(**gateway_components)
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the workers. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.net])
  fip = FloatingIP("actuator_ex2_float", ctxt.infra.server,
                   ctxt.infra.server.iface0.addr0, pool="external")
  #
  #finally, declare the workers MultiComponent
  #
  workers = MultiComponent(Server("worker", "Ubuntu 13.10", "m1.small",
                                  nics=[ctxt.infra.net]))
  
  
class MultipleGroups(InfraSpec):
  #
  #First, declare the common networking components
  #
  with_infra_components(**gateway_components)
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the leaders of clusters. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.infra.net])
  fip = FloatingIP("actuator_ex3_float", ctxt.infra.server,
                   ctxt.infra.server.iface0.addr0, pool="external")
  #
  #finally, declare a "cluster"; a leader that coordinates the workers in the
  #cluster, which operate under the leader's direction
  #
  cluster = MultiComponentGroup("cluster",
                                leader=Server("leader", "Ubuntu 13.10", "m1.small",
                                              nics=[ctxt.infra.net]),
                                workers=MultiComponent(Server("cluster_node",
                                                              "Ubuntu 13.10",
                                                              "m1.small",
                                                              nics=[ctxt.infra.net])))
  
  
class SOSNamespace(NamespaceSpec):
  with_variables(Var("COMP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0),
                 Var("COMP_SERVER_PORT", '8081'),
                 Var("EXTERNAL_APP_SERVER_IP", SingleOpenstackServer.fip.ip),
                 Var("APP_SERVER_PORT", '8080'))
                 
  app_server = (Component("app_server", host_ref=SingleOpenstackServer.server)
                  .add_variable(Var("APP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0)))
                                
  compute_server = Component("compute_server", host_ref=SingleOpenstackServer.server)
  
  
def grid_namespace_factory(num_workers=10):
  class GridNamespace(NamespaceSpec):
    with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                   Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                   Var("FOREMAN_EXTERNAL_PORT", "3000"),
                   Var("FOREMAN_WORKER_PORT", "3001"))
     
    foreman = Component("foreman", host_ref=MultipleServers.foreman)
    
    component_dict = {}
    namer = lambda x: "worker_{}".format(x)
    for i in range(num_workers):
      component_dict[namer(i)] = Component(namer(i), host_ref=MultipleServers.workers[i])
      
    with_components(**component_dict)
    
    del component_dict, namer
    
  return GridNamespace()
