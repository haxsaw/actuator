actuator
========

Actuator allows you to use Python to declaratively describe system infra, configuration, and execution requirements, and then provision them in the cloud.

1. [Intro](#intro)
2. [Requirements](#requirements)
  1. [Python version](#python)
  2. [Core packages](#core)
  3. [Cloud support](#cloud)
  4. [Testing with nose](#testing)
3. [Overview](#overview) (as close to a tl;dr that's still meaningful)
4. Infra Models
5. Namespace Models
6. Configuration Models
7. Execution Models
8. Roadmap

## <a name="intro">Intro</a>
**Current status**
- **10 Sep 2014:** actuator can provision a limited set of items against Openstack clouds. It can create instances, networks, subnets, routers (plus router gateways and interfaces), and floating IPs. Not all options available via the Python Openstack client libraries are supported for each provisionable.

Actuator seeks to provide an end-to-end set of tools for spinning up systems in the cloud, from provisioning the infra, defining the names that govern operation, configuring the infra for the software that is to be run, and then executing that system's code on the configured infra.

It does this by providing facilities that allow a system to be described as a collection of *models* in a declarative fashion directly in Python code, in a manner similar to various declarative systems for ORMs (Elixir being a prime example). Being in Python, these models:

- can be very flexible and dynamic in their composition
- can be integrated with other Python packages
- can be authored and browsed in existing IDEs
- can be debugged with standard tools
- can be used in a variety of ways
- and can be factored into multiple modules of reusable sets of declarative components

And while each model provides capabilties on their own, they can be inter-related to not only exchange information, but to allow instances of a model to tailor the content of other models.

Actuator uses a Python *class* as the basis for defining a model, and the class serves as a logical description of the item being modeled; for instance a collection of infrastructure components for a system. These model classes can have both static and dynamic aspects, and can themselves be easily created within a factory function to make the classes' content highly variable.

Actuator models can be related to each other so that their structure and data can inform and sometimes drive the content of other models.

## <a name="requirements">Requirements</a>
**<a name="python">Python version</a>**

Actuator has been developed against Python 2.7. Support for 3.x will come later.

**<a name="core">Core packages</a>**

Actuator requires the following packages:

  - [networkx](https://pypi.python.org/pypi/networkx), 1.9 minimum
  - [faker](https://pypi.python.org/pypi/fake-factory) (to support running tests), 0.4.2 minimum

**<a name="cloud">Cloud support</a>**

Cloud support modules are only required for the cloud systems you wish to provision against

Openstack
  - [python-novaclient](https://pypi.python.org/pypi/python-novaclient), 2.18.1 minimum
  - [python-neutronclient](https://pypi.python.org/pypi/python-neutronclient), 2.3.7 minimum
  - [ipaddress](https://pypi.python.org/pypi/ipaddress), 1.0.6 minimum

**<a name="testing">Testing with nose</a>**
  - [nose](https://pypi.python.org/pypi/nose)
  - [coverage](https://pypi.python.org/pypi/coverage)

## <a name="overview">Overview</a>

Actuator splits the modeling space into four parts:

1. The *infra model*, established with a subclass of **InfraSpec**, defines all the cloud-provisionable components of a system and their inter-relationships. Infra models can have fixed components that are always provisioned with each instance of the model class, as well as variable components that allow multiple copies of components to be easily created on an instance by instance basis. The infra model also has facilities to define groups of components that can be created as a whole, and an arbitrary number of copies of these groups can be created for each instance. References into the infra model can be held by other models, and these references can be subsequently evaluated against an instance of the infra model to extract data from that particular instance. For example, a namespace model may need the IP address from a particular server in an infra model, and so the namespace model may hold a reference into the infra model that yields the actual IP address of a provisioned server when an instance of that infra model is provisioned.
2. The *namespace model*, established with a subclass of **NamespaceSpec**, defines a hierarchical namespace which defines all the names that are important to the run-time components of a system. Names in the namespace can be used for a variety of purposes, such as setting up environment variables, or establishing name-value pairs for processing template files such as scripts or proerties files. The names in the namespace are organized into system components which map onto the executable software in a system, and each system component's namespace is composed of any names specific to that component, plus the names that are defined higher up in the namespace hierarchy. Values for the names can be baked into the model, supplied at model class instantiation, by setting values on the model class instnace, or can be acquired by resolving references to other models such as the infra model.
3. The *configuration model*, established with a subclass of **ConfigSpec**, defines all the tasks to perform on the system components' infrastructure that make them ready to run the system's executables. The configuration model defines tasks to be performed on the logical system components of the namespace model, which in turn inidicates what infrastructure is involved in the configuration tasks. The configuration model also captures task dependencies so that the configuration tasks are all performed in the proper order.
4. The *execution model*, established with a subclass of **ExecutionSpec**, defines the actual processes to run for each system component named in the namespace model.

Although each model can be built and used independently, it is the namespace model that ties all the other models together, linking the relevant aspects of each model to the other.

Actuator then provides a number of support objects that can take instances of these models and processes their informantion, turning it into actions in the cloud. So for instance, a provisioner can take an infra model instance and manage the process of provisioning the infra it describes, and another can marry that instance with a namespace to fully populate a namespace model instance so that the configurator can carry out configuration tasks, and so on.

### A simple example
The best place to start is to develop a model that can be used provision the infrastructure for a system. An infrastructure model is defined by creating a class that describes the infra in a declarative fashion. This example will use components built the [Openstack](http://www.openstack.org/) binding to actuator.

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
  #
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
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the workers. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small",
                    nics=[lambda ctx: ctx.infra.net])
  fip = FloatingIP("actuator_ex2_float", lambda ctx:ctx.infra.server,
                   lambda ctx: ctx.infra.server.iface0.addr0, pool="external")
  #
  #finally, declare the workers' MultiComponent
  #
  workers = MultiComponent(Server("worker", "Ubuntu 13.10", "m1.small",
                                  nics=[lambda ctx: ctx.infra.net]))
```

The *workers* MultiComponent works like a dictionary in that it can be accessed with a key. For every new key that is used with workers, a new instance of the template component is created:

```python
>>> inst2 = MultipleServers("two")
>>> len(inst2.workers)
0
>>> for i in range(5):
...     _ = inst2.workers[i]
...
>>> len(inst2.workers)
5
>>>
```

Keys are always coerced to strings, and for each new instance of the MultiComponent template that is created, the original name is appened with '_{key}' to make each instance distinct.

```python
>>> for w in inst2.workers.instances().values():
...     print w.logicalName
...
worker_1
worker_0
worker_3
worker_2
worker_4
>>>
```

If you require a group of different resources to be provisioned together, the MultiComponentGroup() wrapper provides a way to define a template of multiple resources that will be provioned together. The following model only uses Servers in the template, but any component can appear in a MultiComponentGroup.

```python
from actuator import MultiComponentGroup, MultiComponent

class MultipleGroups(InfraSpec):
  #
  #First, declare the common networking components
  #
  net = Network("actuator_ex3_net")
  subnet = Subnet("actuator_ex3_subnet", lambda ctx: ctx.infra.net, "192.168.23.0/24",
                  dns_nameservers=['8.8.8.8'])
  router = Router("actuator_ex3_router")
  gateway = RouterGateway("actuator_ex3_gateway", lambda ctx:ctx.infra.router,
                          "external")
  rinter = RouterInterface("actuator_ex3_rinter", lambda ctx:ctx.infra.router,
                           lambda ctx:ctx.infra.subnet)
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the leaders of clusters. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small",
                    nics=[lambda ctx: ctx.infra.net])
  fip = FloatingIP("actuator_ex3_float", lambda ctx:ctx.infra.server,
                   lambda ctx: ctx.infra.server.iface0.addr0, pool="external")
  #
  #finally, declare a "cluster"; a leader that coordinates the workers in the
  #cluster, which operate under the leader's direction
  #
  cluster = MultiComponentGroup("cluster",
                                leader=Server("leader", "Ubuntu 13.10", "m1.small",
                                              nics=[lambda ctx:ctx.infra.net]),
                                workers=MultiComponent(Server("cluster_node", "Ubuntu 13.10",
                                                          "m1.small",
                                                          nics=[lambda ctx:ctx.infra.net])))
                                          
```

This model will behave similarly to the MultiServer attribute in the previous model; that is, the cluster attribute can be treated like a dictionary and keys will cause a new instance of the MultiComponentGroup to be created. The keyword args used in creating the MultiComponentGroup become the attributes of the instances of the group; hence the following expressions are fine:

```python
>>> inst3 = MultipleGroups("three")
>>> len(inst3.cluster)
0
>>> for region in ("london", "ny", "tokyo"):
...     _ = inst3.cluster[region]
...
>>> len(inst3.cluster)
3
>>> inst3.cluster["ny"].leader.iface0.addr0
<actuator.infra.InfraModelInstanceReference object at 0x02A51970>
>>> inst3.cluster["ny"].workers[0]
<actuator.infra.InfraModelInstanceReference object at 0x02A56170>
>>> inst3.cluster["ny"].workers[0].iface0.addr0
<actuator.infra.InfraModelInstanceReference object at 0x02A561B0>
>>> len(inst3.cluster["ny"].workers)
1
>>>
```

Note also that you can nest MultiComponents in MultiComponentGroups, and vice versa.


#### Model references
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

All of these expression result in a reference object, either a model reference or a model instance reference. Model references
