Actuator
========

Actuator allows you to use Python to declaratively describe system infra, configuration, and execution requirements, and then provision them in the cloud.

1. [Intro](#intro)
2. [Installing](#installing)
  1. [Basic](#basic)
  2. [IDE install](#ide)
3. [Requirements](#requirements)
  1. [Python version](#python)
  2. [Core packages](#core)
4. [Tutorial](#tutorial)
5. [Documentation](#docs)
6. [Hadoop Example](#hadoop)
7. Roadmap (yet to come)
8. [Contact](#contact)
9. [Acknowledgements](#hattips)

## <a name="intro">Intro</a>
**Current status**
- **12 Feb 2015:** Actuator can provision a limited set of items against Openstack clouds. It can create instances, networks, subnets, routers (plus router gateways and interfaces), and floating IPs. Not all options available via the Python Openstack client libraries are supported for each provisionable. Namespace models can drive the variable aspects of infra models successfully, and acquire information from the infra model such as IPs of a provisioned server. These can then be accessed by the configuration model, which has support of a small set of Ansible modules (specifically, ping, command, shell, script, and copy file), as well as a task that can process a template file through the namespace before it gets copied to a remote machine. Environment variables are populated from the namespace model for each configuration activity run on a remote system. Due to the direct dependency on Ansible, Actuator must itself run on a *nix box. A number of features over the Oct status have been added to make the environment more expressive.

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

## <a name="installing">Installing</a>
### <a name="basic">Basic</a>
The best way to try Actuator out is to create a virtual Python environment with [virtualenv](https://pypi.python.org/pypi/virtualenv) and then use pip to install Actuator into it (virtualenv will take care of installing pip for you). After you fetch virtualenv and install it into your global Python 2.7, you can create an "Actuator test" (at) environment under your home directory with the following command:

```
~/tmp$ virtualenv --no-site-packages ~/at
```

You then need to activate the environment to work in it; do that with the following shell command:

```
~/tmp$ source ~/at/bin/activate
```

This will change your shell command prompt to now be prepended with the name of your virtual environment, in this case '(at)'. Clone the Actuator project and cd into the project root (where the setup.py file is). There, run the following pip command to install Actuator into your virtual environment:

```
(at)~/tmp/actuator/$ pip install .
```

Now, while in your virtual environment, you can start Python and import Actuator:

```
(at)~/tmp/actuator$ python
Python 2.7.6 (default, Mar 22 2014, 22:59:56) 
[GCC 4.8.2] on linux2
Type "help", "copyright", "credits" or "license" for more information.
>>> from actuator import *
>>> 
```

When you're done playing around with Actuator, remember to deactivate your virtual env:

```
(at)~/tmp/actuator$ deactivate
~/tmp/actuator$
```

### <a name="ide">IDE install</a>
To get the full value of Actuator, you'll want to use it from an IDE. Once you have a virtual environment set up, most IDEs provide a way add additional Python interpreters to choose from when you start a project. You can add the interpreter from the virtual environment created above, and the IDE will then know all about Actuator.

The details vary from IDE to IDE, but there's lots of help on the web for this process. For instance, here are directions for adding interpreters to Eclipse using the PyDev plugin:

[http://pydev.org/manual_101_interpreter.html](http://pydev.org/manual_101_interpreter.html)

## <a name="requirements">Requirements</a>
###<a name="python">Python version</a>

Actuator has been developed against Python 2.7. Support for 3.x will come later.

###<a name="core">Core packages</a>

Actuator requires the following packages:

  - [networkx](https://pypi.python.org/pypi/networkx), 1.9 minimum
  - [ipaddress](https://pypi.python.org/pypi/ipaddress), 1.0.4 minimum
  - [fake_factory](https://pypi.python.org/pypi/fake-factory) (to support running tests), 0.4.2 minimum
  - [ansible](https://pypi.python.org/pypi/ansible/1.7.2), 1.7.2 minimum. Currently required for configuration tasks, but other config systems will be supported in the future
  - [subprocess32](https://pypi.python.org/pypi/subprocess32), 3.2.6 minimum. MUST BE IMPORTED BEFORE ANY ANSIBLE MODULES
  - [python_novaclient](https://pypi.python.org/pypi/python-novaclient), 2.18.1 minimum (for Openstack)
  - [python_neutronclient](https://pypi.python.org/pypi/python-neutronclient), 2.3.7 minimum (for Openstack)
  - [nose](https://pypi.python.org/pypi/nose), 1.3.4 minimum, for testing
  - [coverage](https://pypi.python.org/pypi/coverage), 3.7.1 minimum, for testing
  - [epydoc](https://pypi.python.org/pypi/epydoc), 3.0.1 minimum, documentation generation

## <a name="tutorial">Tutorial</a>
You can find a discussion of the basic concepts and an overview of the use of Actuator [here](Tutorial.md).

## <a name="docs">Documentation</a>
Currently, the only supplemental documentation are the epydoc-generated docs, the source html of which can be found
[here](doc/html). The root document is index.html.

## <a name="hadoop">Hadoop Example</a>
A more significant example of Actuator's use can be found in the examples directory. It is a set of models that describe setting up a Hadoop cluster with an arbitrary number of slave nodes. You can see the readme and associated example files
[here](src/examples/hadoop).

## <a name="contact">Contact</a>
You can write to me with questions at actuaor@pobox.com.

## <a name="hattips">Acknowledgements</a>
The following projects and people have provided inspiration, ideas, or approaches that are used in Actuator.

- [Elixir](http://elixir.ematia.de/trac/): Actuator's declarative style has been informed by Elixir's declarative ORM approach. Additionally, Actuator uses a similar mechanism to Elixir's for its "with_" functions that provide modifications to a modeling class (such as with_variables() and with_components()).
- [Celery](http://www.celeryproject.org/): Actuator has re-used some of Celery's notation for describing dependencies between tasks and other entities.
- [John Nolan](https://www.linkedin.com/pub/john-s-nolan/1/7/a8a), who provided a sounding board for ideas and spent time pairing on an initial implementation.
