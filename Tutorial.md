Actuator Tutorial
========

Actuator allows you to use Python to declaratively describe system infra, configuration, and execution requirements, and then provision them in the cloud.

1. [Intro](#intro)
2. [Overview](#overview) (as close to a tl;dr that's still meaningful)
  1. [Infra Model](#ov_inframodel)
  2. [Namespace Model](#ov_namespacemodel)
  3. [Configuration Model](#ov_configmodel)
  4. [Execution Model](#ov_execmodel)
3. [Infra Models](#inframodels)
  1. [A simple Openstack example](#simple_openstack_example)
  2. [Multiple Components](#multi_components)
  3. [Component Groups](#component_groups)
  4. [Model References and Context Expressions](#modrefs_ctxtexprs)
4. [Namespace Models](#nsmodels)
  1. [An example](#simplensexample)
  2. [Dynamic Namespaces](#dynamicns)
  3. [Var objects](#varobjs)
5. Configuration Models (yet to come)
6. Execution Models (yet to come)

## <a name="intro">Intro</a>

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

## <a name="overview">Overview</a>

Actuator splits the modeling space into four parts:

###<a name="ov_inframodel">Infra Model</a>

The *infra model*, established with a subclass of **InfraSpec**, defines all the cloud-provisionable infrastructure components of a system and their inter-relationships. Infra models can have fixed components that are always provisioned with each instance of the model class, as well as variable components that allow multiple copies of components to be easily created on an instance by instance basis. The infra model also has facilities to define groups of components that can be created as a whole, and an arbitrary number of copies of these groups can be created for each instance. References into the infra model can be held by other models, and these references can be subsequently evaluated against an instance of the infra model to extract data from that particular instance. For example, a namespace model may need the IP address from a particular server in an infra model, and so the namespace model may hold a reference into the infra model for the IP address attribute that yields the actual IP address of a provisioned server when an instance of that infra model is provisioned.

###<a name="ov_namespacemodel">Namespace Model</a>

The *namespace model*, established with a subclass of **NamespaceSpec**, defines a hierarchical namespace which defines all the names that are important to the run-time components of a system. Names in the namespace can be used for a variety of purposes, such as setting up environment variables, or establishing name-value pairs for processing template files such as scripts or properties files. The names in the namespace are organized into system components which map onto the executable software in a system, and each system component's namespace is composed of any names specific to that component, plus the names that are defined higher up in the namespace hierarchy. Values for the names can be baked into the model, supplied at model class instantiation, by setting values on the model class instnace, or can be acquired by resolving references to other models such as the infra model.

###<a name="ov_configmodel">Configuration Model</a>

The *configuration model*, established with a subclass of **ConfigSpec**, defines all the tasks to perform on the system components' infrastructure that make them ready to run the system's executables. The configuration model defines tasks to be performed on the logical system components of the namespace model, which in turn inidicates what infrastructure is involved in the configuration tasks. The configuration model also captures task dependencies so that the configuration tasks are all performed in the proper order.

###<a name="ov_execmodel">Execution Model</a>

The *execution model*, established with a subclass of **ExecutionSpec**, defines the actual processes to run for each system component named in the namespace model. Like with the configuration model, dependencies between the executables can be expressed so that a particular startup order can be enforced.

Each model can be built and used independently, but it is the inter-relationships between the models that give Actuator its representational power.

Actuator then provides a number of support objects that can take instances of these models and processes their informantion, turning it into actions in the cloud. So for instance, a provisioner can take an infra model instance and manage the process of provisioning the infra it describes, and another can marry that instance with a namespace to fully populate a namespace model instance so that the configurator can carry out configuration tasks, and so on.

As may have been guessed, the key model in Actuator is the namespace model, as it serves as the focal point to tie all the other models together.

##<a name="inframodels">Infra models</a>

Although the namespace model is the one that is most central in Actuator, it actually helps to start with the infra model as it not only is a little more accessible, but building an infra model first can yield immediate benefits. The infra model describes all the dynmaically provisionable infra components and describes how they relate to each other. The model can define groups of components and components that can be repeated an arbitrary number of times, allowing them to be nested in very complex configurations.

### <a name="simple_openstack_example">A simple Openstack example</a>
The best place to start is to develop a model that can be used to provision the infrastructure for a system. An infrastructure model is defined by creating a class that describes the infra in a declarative fashion. This example will use components built the [Openstack](http://www.openstack.org/) binding to Actuator.

```python
from actuator import InfraSpec, ctxt
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

class SingleOpenstackServer(InfraSpec):
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

Often, there's a lot of repeated boilerplate in an infra spec; in the above example the act of setting up a network, subnet, router, gateway, and router interface are all common steps to get access to provisioned infra from outside the cloud. Actuator provides two ways to factor out common component groups: providing a dictionary of components to the with_infra_components function, and using the [ComponetGroup](#component_groups) wrapper class to define a group of standard components. We'll recast the above example using with_infra_components():

```python
gateway_components = {"net":Network("actuator_ex1_net"),
                      "subnet":Subnet("actuator_ex1_subnet", ctxt.model.net,
                                      "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                      "router":Router("actuator_ex1_router"),
                      "gateway":RouterGateway("actuator_ex1_gateway", ctxt.model.router,
                                              "external"),
                      "rinter":RouterInterface("actuator_ex1_rinter", ctxt.model.router,
                                               ctxt.model.subnet)}


class SingleOpenstackServer(InfraSpec):
  with_infra_components(**gateway_components)
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
```

With with_infra_components(), all the keys in the dictionary are established as attributes on the infra model class, and can be accessed just as if they were declared directly in the class. Since this is just standard keyword argument notation, you could also use a list of "name=value" expressions for the same effect.

### <a name="multi_components">Multiple components</a>
If you require a set of identical components to be created in a model, the MultiComponent wrapper provides a way to declare a component as a template and then to get as many copies of that template stamped out as required:

<a name="multiservers">&nbsp;</a>
```python
from actuator import InfraSpec, MultiComponent, ctxt, with_infra_components
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

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
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex2_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
  #
  #finally, declare the workers MultiComponent
  #
  workers = MultiComponent(Server("worker", "Ubuntu 13.10", "m1.small",
                                  nics=[ctxt.model.net]))
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

### <a name="component_groups">Component Groups</a>

If you require a group of different resources to be provisioned as a unit, the ComponentGroup() wrapper provides a way to define a template of multiple resources that will be provisioned as a whole. The following example shows how the boilerplate gateway components could be expressed using a ComponentGroup().

```python
gateway_component = ComponentGroup("gateway", net=Network("actuator_ex1_net"),
                              subnet=Subnet("actuator_ex1_subnet", ctxt.comp.container.net,
                                          "192.168.23.0/24", dns_nameservers=['8.8.8.8']),
                              router=Router("actuator_ex1_router"),
                              gateway=RouterGateway("actuator_ex1_gateway", ctxt.comp.container.router,
                                                    "external")
                              rinter=RouterInterface("actuator_ex1_rinter", ctxt.comp.container.router,
                                                     ctxt.comp.container.subnet))


class SingleOpenstackServer(InfraSpec):
  gateway = gateway_component
  server = Server("actuator1", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.gateway.net])
  fip = FloatingIP("actuator_ex1_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
```

The keyword args used in creating the ComponentGroup become the attributes of the instances of the group.

If you require a group of different resources to be provisioned together repeatedly, the MultiComponentGroup() wrapper provides a way to define a template of multiple resources that will be provioned together. MultiComponentGroup() is simply a shorthand for wrapping a ComponentGroup in a MultiComponent. The following model only uses Servers in the template, but any component (including ComponentGroups and MultiComponents) can appear in a MultiComponentGroup.

<a name="multigroups">&nbsp;</a>
```python
from actuator import InfraSpec, MultiComponent, MultiComponentGroup, ctxt
from actuator.provisioners.openstack.components import (Server, Network, Subnet,
                                                         FloatingIP, Router,
                                                         RouterGateway, RouterInterface)

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
  foreman = Server("foreman", "Ubuntu 13.10", "m1.small", nics=[ctxt.model.net])
  fip = FloatingIP("actuator_ex3_float", ctxt.model.server,
                   ctxt.model.server.iface0.addr0, pool="external")
  #
  #finally, declare a "cluster"; a leader that coordinates the workers in the
  #cluster, which operate under the leader's direction
  #
  cluster = MultiComponentGroup("cluster",
                                leader=Server("leader", "Ubuntu 13.10", "m1.small",
                                              nics=[ctxt.model.net]),
                                workers=MultiComponent(Server("cluster_node",
                                                              "Ubuntu 13.10",
                                                              "m1.small",
                                                              nics=[ctxt.model.net])))
```

The keyword args used in creating the ComponentGroup become the attributes of the instances of the group; hence the following expressions are fine:

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

This model will behave similarly to the MultiServer attribute in the previous model; that is, the *cluster* attribute can be treated like a dictionary and keys will cause a new instance of the MultiComponentGroup to be created. Note also that you can nest MultiComponents in MultiComponentGroups, and vice versa.


### <a name="modrefs_ctxtexprs">Model References and Context Expressions</a>
A few of the examples above have shown that accessing model attributes results in a reference object of some sort. These objects are the key to declaratively relating aspects of various models to one another. For instance, a reference to the attribute that stores the IP address of a provisioned server can be used as the value of a variable in the namespace model, and once the IP address is known, the variable will have a meaningful value.

There are two different ways to get references to parts of a model: first through the use of _model references_, which are direct attribute accesses to model or model instance objects. This approach can only be used after a model class has already been created; this means that if a reference between class memebers is required in the middle of a class definition, model references aren't yet available, and hence can't be used.

The second method is through the use of _context expressions_. A context expression provides a way to express a reference to objects and models that don't exist yet-- the expression's evaluation is delayed until the reference it represents exists, and only then does the expression yield an actual reference.

#### Model References

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

All of these expressions result in a reference object, either a model reference or a model instance reference. _References_ are objects that serve as a logical "pointer" to a component or attribute of an infra model. _Model references_ are logical references into an infra model; there may not be an actual component or attribute underlying the reference. _Model instance references_ (or "instance references") are references into an _instance_ of an infra model; they refer to an actual component or attribute (although the value of the attribute may not have been set yet). Instance references can only be created relative to an instance of a model, or by transforming a model reference to an instance reference using an instance of a model. An example here will help:

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

The RouterGateway and RouterInterface components both require a model reference to a Router component as their second argument. Now, after the SingleOpenstackServer class is defined, this reference would be easy to obtain with an expression such as SingleOpenstackServer.router. However, within the class defintion, the class object doesn't exist yet, and so trying to use an expression like:

```python
  gateway = RouterGateway("actuator_ex1_gateway", SingleOpenstackServer.router, "external")
```

will yield a NameError exception saying that "SingleOpenstackServer" is not defined.

This is where context expressions come in. Every time a component in a model is processed by Actuator, a processing context is created. The _context_ wraps up:

- the instance of the model the component is part of,
- the component itself,
- and the name of the component.

In a model class, the context is referred to by the global object *ctxt*, and the above three objects can be accessed via ctxt in the following way:

- the model instance can be accessed via _ctxt.model_
- the component itself can be accessed via _ctxt.comp_
- the component's name can be accessed via _ctxt.name_

## <a name="nsmodels">Namespace models</a>
The namespace model provides the means for joining the other Actuator models together. It does this by declaring the logical components of a system, relating these components to the infrastructure elements where the components are to execute, and providing the means to identify what configuration task is to be carried out for each component as well as what executables are involved with making the component function.

A namespace model has four aspects. It provides the means to:

1. ...define the logical execution components of a system
2. ...define the relationships between logical components and hosts in the infra model where the components are to execute
3. ...arrange the components in a meaningful hierarchy
4. ...establish names within the hierachy whose values will impact configuration activities and the operation of the components

### <a name="simplensexample">An example</a>
Here's a trivial example that demonstrates the basic features of a namespace. It will model two components, an app server and a computation engine, and use the SingleOpenstackServer infra model from above for certain values:

```python
from actuator import Var, NamespaceSpec, Component, with_variables

class SOSNamespace(NamespaceSpec):
  with_variables(Var("COMP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0),
                 Var("COMP_SERVER_PORT", '8081'),
                 Var("EXTERNAL_APP_SERVER_IP", SingleOpenstackServer.fip.ip),
                 Var("APP_SERVER_PORT", '8080'))
                 
  app_server = (Component("app_server", host_ref=SingleOpenstackServer.server)
                  .add_variable(Var("APP_SERVER_HOST", SingleOpenstackServer.server.iface0.addr0)))
                                
  compute_server = Component("compute_server", host_ref=SingleOpenstackServer.server)
```

First, some global Vars are established that capture the host and port where the compute_server will be found, the external IP where the app_server will be found, and the port number where it can be contacted. While the ports are hard coded values, the host IPs are determined from the SingleOpenstackServer model by creating a model reference to the model attribute where the IP will become available. Since these Vars are defined at the model (global) level, they are visible to all components.

Next comes the app_server component, which is declared with a call to Component. Besides a name, Component is supplied a host_ref in the form of Server model reference from the SingleOpenstackserver model. This tells the namespace that this component's configuration tasks and executables will be run on whatever host is provisioned for this part of the model. The app_server component is also supplied a private Var object that captures the host IP where the server will run. While the app_server binds to an IP on the subnet, the FloatingIP associated with this subnet IP will enable the server to be reached from outside the subnet.

Finally, we declare the compute_server Component. Similar to the app_server Component, the compute_server Component identifies the Server where it will run by setting the host_ref keyword to a infra model reference for the Server to use. In this example, both Components will be run on the same server.

When an instance of the namespace is created, useful questions can be posed to the instance:
* We can ask for a list of components
* We can ask for all the Vars (and their values) from the perspective of a specific component
* We can identify any Vars whose value can't be resolved from the perspective of each component
* We can ask to compute the necessary provisioning based on the namespace and an infra model instance

That looks something like this:
```python
>>> sos = SingleOpenstackServer("sos")
>>> ns = SOSNamespace()
>>> for c in ns.get_components.values():
...     print "Component: %s, Vars:" % c.name
...     for v in c.get_visible_vars().values():
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

Actuator allows for more dynamic namespaces to be constructed, in particular in support of arbitrary numbers of components. By coupling such a namespace with an infra model that uses MultiComponent or MultiComponentGroup elements, appropriately sized infra can be identified and provisioned depending on the nature of the dynamic namespace.

The best way to understand this is with an example. We'll devise a trivial computational grid: besides the normal gateway elements, the infrastructure will contain a "foreman" to coordinate the computational activities of a variable number of "workers", each on a seperate server.

The [MultipleServers](#multiservers) infra model from above fits this pattern, so we'll define a dynamic namespace model that grows components that refer back to this infra model in order to acquire the appropriate infrastructure to meet the namespace's needs.

We'll use two different techniques for creating a suitable dynamic namespace. In the first, we'll create a class factory function that defines a new namespace class with the appropriate number of worker Components. In the second, we'll use some additional features of Actuator to express the same capabilities in a more concise way.

First, the class factory approach:

```python
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
```

Making a dynamic namespace class in Python is trivial; by simply putting the class statement inside a function, each call to the function will generate a new class. By supplying parameters to the function, the content of the class can be altered.

In this example, after setting some global Vars in the namespace with the with_variables() function, we next create the "foreman" component, and use host_ref to associate it with a server in the infra model. Next, we set up a dictionary whose keys will eventually become other attributes on the class, and whose values will become the associated Components for those attributes. In a for loop, we then simply create new instances of Component, associating each with a different worker in the MultipleServers infra model (host_ref=MultipleServers.workers[i]). We then use the function *with_components()* to take the content of the dict and attach all the created components to the namespace class. The class finishes by deleting the unneeded dict and lambda function. The factory function completes by returning an instance of the class that was just defined.

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

Now the second approach, which utilizes some other capabilities of Actuator. Namespaces have their own analogs to the infra model's ComponentGroup, MultiComponent, and MultiComponentGroup classes: they are NSComponentGroup, NSMultiComponent, and NSMultiComponentGroup. These are similar to their infrastructure counterparts with the exceptions that

1. They can contain only Components or the various NS* Component containers mentinoed above;
2. They can have variables (Var objects) attached to them.

Using this approach, the solution looks like the following:

```python
class GridNamespace(NamespaceSpec):
  with_variables(Var("FOREMAN_EXTERNAL_IP", MultipleServers.fip.ip),
                 Var("FOREMAN_INTERNAL_IP", MultipleServers.foreman.iface0.addr0),
                 Var("FOREMAN_EXTERNAL_PORT", "3000"),
                 Var("FOREMAN_WORKER_PORT", "3001"))
                  
  foreman = Component("foreman", host_ref=MultipleServers.foreman)
  
  grid = NSMultiComponent(Component("node", host_ref=ctxt.model.infra.workers[ctxt.name]))
```

This approach doesn't use a factory; instead, it uses NSMultiComponent to define a "template" Component object to create instances from each new key supplied to the "grid" attribute of the namespace. After defining a namespace class this way, one simply creates instances of the class and then, in a manner similar to creating new components on an infra model, uses new keys to create new Components on the instance. These new component instances will in turn create new worker instances on a MultiServers model instance:

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

Using this approach, we can treat the namespace model like the infra model, meaning that we can provide a logical definition of components and drive the creation of physical components simply by referencing them. These references flow through to the infra model, likewise causing dynamic infra components to be created.

### <a name="varobjs">Var objects</a>
Namespaces and their components serve as containers for *Var* objects. These objects provide a means to establish names that can be used symbolically for a variety of purposes, such as environment variables for tasks and executables, or parameter maps for processing templatized text files such as scripts or properties files.

Vars associate a 'name' (the first parameter) with a value (the second parameter). The value parameter of a Var can be one of several kinds of objects: it may be a plain string, a string with a replacement paremeter in it, or a reference to an infra model element.

We've seen 
