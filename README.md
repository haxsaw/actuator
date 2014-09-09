actuator
========

Use Python to declaratively describe system infra, configuration, and execution requirements, and then provision them in the cloud.

actuator seeks to provide an end-to-end set of tools for spinning up systems in the cloud, from provisioning the infra, configuring it for the software that is to be run, and then executing that system's code.

It does this by providing facilities that allow a system to be described as a collection of *models* in a declarative fashion directly in Python code, in a manner similar to various declarative systems for ORMs (Elixir being a prime example). Being in Python, these models can be very flexible and dynamic in their content, and can be integrated with other Python packages. Also, since the models are in Python, they can be authored and browsed in existing IDEs, and debugged with standard tools. And while each model provides capabilties on their own, they can be inter-related to not only exchange information, but to allow instances of a model to customized to a particular set of circumstances.

### A simple example
The best place to start is to develop a model that can be used provision the infrastructure for a system. An infrastructure model is defined by creating a class that describes to the infra in a declarative fashion. This example will use components from the Openstack binding to actuator.

```python
from actuator import InfraSpec
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)
                                                         
class SingleOpenstackServer(InfraSpec):
  server = Server("actuator1", "Ubuntu 13.10", "m1.small",
                  nics=[lambda ctx: ctx.infra.net])
  net = Network("actuator_ex1_net")
  fip = FloatingIP("actuator_ex1_float", lambda ctx:ctx.infra.server,
                   lambda ctx: ctx.infra.server.iface0.addr0, pool="external")
  subnet = Subnet("actuator_ex1_subnet", lambda ctx: ctx.infra.net, "192.168.23.0/24",
                  dns_nameservers=['8.8.8.8'])
  router = Router("actuator_ex1_router")
  gateway = RouterGateway("actuator_ex1_gateway", lambda ctx:ctx.infra.router,
                          "external")
  rinter = RouterInterface("actuator_ex1_rinter", lambda ctx:ctx.infra.router,
                           lambda ctx:ctx.infra.subnet)
```

The order of the components in the class isn't particularly important; the provisioner will take care of sorting out what needs to be done before what. Also note that use of `lambdas` for some of the arguments; this is how actuator defers evaluation of an argument until the needed reference is defined; more on this below.

Instances of the class (and hence the model) are then created, and the instance is given to a provisioner which inspects the model instance and performs the necessary provsioning actions in the proper order.

```python
from actuator.provisioners.openstack.openstack import OpenstackProvisioner
inst = SingleOpenstackServer("actuator_ex1")
provisioner = OpenstackProvisioner(uid, pwd, uid, url)
provisioner.provision_infra_spec(inst)
```

#### Multi components
If you require a group of identical components to be created in a model, the MultiComponent wrapper provides a way to declare a component as a template and then to get as many copies of that template stamped out as required:

```python
from actuator import MultiComponent

class MultipleServers(InfraSpec):
  
  #First, declare the common networking components
  #
  net = Network("actuator_ex2_net")
  subnet = Subnet("actuator_ex2_subnet", lambda ctx: ctx.infra.net, "192.168.23.0/24",
                  dns_nameservers=['8.8.8.8'])
  router = Router("actuator_ex2_router")
  gateway = RouterGateway("actuator_ex2_gateway", lambda ctx:ctx.infra.router,
                          "external")
  rinter = RouterInterface("actuator_ex2_rinter", lambda ctx:ctx.infra.router,
                           lambda ctx:ctx.infra.subnet)
  
  #now declear the "foreman" this will be the only server the outside world can
  #reach, and it will pass off work requests to the workers. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small",
                    nics=[lambda ctx: ctx.infra.net])
  fip = FloatingIP("actuator_ex2_float", lambda ctx:ctx.infra.server,
                   lambda ctx: ctx.infra.server.iface0.addr0, pool="external")
  
  #finally, declare the workers MultiComponent
  workers = MultiComponent(Server("foreman", "Ubuntu 13.10", "m1.small",
                                  nics=[lambda ctx: ctx.infra.net]))
```

#### Model references and MultiComponents
Once a model class has been defined, you can create expressions that refer to attributes of components in the class:

```python
>>> SingleOpenstackServer.server
<actuator.infra.InfraModelReference object at 0x0291CB70>
>>> SingleOpenstackServer.server.iface0
<actuator.infra.InfraModelReference object at 0x02920110>
>>> SingleOpenstackServer.server.iface0.addr0
<actuator.infra.InfraModelReference object at 0x0298C110>
>>>
```

Likewise, you can create references to attributes on instances of the model class:
```python
>>> inst.server
<actuator.infra.InfraModelInstanceReference object at 0x0298C6B0>
>>> inst.server.iface0
<actuator.infra.InfraModelInstanceReference object at 0x0298C6D0>
>>> inst.server.iface0.addr0
<actuator.infra.InfraModelInstanceReference object at 0x0298CAD0>
>>>
```

All of these expression result in some kind of reference object
