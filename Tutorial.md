Actuator Tutorial
========

Actuator allows you to use Python to declaratively describe system infra, configuration, and execution requirements, and then provision them in the cloud.

1. [Intro](#intro)
2. [Overview](#overview) (as close to a tl;dr that's still meaningful)
  1. [Infra Model](#ov_inframodel)
  2. [Namespace Model](#ov_namespacemodel)
  3. [Configuration Model](#ov_configmodel)
  4. [Execution Model](#ov_execmodel)
3. [Infra models](#inframodels)
  1. [A simple Openstack example](#simple_openstack_example)
  2. [Multiple Components](#multi_resources)
  3. [Component Groups](#resource_groups)
  4. [Model References and Context Expressions](#modrefs_ctxtexprs)
4. [Namespace models](#nsmodels)
  1. [An example](#simplensexample)
  2. [Dynamic Namespaces](#dynamicns)
  3. [Var objects](#varobjs)
5. [Configuration models](#configmodels)
  1. [Declaring tasks](#taskdec)
  2. [Declaring dependencies](#taskdeps)
  3. [Dependency expressions](#depexp)
  4. [Auto-scaling tasks](#taskscaling)
  5. [Config classes as tasks](#classtasks)
  6. [Reference selection expressions](#refselect)
6. Execution Models (yet to come)

## <a name="intro">Intro</a>

Actuator seeks to provide an end-to-end set of tools for spinning up systems in the cloud, from provisioning the infra, defining the roles that define the system and the names that govern their operation, configuring the infra for the software that is to be run, and then executing that system's code on the configured infra.

It does this by providing facilities that allow a system to be described as a collection of *models* in a declarative fashion directly in Python code, in a manner similar to various declarative systems for ORMs (Elixir being a prime example). Being in Python, these models:

- can be very flexible and dynamic in their composition
- can be integrated with other Python packages
- can be authored and browsed in existing IDEs
- can be debugged with standard tools
- can be inspected for auditing and other purposes
- and can be factored into multiple modules of reusable sets of declarative components

And while each model provides capabilties on their own, they can be inter-related to not only exchange information, but to allow instances of a model to tailor the content of other models.

Actuator uses a Python *class* as the basis for defining a model, and the class serves as a logical description of the item being modeled; for instance a collection of infrastructure resources for a system. These model classes can have both static and dynamic aspects, and can themselves be easily created within a factory function to make the classes' content highly variable.

Actuator models can be related to each other so that their structure and data can inform and sometimes drive the content of other models.

## <a name="overview">Overview</a>

Actuator splits the modeling space into four parts:

###<a name="ov_inframodel">Infra Model</a>

The *infra model*, established with a subclass of **InfraModel**, defines all the infrastructure resources of a system and their inter-relationships. Infra models can have fixed components that are always provisioned with each instance of the model class, as well as variable components that allow multiple copies of components to be easily created on an instance-by-instance basis. The infra model also has facilities to define groups of components that can be created as a whole, and an arbitrary number of copies of these groups can be created for each instance. References into the infra model can be held by other models, and these references can be subsequently evaluated against an instance of the infra model to extract data from that particular instance. For example, a namespace model may need the IP address from a particular server in an infra model, and so the namespace model may hold a reference into the infra model for the IP address attribute that yields the actual IP address of a provisioned server when an instance of that infra model is provisioned.

###<a name="ov_namespacemodel">Namespace Model</a>

The *namespace model*, established with a subclass of **NamespaceModel**, defines a hierarchical namespace based around system "roles" which defines all the names that are important to the configuration and run-time operation of a system. A "role" can be thought of as a software component of a system; for instance, a system might have a database role, an app server role, or a grid node role. Names in the namespace can be used for a variety of purposes, such as setting up environment variables, or establishing name-value pairs for processing template files such as scripts or properties files. The names in the namespace are associated with the namespace's roles, and each system role's view of the namespace is composed of any names specific to that role, plus the names that are defined higher up in the namespace hierarchy. Values for the names can be baked into the model, supplied at model class instantiation, by setting values on the model class instance, or can be acquired by resolving references to other models such as the infra model.

###<a name="ov_configmodel">Configuration Model</a>

The *configuration model*, established with a subclass of **ConfigModel**, defines all the tasks to perform on the system roles' infrastructure that make them ready to run the system's executables. The configuration model defines tasks to be performed on the logical system roles of the namespace model, which in turn inidicates what infrastructure is involved in the configuration tasks. The configuration model also captures task dependencies so that the configuration tasks are all performed in the proper order. Configuration models can also be treated as tasks and used within other configuration models.

###<a name="ov_execmodel">Execution Model</a>

The *execution model*, established with a subclass of **ExecutionModel**, defines the actual processes to run for each system component named in the namespace model. Like with the configuration model, dependencies between the executables can be expressed so that a particular startup order can be enforced.

Each model can be built and used independently, but it is the inter-relationships between the models that give Actuator its representational power.

Actuator then provides a number of support tools that can take instances of these models and processes their informantion, turning it into actions in the cloud. So for instance, a provisioner can take an infra model instance and manage the process of provisioning the infra it describes, and another can marry that instance with a namespace to fully populate a namespace model instance so that the configurator can carry out configuration tasks, and so on.

As may have been guessed, the key model in Actuator is the namespace model, as it serves as the focal point to tie all the other models together.

##<a name="inframodels">Infra models</a>

Although the namespace model is the one that is most central in Actuator, it actually helps to start with the infra model as it not only is a little more accessible, but building an infra model first can yield immediate benefits. The infra model describes all the dynamically provisionable infra resources and describes how they relate to each other. The model can define groups of resources and resources that can be repeated an arbitrary number of times, allowing them to be nested in very complex configurations.

### <a name="simple_openstack_example">A simple Openstack example</a>
The best place to start is to develop a model that can be used to provision the infrastructure for a system. An infrastructure model is defined by creating a class that describes the infra's resources in a declarative fashion. This example will use components built using the [Openstack](http://www.openstack.org/) binding to Actuator.

```python
from actuator import InfraModel, ctxt
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

class SingleOpenstackServer(InfraModel):
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  net = Network("actuator_ex1_net")
  fip = FloatingIP("actuator_ex1_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
  subnet = Subnet("actuator_ex1_subnet", ctxt.model.net, "192.168.23.0/24",
                  dns_nameservers=['8.8.8.8'])
  router = Router("actuator_ex1_router")
  gateway = RouterGateway("actuator_ex1_gateway", ctxt.model.router, "external")
  rinter = RouterInterface("actuator_ex1_rinter", ctxt.model.router, ctxt.model.subnet)
```

The order of the components in the class isn't particularly important; the provisioner will take care of sorting out what needs to be done before what. Also note the use of 'ctxt.model.*' for some of the arguments; these constructions are called _context expressions_ as they result in instances of the ContextExpr class, which are used to defer the evaluation of a model reference until an instance of the model (the "context") is available to evaluate the expression against. 

Instances of the class (and hence the model) are then created, and the instance is given to a provisioner which inspects the model instance and performs the necessary provsioning actions in the proper order.

```python
from actuator.provisioners.openstack.openstack import OpenstackProvisioner
inst = SingleOpenstackServer("actuator_ex1")
provisioner = OpenstackProvisioner(uid, pwd, uid, url)
provisioner.provision_infra_spec(inst)
```

Often, there's a lot of repeated boilerplate in an infra spec; in the above example the act of setting up a network, subnet, router, gateway, and router interface are all common resources needed to get access to provisioned infra from outside the cloud. Actuator provides two ways to factor out common groups of resources: providing a dictionary of resources to the with_infra_resources function, and using the [ResourceGroup](#resource_groups) wrapper class to define a group of standard resources. We'll recast the above example using with_infra_components():

```python
gateway_components = {"net":Network("actuator_ex1_net"),
                      "subnet":Subnet("actuator_ex1_subnet", ctxt.model.net,
                                      "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                      "router":Router("actuator_ex1_router"),
                      "gateway":RouterGateway("actuator_ex1_gateway", ctxt.model.router,
                                              "external"),
                      "rinter":RouterInterface("actuator_ex1_rinter", ctxt.model.router,
                                               ctxt.model.subnet)}


class SingleOpenstackServer(InfraModel):
  with_infra_resources(**gateway_components)
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
```

With with_infra_resources(), all the keys in the dictionary are established as attributes on the infra model class, and can be accessed just as if they were declared directly in the class. Since this is just standard keyword argument notation, you could also use a list of "name=value" expressions for the same effect.

### <a name="multi_resources">Multiple resources</a>
If you require a set of identical components to be created in a model, the MultiResource wrapper provides a way to declare a resource as a template and then to get as many copies of that template created as required:

<a name="multiservers">&nbsp;</a>
```python
from actuator import InfraSpec, MultiResource, ctxt, with_infra_resources
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

class MultipleServers(InfraModel):
  #
  #First, declare the common networking components with with_infra_components
  #
  with_infra_resources(**gateway_components)
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the workers. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex2_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
  #
  #finally, declare the workers MultiResource
  #
  workers = MultiResource(Server("worker", "Ubuntu 13.10", "m1.small",
                                  nics=[ctxt.model.net]))
```

The *workers* MultiResource works like a dictionary in that it can be accessed with a key. For every new key that is used with workers, a new instance of the template component is created:

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

Keys are always coerced to strings, and for each new instance of the MultiResource template that is created, the original name is appened with '_{key}' to make each instance distinct.

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

### <a name="resource_groups">Resource Groups</a>

If you require a group of different resources to be provisioned as a unit, the ResourceGroup() wrapper provides a way to define a template of multiple resources that will be provisioned as a whole. The following example shows how the boilerplate gateway components could be expressed using a ResourceGroup().

```python
gateway_component = ResourceGroup("gateway", net=Network("actuator_ex1_net"),
                              subnet=Subnet("actuator_ex1_subnet", ctxt.comp.container.net,
                                          "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                              router=Router("actuator_ex1_router"),
                              gateway=RouterGateway("actuator_ex1_gateway", ctxt.comp.container.router,
                                                    "external")
                              rinter=RouterInterface("actuator_ex1_rinter", ctxt.comp.container.router,
                                                     ctxt.comp.container.subnet))


class SingleOpenstackServer(InfraModel):
  gateway = gateway_component
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.gateway.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
```

The keyword args used in creating the ResourceGroup become the attributes of the instances of the group.

If you require a group of different resources to be provisioned together repeatedly, the MultiResourceGroup() wrapper provides a way to define a template of multiple resources that will be provioned together. MultiResourceGroup() is simply a shorthand for wrapping a ResourceGroup in a MultiResource. The following model only uses Servers in the template, but any component (including ResourceGroups and MultiResources) can appear in a MultiResourceGroup.

<a name="multigroups">&nbsp;</a>
```python
from actuator import InfraModel, MultiResource, MultiResourceGroup, ctxt
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

class MultipleGroups(InfraSpec):
  #
  #First, declare the common networking components
  #
  with_infra_resources(**gateway_components)
  #
  #now declare the "foreman"; this will be the only server the outside world can
  #reach, and it will pass off work requests to the leaders of clusters. It will need a
  #floating ip for the outside world to see it
  #
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex3_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
  #
  #finally, declare a "cluster"; a leader that coordinates the workers in the
  #cluster, which operate under the leader's direction
  #
  cluster = MultiResourceGroup("cluster",
                                leader=Server("leader", "Ubuntu 13.10", "m1.small",
                                              nics=[ctxt.model.net]),
                                workers=MultiResource(Server("cluster_node",
                                                              "Ubuntu 13.10",
                                                              "m1.small",
                                                              nics=[ctxt.model.net])))
```

The keyword args used in creating the ResourceGroup become the attributes of the instances of the group; hence the following expressions are fine:

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

This model will behave similarly to the MultiServer model above; that is, the *cluster* attribute can be treated like a dictionary and keys will cause a new instance of the MultiResourceGroup to be created. Note also that you can nest MultiResources in MultiResourceGroups, and vice versa.


### <a name="modrefs_ctxtexprs">Model References and Context Expressions</a>
A few of the examples above have shown that accessing model attributes results in a reference object of some sort. These objects are the key to declaratively relating aspects of various models to one another. For instance, a reference to the attribute that stores the IP address of a provisioned server can be used as the value of a variable in the namespace model, and once the IP address is known, the variable will have a meaningful value.

There are two different ways to get references to parts of a model: first through the use of _model references_, which are direct attribute accesses to model or model instance objects. This approach can only be used after a model class has already been created; this means that if a reference between memebers is required in the middle of a model class definition, model references aren't yet available, and hence can't be used.

The second method is through the use of _context expressions_. A context expression provides a way to express a reference to objects and models that don't exist yet-- the expression's evaluation is delayed until the reference it represents exists, and only then does the expression yield an actual reference.

#### Model References

Once a model class has been defined, you can create expressions that refer to attributes of components in the class:

```python
>>> SingleOpenstackServer.server
<actuator.infra.ModelReference object at 0x0291CB70>
>>> SingleOpenstackServer.server.iface0
<actuator.infra.ModelReference object at 0x02920110>
>>> SingleOpenstackServer.server.iface0.addr0
<actuator.infra.ModelReference object at 0x0298C110>
>>>
```

Likewise, you can create references to attributes on instances of the model class:
```python
>>> inst.server
<actuator.infra.ModelInstanceReference object at 0x0298C6B0>
>>> inst.server.iface0
<actuator.infra.ModelInstanceReference object at 0x0298C6D0>
>>> inst.server.iface0.addr0
<actuator.infra.ModelInstanceReference object at 0x0298CAD0>
>>>
```

All of these expressions result in a reference object, either a model reference or a model instance reference. _References_ are objects that serve as a logical "pointer" to a component or attribute of an infra model. _Model references_ are logical references into an infra model; there may not be an actual component or attribute underlying the reference. _Model instance references_ (or "instance references") are references into an _instance_ of a  model; they refer to an actual resource or attribute (although the value of either may not have been set yet). Instance references can only be created relative to an instance of a model, or by transforming a model reference to an instance reference using an instance of a model. An example here will help:

```python
#re-using the definition of SingleOpenstackServer from above...
>>> inst = SingleOpenstackServer("refs")
>>> modref = SingleOpenstackServer.server
>>> instref = inst.server
>>> instref is inst.get_inst_ref(modref)
True
>>>
```

Model references provide a number of capabilities:

- They serve as bookmarks into models
- They behave something like a [future](https://en.wikipedia.org/wiki/Futures_and_promises) in that they provide a reference to a value that hasn't been determined yet
- They provide a way to make logical connections between models in order to share information
- They serve as a way to logically identify components that should be provisioned

For example, suppose a model elsewhere needs to know the first IP address on the first interface of the server from the SingleOpenstackServer model. That IP address won't be known until the server is provisioned, but a reference to this piece of information can be created by the following expression:

```python
SingleOpenstackServer.server.iface0.addr0
```

The rest of Actuator knows how to deal with these references and how to extract the underlying values when they become available. Every attribute of all objects in a model produce a reference, and the underying value that the reference is pointing to can be accessed with the _value()_ method:

```python
>>> SingleOpenstackServer.server.name.value()
actuator1
>>>
```
Since model references are the means to make connections between models, we'll look at these in more detail in the section below on [namespace models](#nsmodels).

#### Context Expressions

There are circumstances where model references either aren't possible or can't get the job done. For example, take this fragment of the the [SingleOpenstackServer](#simple_openstack_example) infra model example from above:

```python
class SingleOpenstackServer(InfraSpec):
  router = Router("actuator_ex1_router")
  gateway = RouterGateway("actuator_ex1_gateway", ctxt.model.router, "external")
  rinter = RouterInterface("actuator_ex1_rinter", ctxt.model.router, ctxt.model.subnet)
  #etc...
```

The RouterGateway and RouterInterface resources both require a model reference to a Router resource as their second argument. Now, after the SingleOpenstackServer class is defined, this reference would be easy to obtain with an expression such as SingleOpenstackServer.router. However, within the class defintion, the class object doesn't exist yet, and so trying to use an expression like:

```python
  gateway = RouterGateway("actuator_ex1_gateway", SingleOpenstackServer.router, "external")
```

will yield a NameError exception saying that "SingleOpenstackServer" is not defined.

This is where context expressions come in. Every time a component in a model is processed by Actuator (be it a resource or some other component), a processing context is created. The _context_ wraps up:

- the instance of the model the component is part of,
- the component itself,
- and the name of the component.

In a model class, the context is referred to by the global object *ctxt*, and the above three objects can be accessed via ctxt in the following way:

- the model instance can be accessed via _ctxt.model_
- the component itself can be accessed via _ctxt.comp_
- the component's name can be accessed via _ctxt.name_

These _context expressions_ provide a way to define a reference to another part of the model that will be evaluated only when the reference is needed. Repeating the infra model fragment from above:

```python
class SingleOpenstackServer(InfraSpec):
  router = Router("actuator_ex1_router")
  gateway = RouterGateway("actuator_ex1_gateway", ctxt.model.router, "external")
  rinter = RouterInterface("actuator_ex1_rinter", ctxt.model.router, ctxt.model.subnet)
  #etc...
```

We can see that we can provide the required reference to SingleOpenstackServer's Router by creating a context expression that names the router attribute of the SingleOpenstackServer model via the ctxt object.

The context object _ctxt_ allows you to access any attribute of a model or component reachable from either the model or component. Hence, in the same way we were able to access first IP address on the first interface with:

```python
SingleOpenstackServer.server.iface.addr0
```

We can use a context expression to create a reference to this IP using the ctxt object:

```python
ctxt.model.server.iface.addr0
```

As mentioned previously, context expressions provide a way to express model relationships between model components before the model is fully defined. Additionally, because they allow references to be evaluated later in processing, they are useful in certain circumstances in creating references between models. We'll see examples of these sorts of uses below.

## <a name="nsmodels">Namespace models</a>
The namespace model provides the means for joining the other Actuator models together. It does this by declaring the logical roles of a system, relating these roles to the infrastructure elements where the roles are to execute, and providing the means to identify what configuration task is to be carried out for each role as well as what executables are involved with making the role function.

A namespace model has four aspects. It provides the means to:

1. ...define the logical execution roles of a system
2. ...define the relationships between logical roles and hosts in the infra model where the roles are to execute
3. ...arrange the roles in a meaningful hierarchy
4. ...establish names within the hierachy whose values will impact configuration activities and the operation of the roles

### <a name="simplensexample">An example</a>
Here's a trivial example that demonstrates the basic features of a namespace. It will model two roles, an app server and a computation engine, and use the SingleOpenstackServer infra model from above for certain values:

```python
from actuator import Var, NamespaceModel, Role, with_variables

class SOSNamespace(NamespaceModel):
  with_variables(Var("COMP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0),
                 Var("COMP_SERVER_PORT", '8081'),
                 Var("EXTERNAL_APP_SERVER_IP", SingleOpenstackServer.fip.ip),
                 Var("APP_SERVER_PORT", '8080'))
                 
  app_server = (Role("app_server", host_ref=SingleOpenstackServer.server)
                  .add_variable(Var("APP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0)))
                                
  compute_server = Role("compute_server", host_ref=SingleOpenstackServer.server)
```

First, some global Vars (variables) are established that capture the host and port where the compute_server will be found, the external IP where the app_server will be found, and the port number where it can be contacted. While the ports are hard coded values, the host IPs are determined from the SingleOpenstackServer model by creating a model reference to the model attribute where the IP will become available. Since these Vars are defined at the model (global) level, they are visible to all components.

Next comes the app_server role, which is declared with a call to Role. Besides a name, Role is supplied a host_ref in the form of Server model reference from the SingleOpenstackserver model. This tells the namespace that this component's configuration tasks and executables will be run on whatever host is provisioned for this part of the model. The app_server component is also supplied a private Var object that captures the host IP where the server will run. While the app_server binds to an IP on the subnet, the FloatingIP associated with this subnet IP will enable the server to be reached from the outside world.

Finally, we declare the compute_server Role. Similar to the app_server Role, the compute_server Role identifies the Server where it will run by setting the host_ref keyword to a infra model reference for the Server to use. In this example, both Components will be run on the same server.

When an instance of the namespace is created, useful questions can be posed to the instance:
* We can ask for a list of roles
* We can ask for all the Vars (and their values) from the perspective of a specific role
* We can identify any Vars whose value can't be resolved from the perspective of each role
* We can ask to compute the necessary provisioning based on the namespace and an infra model instance

These operations look something like this:
```python
>>> sos = SingleOpenstackServer("sos")
>>> ns = SOSNamespace()
>>> for r in ns.get_roles.values():
...     print "Component: %s, Vars:" % r.name
...     for v in r.get_visible_vars().values():
...             value = v.get_value(c)
...
...             print "%s=%s" % (v.name, value if Value is not None else "<UNRESOLVED>")
...
Component: compute_server, Vars:
COMP_SERVER_HOST=<UNRESOLVED>
COMP_SERVER_PORT=8081
APP_SERVER_PORT=8080
EXTERNAL_APP_SERVER_IP=<UNRESOLVED>
Component: app_server, Vars:
APP_SERVER_HOST=<UNRESOLVED>
COMP_SERVER_HOST=<UNRESOLVED>
COMP_SERVER_PORT=8081
APP_SERVER_PORT=8080
EXTERNAL_APP_SERVER_IP=<UNRESOLVED>
>>> provisionables = ns.compute_provisioning_for_environ(sos)
>>> provisionables
set([<actuator.provisioners.openstack.components.Router object at 0x026EC070>,<actuator.p
rovisioners.openstack.components.Subnet object at 0x026E5E90>, <actuator.provisioners.ope
nstack.components.Network object at 0x026EC0D0>, <actuator.provisioners.openstack.compone
nts.FloatingIP object at 0x026E5EF0>, <actuator.provisioners.openstack.components.RouterG
ateway object at 0x026EC130>, <actuator.provisioners.openstack.components.Server object a
t 0x026E5F50>, <actuator.provisioners.openstack.components.RouterInterface object at 0x02
6E5FF0>])
>>> 
```

### <a name="dynamicns">Dynamic Namespaces</a>
The namespace shown above is static in nature. Although some of the values for Var objects are supplied dynamically, the namespace itself has a static number of components and structure.

Actuator allows for more dynamic namespaces to be constructed, in particular in support of arbitrary numbers of components. By coupling such a namespace with an infra model that uses MultiResource or MultiResourceGroup elements, appropriately sized infra can be identified and provisioned depending on the nature of the dynamic namespace.

The best way to understand this is with an example. We'll devise a trivial computational grid: besides the normal gateway elements, the infrastructure will contain a "foreman" to coordinate the computational activities of a variable number of "workers", each on a seperate server.

The [MultipleServers](#multiservers) infra model from above fits this pattern, so we'll define a dynamic namespace model that grows roles that refer back to this infra model in order to acquire the appropriate infrastructure to meet the namespace's needs.

We'll use two different techniques for creating a suitable dynamic namespace. In the first, we'll create a class factory function that defines a new namespace class with the appropriate number of worker Components. In the second, we'll use some additional features of Actuator to express the same capabilities in a more concise declarative way.

First, the class factory approach:

```python
def grid_namespace_factory(num_workers=10):

  class GridNamespace(NamespaceModel):
    with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                   Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                   Var("FOREMAN_EXTERNAL_PORT", "3000"),
                   Var("FOREMAN_WORKER_PORT", "3001"))
     
    foreman = Role("foreman", host_ref=MultipleServers.foreman)
    
    component_dict = {}
    namer = lambda x: "worker_{}".format(x)
    for i in range(num_workers):
      component_dict[namer(i)] = Component(namer(i), host_ref=MultipleServers.workers[i])
      
    with_roles(**component_dict)
    
    del component_dict, namer
    
  return GridNamespace()
```

Making a dynamic namespace class in Python is trivial; by simply putting the class statement inside a function, each call to the function will generate a new class. By supplying parameters to the function, the content of the class can be altered.

In this example, after setting some global Vars in the namespace with the with_variables() function, we next create the "foreman" role, and use the host_ref keyword argument to associate it with a server in the infra model. Next, we set up a dictionary whose keys will eventually become other attributes on the namespace class, and whose values will become the associated Components for those attributes. In a for loop, we then simply create new instances of Component, associating each with a different worker in the MultipleServers infra model (host_ref=MultipleServers.workers[i]). We then use the function *with_roles()* to take the content of the dict and attach all the created components to the namespace class. The class finishes by deleting the unneeded dict and lambda function. The factory function completes by returning an instance of the class that was just defined.

Now we can use the factory function to create grids of different sizes simply by varying the input value to the factory function:

```python  
>>> ns = grid_namespace_factory(20)
>>> ms_inst = MultipleServers("ms")
>>> provs = ns.compute_provisioning_for_environ(ms_inst)
>>> len(provs)
27
>>> ns.worker_8
<actuator.namespace.Component object at 0x02670D10>
>>>
>>> ns2 = grid_namespace_factory(200)
>>> ms_inst2 = MultipleServers("ms2")
>>> provs2 = ns2.compute_provisioning_for_environ(ms_inst2)
>>> len(provs2)
207
>>>
```

Now for the second approach, which utilizes some other capabilities of Actuator. Namespaces have their own analogs to the infra model's ResourceGroup, MultiResource, and MultiResourceGroup classes: they are RoleGroup, MultiRole, and MultiRoleGroup. These are similar to their infrastructure counterparts with the exceptions that

1. They can contain only Roles or the various Role containers mentinoed above;
2. They can have variables (Var objects) attached to them.

Using this approach, the solution looks like the following:

```python
class GridNamespace(NamespaceModel):
  with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                 Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                 Var("FOREMAN_EXTERNAL_PORT", "3000"),
                 Var("FOREMAN_WORKER_PORT", "3001"))
                  
  foreman = Role("foreman", host_ref=MultipleServers.foreman)
  
  grid = MultiRole(Role("node", host_ref=ctxt.model.infra.workers[ctxt.name]))
```

This approach doesn't use a factory; instead, it uses MultiRole to define a "template" Role object to create instances from each new key supplied to the "grid" attribute of the namespace model. After defining a namespace class this way, one simply creates instances of the class and then, in a manner similar to creating new components on an infra model, uses new keys to create new Roles on the namespace instance. These new role instances will in turn create new worker instances on a MultiServers model instance:

```python
>>> ns = GridNamespace()
>>> ms_infra = MultipleServers("ms1")
>>> for i in range(20):
...     _ = ns.grid[i]
... 
>>> provs = ns.compute_provisioning_for_environ(ms_infra)
>>> len(provs)
27
>>> ns2 = GridNamespace()
>>> ms_infra2 = MultipleServers("ms2")

>>> for i in range(200):
...     _ = ns2.grid[i]
... 
>>> provs2 = ns2.compute_provisioning_for_environ(ms_infra2)
>>> len(provs2)
207
```

Using this approach, we can treat the namespace model like the infra model, meaning that we can provide a logical definition of roles and drive the creation of physical roles simply by referencing them. These references flow through to the infra model, likewise causing dynamic infra resources to be created.

### <a name="varobjs">Var objects</a>
Namespaces and their Roles serve as containers for *Var* objects. These objects provide a means to establish names that can be used symbolically for a variety of purposes, such as environment variables for tasks and executables, or parameter maps for processing templatized text files such as scripts or properties files.

Vars associate a 'name' (the first parameter) with a value (the second parameter). The value parameter of a Var can be one of several kinds of objects: it may be a plain string, a string with a replacement paremeter in it, a reference to an infra model element that results in a string, or context expression that results in a string.

We've seen examples of both plain strings and model references as values, and now will look at how replacement parameters and context expressions work. A replacement parameter takes the form of _!{string}_; whenever this pattern is found, the inner string is extracted and looked up as the name for another Var. The lookup repeats; if the value found contains '!{string}', the lookup is repeated until no more replacement parameters are found. This allows complex replacement patterns to be defined.

Additionally, the hierarchy of roles, containers (MultiRole, RoleGroup, and MultiRoleGroup) and the model class is taken into account when searching for a variable. If the variable can't be found defined on the current role, the enclosing variable container is searched, progressively moving to the model class itself. If the variable can't be found on the model class, then the variable is undefined, and an exception may be raised (depending on how the search was initiated). This allows for complex replacement patterns to be defined which have different parts of the pattern filled in at different levels of the namespace.

The following example will make this more concrete. Here we will create a Namespace model that defines a variable "NODE_NAME" that is composed of a base name plus an id specific to the node. While NODE_NAME will be defined at a global level in the model, the two other variables the comprise NODE_NAME, BASE_NAME and NODE_ID, will be defined on different model objects.

```python
>>> class VarExample(NamespaceModel):
...   with_variables(Var("NODE_NAME", "!{BASE_NAME}-!{NODE_ID}"))
...   grid = (MultiRole(Role("worker", variables=[Var("NODE_ID", ctxt.name)]))
...            .add_variable(Var("BASE_NAME", "Grid")))
>>> ns = VarExample()
>>> ns.grid[5].var_value("NODE_NAME")
Grid-5
>>>
```

At the most global level, the NODE_NAME Var is defined with a value that contains two replacement parameter patterns. The first, BASE_NAME, is a Var defined on the grid MultiRole object, and has a value of 'Grid'. The second, NODE_ID, is defined on the Role managed by MultiRole, and has a value of _ctxt.name_. This context expression represents the name used to reach this role *when the expression is evaluated*. Context expressions aren't evaluated until they are used, and hence the value of this expression will depend on what node in the grid it is evaluated for. In this case, it is evaluateed for ns.grid[5], and hence ctxt.name will have a value of '5'. For each grid component created, the value of ctxt.name will match the key used in ns.grid[key].

It's also worth noting in the two different methods used to set Vars on namespace model roles or containers. In the first method, Vars can be set using the keyword argument "variables"; the value must be an iterable (list) of Var objects to set on the role. In the second method, Vars are added to a role container with the add_variable() method, which takes an arbitrary number of Var objects when called, separated by ','. The add_variable() method has a return value of the component the method was invoked on, and hence the value of VarExample.grid is still the MultiRole instance.

### Variable setting and overrides
Vars don't have to be defined when the namespace model class is defined; they can specified as having an empty value (*None* in Python), and that value can be provided later.

There are two ways to supply a missing Var value:
- The add_variables() method can be used to supply a Var to a role, role container, or model instance after the model has been defined. This is a "destructive" call in that if another Var with the same name (same first parameter value) already exists on the object, it will be replaced with the Var object in the add_variables() call.
- The add_override() method is similar to add_variables() in that it allows a new Var to be supplied after a model instance has been created, but unlike add_variables(), it saves the Var in an "override" area which is searched first when a variable name is required, leaving the original Var in tact. The override can be subsequently cleared out and any original Var values will then be visible.

## <a name="configmodels">Configuration models</a>

The configuration model is what instructs Actuator to do to the new provisioned infrastructure in order to make it ready to run application software. The configuration model has two main aspects:

1. A declaration of the tasks that need to be performed
2. A declaration of the dependencies between the tasks that will dictate the order of performance

Together, this provides Actuator the information it needs to perform all configuration tasks on the proper system roles in the proper order.

### <a name="taskdec">Declaring tasks</a>

Tasks must be declared relative to a Namespace and its Roles; it is the roles that inform the config model where the tasks are to ultimately be run. In the following examples, we'll use the this simple namespace that sets up a target role where some files are to be copied, as well as a couple of Vars that dictate where the files will go.

```python
class SimpleNamespace(NamespaceModel):
  with_variables(Var("DEST", "/tmp"),
                 Var("PKG", "actuator"),
                 Var("CMD_TARGET", "127.0.0.1"))
  copy_target = Role("copy_target", host_ref="!{CMD_TARGET}")
ns = SimpleNamespace()
```

We've established several Vars at the model level, one which includes a hard-coded IP to use for commands, in this case 'localhost', and a single component that will be the target of the files we want to copy. *NOTE*: Actuator uses [Ansible](https://pypi.python.org/pypi/ansible/1.7.2) under the covers for managing the execution of commands over ssh, and hence for this example to work it must be run on a *nix box that has appropriate ssh keys set up to allow for passwordless login.

Declaring tasks is a matter of creating one or more instances of various task classes which in many cases are Actuator analogs for Ansible modules. In this example, we'll declare two tasks: one which will remove any past files copied to the target (only really needed for non-dynamic hosts), and another that will copy the files to the target, in this case the Actuator package itself.

```python
import os, os.path
import actuator
from actuator import ConfigModel, CopyFileTask, CommandTask

#find the path to actuator; if it is under our cwd, the it won't be at an absolute path
actuator_path = actuator.__file__
if not os.path.isabs(actuator_path):
  actuator_path = os.path.join(os.getcwd(), "!{PKG}")
  
class SimpleConfig(ConfigModel):
  cleanup = CommandTask("clean", "/bin/rm -f !{PKG}", chdir="!{DEST}",
                        task_role=SimipleNamespace.copy_target)
  copy = CopyFileTask("copy-file", "!{DEST}", src=actuator_path,
                      task_role=SimpleNamespace.copy_target)
```

This config model is set up to run the cleanup and copy tasks on whatever host is identified by the value of the _task_role_ keyword argument. Note the use of replacement parameters in the various argument strings to the tasks; these will be evaluated against the available Vars visible to the namespace role identified by task_role.

Once a a config model has been created, it can be given to an execution agent for processing against a specific namespace:

```python
from actuator.exec_agents.ansible.agent import AnsibleExecutionAgent
cfg = SimpleConfig()
ea = AnsibleExecutionAgent(config_model_instance=cfg,
                           namespace_model_instance=ns)
ea.perform_config()
```

If all ssh keys have been set up properly, Actuator will be able to execute these tasks on the host of the role named with SimpleNamespace.copy_target. However, this isn't enough to get proper results, which will be discussed next.

### <a name="taskdeps">Declaring dependencies</a>

This is a fully functional config model, but there's a good chance it will give wrong or inconsistent results. The reason is that Actuator hasn't been told anything about the order of performing the config tasks. Hence, Actuator will perform these tasks in parallel, and the end result will simply depend on the relative scheduling timings of the ssh sessions set up for each task.

What we want to do is add dependency information to the model so that Actuator knows the proper order to perform the tasks. To do this, we use the with_dependencies() function and the '|' and '&' symbols to describe the dependencies between tasks. Adding this to the above config model, we would get the following:

```python
import os, os.path
import actuator
from actuator import ConfigModel, CopyFileTask, CommandTask

#find the path to actuator; if it is under our cwd, the it won't be at an absolute path
actuator_path = actuator.__file__
if not os.path.isabs(actuator_path):
  actuator_path = os.path.join(os.getcwd(), "!{PKG}")
  
class SimpleConfig(ConfigModel):
  cleanup = CommandTask("clean", "/bin/rm -f !{PKG}", chdir="!{DEST}",
                        task_role=SimipleNamespace.copy_target)
  copy = CopyFileTask("copy-file", "!{DEST}", src=actuator_path,
                      task_role=SimpleNamespace.copy_target)
  #NOTE: this call must be within the config model, not after it!
  with_dependencies( cleanup | copy )
```

Actuator uses some of the notation from [Celery](http://www.celeryproject.org/) to describe task dependencies. The pipe symbol '|' means perform the task on the left before the task on the right. This provides Actuator sufficient information to determine which task(s) to start with and what follows each as they complete. This will now provide repeatable results.

### <a name="depexp">Dependency expressions</a>

By using dependency expressions and the with_dependencies() function, dependency graphs of arbitrary complexity can be declared. For this next section, we'll assume a config model with 5 tasks in it, t1..t5. The following invocations of the with_dependencies() function will yield identical dependency graphs, where each task is done in series, and a task doesn't start until the one before it completes.

```python
with_dependencies( t1 | t2 | t3 | t4 | t5 )
#or 
with_dependencies( t1 | t2,
                   t2 | t3,
                   t3 | t4 | t5)
#or the following, which is two independent invocations of with_dependencies()
with_dependencies( t1 | t2 | t3 )
with_dependencies( t3 | t4 | t5 )
#or various combinations of the above
```

The with_dependencies() function can take any number of dependency expressions and be invoked any number of times. It will collect all dependency expressions from all the arguments and each invocation and assemble a dependency graph that instructs it how to perform the config model's tasks. All tasks that don't appear an any dependency expression are performed immedicately.

The above example illustrates how to arrange tasks in series, but what about tasks that can be performed in parallel? To indicate the eligibility of tasks to be performed in parallel, use the '&' operator in task dependency expressions. Using the same five tasks from above, the following would instruct Actuator to perform the identified tasks in parallel:

```python
#Perform t1 first, then t2 and t3 together, and then t4 and t5 serially
with_dependencies( t1 | (t2 & t3) | t4 | t5 )
#the same, but with implicit parallelism
with_dependencies( t1 | t2, t1 | t3, t2 | t4, t3 | t4, t4 | t5 )

#Perform t1 and t2 together, then t3, followed by t4 and t5 together
with_dependencies( (t1 & t2) | t3 | (t4 & t5) )
#the same, but with multiple expressions
with_dependencies( (t1 & t2) | t3, t3 | (t4 & t5) )
#the same, but with multiple invocations of with_dependencies
with_dependencies( (t1 & t2) | t3 )
with_dependencies( t3 | (t4 & t5) )

#Perform t1 then t2 in parallel with t3, all of which can be done in parallel with t4 then t5
with_dependencies( ((t1 | t2) & t3) & (t4 | t5) )

#Perform t1..t5 in parallel, but then remember that t1 has to be done before t4 and add that
#dependency in
with_dependencies( t1 & t2 & t3 & t4 & t5 )
with_dependencies( t1 | t4 )
#the same, but after fixing your original oversight
with_dependencies( (t1 | t4) & t2 & t3 & t5 )
```

As we can see, dependency expressions can be arbitrarily nested, and the expressions can be layered on additively to create complex relationships that can't be expressed with a single expression.

### <a name="taskscaling">Auto-scaling tasks</a>

For situations where there are multiple identical hosts that all requre the same configuration tasks, Actuator provides a means to identify the task to perform on each host and scale the number of tasks actually performed depending on how many hosts are in an instance of the model. The *MultiTask* container allows you to wrap another task and associate the wrapped task with a reference that names a group of hosts on which to perform the task.

To illustrate how this works, we'll introduce a new Namespace class that has a variable aspect to it:

```python
class GridNamespace(NamespaceModel):
  grid = MultiRole(Role("grid-node", host_ref=SomeInfra.grid[ctxt.name]))
  
  
class GridConfig(ConfigModel):
  reset = MultiTask("reset", CommandTask("remove", "/bin/rm -rf /some/path/*"),
                    GridNamespace.q.grid.all())
  copy = MultiTask("copy", CopyFileTask("copy-tarball', '/some/path/software.tgz',
                                        src='/some/local/path/software.tgz'),
                   GridNamespace.q.grid.all())
  with_dependencies(reset | copy)
```

In the above example, the Namespace model has a role container 'grid' that can grow to define an aribitrary number of roles. For each grid node, we want to clear out a directory and then transfer a tarball to be unpacked in that same directory. To do this flexibly, we wrap the task we want to run on a group of components in a MultiTask, providing a name for the MultiTask, a template task to apply to all the components, and then a list of components to apply the task to, in this case GridNamespacce.q.grid.all().

The 'q' attribute of GridNamespace is supplied by all Actuator model base classes. It signals the start of a _reference selection expression_, which is a logical expression that yields a list of references to elements of a model. In this case, the expression will make the template task apply to every grid role that is generated in the namespace. Reference selection expressions will be gone into in more deal below.

For the purposes of setting up dependencies, MultTasks can be treated like any other task; that is, they can appear in dependency expressions. The dependency system will ensure that all instances of the template task complete before the MultiTask itself completes.

### <a name="classtasks">Config classes as tasks</a>

MultiTasks make it easy to create configuration models that automatically scale relative to an instance of a namespace. However, MultiTasks may be limiting in some circumstances:

- Since the MultiTask can't finish until all of its template instances finish, overall progress may be slowed due to a single slow-completing task instance.
- Expressing complex dependencies in terms of MultiTask tasks can be subject to slow progress, again due to the completion requirement for each template instance inside each MultiTask.

What we would like is to be able to express a set of tasks and their dependencies, and then have the set of tasks be applied to a single host. If we could then wrap up such a representation in a MultiTask, we can have different components proceed through their complex set of config tasks at varying rates, allowing better ovverall progress even if one component is processing tasks slowly.

Fortunately, we already have a mechanism for modeling this situation: the config model itself! What is needed is to be able to treat a config model as if it were a task. To do that, we use the *ConfigClassTask* wrapper; this wrapper allows a config model to be used as if it was task, providing the means to define a set of tasks to be performed on a single role, all with their own dependencies.

To illustrate this, we'll re-write the above example with a ConfigClassTask to wrap up the operations that are all to be carried out on a single component:

```python
#this is the same namespace model as above
class GridNamespace(NamespaceModel):
  grid = MultiRole(Role("grid-node", host_ref=SomeInfra.grid[ctxt.name]))


#this config model is new; it defines all the tasks and dependencies for a single role
#Notice that there is no mention of a 'task_role' within this model
class NodeConfig(ConfigModel):
  reset = CommandTask("remove", "/bin/rm -rf /some/path/*")
  copy = CopyFileTask("copy-tarball', '/some/path/software.tgz',
                      src='/some/local/path/software.tgz')
  with_dependencies(reset | copy)
  

#this model now uses the NodeConfig model in a MultiTask to define all the tasks that need
#to be carried out on each role
class GridConfig(ConfigModel):
  setup_nodes = MultiTask("setup-nodes", ConfigClassTask("setup-suite", NodeConfig),
                          GridNamespace.q.grid.all())
```

In this example, the ConfigClassTask wrapper makes the NodeConfig model appear to be a plain task, and allows the MultiTask wrapper to create as many instances of NodeConfig as needed according to the the number of items that are returned by the reference selection expression, GridNamespace.q.grid.all().

The big operational difference here is that each "reset | copy" pipeline operates in parallel on each component named by GridNamespace.q.grid.all(). In the MultiTask example, all _resets_ had to complete before the first _copy_ could start on *any* role, but with ConfigClassTask, if one node finishes its _reset_ before another, that node's _copy_ task can start right away. This means that slow nodes don't slow down all work within the MultiTask. The MultiTask still won't complete until all of the ConfigClassTask instances complete, but overall progress will be less "lumpy" than if each MultiTask had to wait until the slowest task completed.

Notice that nowhere in the NodeConfig model is a _task_role_ identified. This is characteristic of models that are to be wrapped with ConfigClassTask-- the task_role will be externally supplied, and hence no reference is required within the model that is to be wrapped. Here, the MultiTask supplies the task_role value from the GridNamespace.q.grid.all() expression.

ConfigClassTask can be used independently of the MultiTask wrapper; it is a first-class task that can be expressed within a model and can enter into dependency expressions. When used this way, a task_role must be supplied to the ConfigClassTask, and this can be done in the normal way with the task_role keyword argument.

### <a name="refselect">Reference selection expressions</a>

In the above sections on the MultiTask and ConfigClassTask, the notion of referencce selection expressions was introduced. This section will go into these expressions in more detail an explain how they can be used to select references. Although their primary use is to select namespace model component references, these expressions can be used with any model to select a set of references for a variety of purposes.

As mentioned above, a reference selection expression is initiated by accessing the 'q' attribute on a model class. After the 'q', attributes of the model and its objects can be performed just as if you were doing so in the model class itself. However, instead of generating a single model reference, such accesses further define an expression that will yield a list of references into the model.

Each attribute access in a reference selection expression will yield either a single-valued attribute (such as a Role in a NamespaceModel), or a collection of values as represented by wrappers such as MultiRole or MultiRoleGroup. In this latter case, it is possible to restrict the set of references selected through the use of test methods which will filter out unwanted references in the collection. In either case, such references may be followed by further attribute accesses into the model, and attributes will be accessed only on the items selected to this point.

A contrived example will illustrate this; consider the following nested namespace model:

```python
class Contrived(NamespaceModel):
  top = MultiRole(MultiRoleGroup("site",
                                  leader=Role('leader'),
                                  grid=MultiRole(Role('grid-node'))))
```

Further, suppose we created an instance of this model and populated it by generating the references shown:

```python
con = Contrived()
for city in ["NY", "LN", "TK", "SG", "HK", "SF"]:
  for i in range(20):
    _ = con.top[city].grid[i]
```

We can then construct the following expressions to select lists of role references from this model instance:

```python
#list of leader Roles regardless of the instance of top
Contrived.q.top.all().leader

#1-element list of leader Role for the top['NY'] instance
Contrived.q.top.key("NY").leader

#list of all grid Roles under top['NY']
Contrived.q.top.key("NY").grid.all()

#list of all grid Roles under top["NY"], top["LN"] and top["TK"]
Contrived.q.top.keyin(["NY", "LN", "TK"]).grid.all()

#list of all leader Roles who's top key starts with 'S'
Contrived.q.top.match("S.*").leader

#list of all even numbered grid Roles for top["HK"]
def even_test(key):
  return int(key) % 2 == 0
Contrived.q.top.key("HK").grid.pred(even_test)

#list of the leader and all grid Roles for top["NY"]
Contrived.q.union(Contrived.q.top.key("NY").leader,
                  Contrived.q.top.key("NY").grid.all())
                  
#list of leaders where top key starts with S,
#and the key is in "NY", "LN" (in other words, an empty list)
Contrived.top.match("S.*").keyin(["NY", "LN"])
```

The following tests are available to filter out unwanted references:
- *all()* selects all items; this is actually the implicit action when naming an attribute that is a collection of items
- *key(string)* only selects the items whose key matches the supplied string
- *keyin(iterable)* only selects the items whose keys are in the supplied iterable of keys
- *match(regex_string)* only selects items whose key matches the supplied regex string
- *no_match(regex_string)* only selects items whose key doesn't match the supplied regex string
- *pred(callable)* only selects items for which the supplied callable returns True. The callable is supplied with one argument, the key of the item it to determine if it should be included.

