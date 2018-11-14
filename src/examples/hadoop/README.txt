Hadoop 1.2.1 cluster model
==========================

This is an Actuator example that illustrates the use of Actuator in modeling a
Hadoop cluster of arbitrary size. While it doesn't configure every last corner
of Hadoop (for example, while SSH security is present, other Hadoop security is
ignored), it does illustrate a broad range of Actuator features in the
infra, namespace, and config modeling spaces, tools for examining models, and
possible integrations to other systems.

1. Getting Started; what you need to do first if you want to run this
2. Execution
3. Structure

1. Getting Started; what you need to do first if you want to run this stuff
===========================================================================
Besides installing Actuator and its dependendencies, you also need to perform a
couple of prep steps to make the example works for the clouds on which you want to
run the demo.

You don't need all of the cloud credentials discussed below; you only need the ones
relevant to the cloud where you want to run the demo.

PYTHONPATH
----------
Be sure to set your path to cover where to find the 'actuator' package as well as the
path to the haddop demo directory.


Cloud Credentials
-----------------
OpenStack:
When trying to provision against OpenStack, Actuator uses a standard OpenStack package
called os-client-config that by default looks for a file named clouds.yml in the demo
directory for details on connecting to an OpenStack cloud. There is some variability
in what to fill in here, but the file clouds.yml-example shows how to do it for
CityCloud and Auro. The documentation for os-client-config provides more help.


AWS:
When trying to provision against AWS, the demo looks for a file name 'awscreds.txt'
in the demo directory that contains AWS cloud credentials. The file has a single line
which consists of account key, a '|' character, and then the secret key like so:

account_key|secret_key

These are the credentials used to contact AWS and manipulate the API.


Azure:
When trying to provision against Azure, the demo looks for a file named 'azurecreds.txt'
in the demo directory that contains Azure credentials. The file has a single line which
consists of four pieces of data separated by commas. The required data is the subscription id,
the client id, the secret, and tenant. The line should appear as follows:

subscription_id,client_id,secret,tenant


SSH keys used during configuration
----------------------------------
The demo uses the key pair actuator-dev-key/actuator-dev-key.pub for remotely accessing
provisioned instances in clouds. The private key must have permissions of 600 on Linux
to work properly. You can substitute your own keypairs if you wish, but if you don't want
to change the demo then the public and private files should be renamed as above.


User
----
The demo always starts an instance of Ubuntu server which has a user name of 'ubuntu' under
which all config activities are conducted. This user must exist, or otherwise the proper user
name must be supplied.


2. Execution
============
Basic Capabilities
------------------
The demo is interactive and provides a number of different functions that display various
Actuator capabilities. The simplest way to run the demo is to run hdemo.py:

    python hdemo.py

This will bring up an interactive prompt that provides the following functions. Only currently
available functions will be shown when prompted for input.

    f (forecast): Allows you to specify a number of slaves in your Hadoop cluster
                  and get a price forecast based on the resources required for each
                  of three different clouds (an Openstack, AWS, and Azure)
    n (namespace):Generates a namespace report for a Hadoop cluster of specified size.
                  Generally, it's best to only do a single slave in order to not be
                  swamped with repetitive output. Shows the namespace visible from
                  the perspective of each role in the namespace. If you have already
                  stood-up a system or loaded one from a file, the namespace report
                  will be generated from this system.
    u (security): Generates a security report for the type of cloud infra you specify.
                  The report shows the security groups, rules, and the entities the
                  groups are applied to. If you have already stood-up a system or loaded
                  one from a file, the security report will be generated from this system.
    l (load):     Loads the persisted state of a system from a file. This can be used to
                  deprovision the system at a later time or run one of the reports on
                  the system.
    s (standup):  Allows you to provision a Hadoop cluster on the cloud you select. You
                  can choose the number of slaves to create in the cluster and what
                  cloud the system should be built on.
    p (persist):  Only available after a system has been 'stood-up' or loaded. Prompts
                  for a file name and writes a JSON representation of the Actuator
                  state to the file. Can be loaded later using the load function.
    t (teardown): Causes the current system to be de-provisioned from the cloud where
                  it came from. You must have first either run the standup or load
                  functions. Teardown can be run repeatedly if there is a failure and
                  the entire system hasn't be torn down.
    r (retry):    In the case of a failure in standup , you can retry the standup with
                  same system model. Previous steps will be skipped and only the tasks
                  that remain unfinished will be performed.
    q (quit):     Exit the demo.


Additional Integrations
-----------------------
The hdemo.py program respects a number of command-line arguments that enable
additional integrations. If you want to do more than one integration, just concatenate
the flags as a single argument to hdemo.py, like 'mz'.


Mongo:
If you have Mongo running on the machine with the demo, then:

    python hdemo.py m

Will cause hdemo to store the post-stadnup JSON representation of a system into Mongo.
Queries against this structure can be made with the functions in hreport.py; run it
like so:

    python -i hreport.py

You can then get summaries of numbers of servers in each historical system, or the
active or terminated systems for a particular app (the app name to search for is 'hadoop').


Zabbix:
If you have a Zabbix instance handy, you can have the demo record information regarding
the provisioned instances in Zabbix and then have Zabbix monitor the instances. The
Zabbix agent is set up by the config model, but turing on this integration causes the
demo to notify Zabbix of the instances and start polling for monitoring information. Run
hdemo like:

    python hdemo.py z

For this to work, you also need to set two environment variables:

    ZABBIX_SERVER: This should be the public IP of the server. This is used to create
        a security rule on the cloud instance that only allows connections to the
        Zabbix agent from this IP. This can be the public IP of your NAT host.
    ZABBIX_PRIVATE: This should be the IP you'd use to contact Zabbix's API to tell
        it about new machines to monitor. This is generally a private IP address behind
        your firewall.

If you run 'hdemo.py z' without these environment variables it will complain and exit.


Visualisation:
If you run hdemo.py as follows:

    python hdemo.py v

AND you have Kivy set up properly, you can get a visualisation of the progress of provisioning
and configuration during standup and teardown. This option illustrates the possibilities
of integrating an external event system into Actuator during its automation processes. While
this shows a directly bound visualisation, the interface allows other kinds of interactions such
as sending messages to a remote system for storage or disply.

The big 'AND' is because setting Kivy up properly is a topic on it's own, and includes SDL2 and
Graphviz. Setting up Kivy will be addressed elsewhere.

If you do get Kivy setup, when you run either a standup or teardown a window will be
shown with a directed graph representing the tasks to perform in either an infrastructure
or configuration model. White nodes denote tasks yet to be performed, blue means tasks in
process, yellow means that there has been a non-fatal failure and the task will be retried,
green means the task is completed, and red means that the retry limit for the task has been
reached that the task has fatally failed, ceasing the automation.

You can also click on a node and get a description of what it is and any errors it currently
has.


3. Structure
============
The demo has been structured to illustrate a nummber of different Actuator features, and so
can be a source for guidance in a variety of uses.

One key feature is that while there are different infrastructure models that work with different
cloud platforms, the namespace and config models are the same regardless of the infra model. This
demonstrates the decoupling that Actuator enables in modeling, allowing changes in deployment
platform as needs dictate.

The demo is also structured to illustrate different approaches to use, from simple isolated
declarative models to highly modular approaches that emphasise reuse and integration into a
larger environment.


Key Modules
-----------
The key modules in the demo are as follows:

hcommon.py:
This module defines the common configuration and namespace models used in the demo, as well
as a few other common resources such as standard keypair names. It illustrates a number of
different features such as variable name substitution, using a config model as a task in
other models, and creating logical references to an infrastructure model from the namespace
to drive infra provisioning.

It also defines a class that is only useful to the demo itself, DemoPlatform: this class bundles
up the specific knowledge needed for each kind of cloud platform to allow it to run successfully.

hdemo.py:
This is the 'main program' of the demo. It brings together the models of hcommon with the specific
infra model of each cloud platform, and illustrates a variety of higher-level functions that
Actuator provices.

The main loop is structured to clearly illustrate the activities involved in carrying out each
function. This provides simple 'recipes' for performing these functions in other contexts.


Platform-specific models
------------------------
The following three modules illustrate increasing sophistication in the use of Actuator in modeling
and how the models can be used in broader contexts.

azurehadoop.py:
This defines a Hadoop infrastructure on the Azure platform. This model illustrates the simplest use
of Actuator, with all values for all model components specified directly in the model.

awshadoop.py:
This model defines Hadoop infrastructure on AWS. It is slightly more oomplex than the Azure model,
illustrating a technique for creating a base model where common components can be defined and
used, and a derived model that specifies the additional components required for the application
itself, which can refer to the components of the base model where needed.

openstackhadoop.py:
This is the most complex model and illustrates many additional capabilities of Actuator:

  - It shows the use of a component that can be brought in from outside the model (possibly
    imported from library module), external_connection and zabbix_agent_secgroup.
  - It shows the use of a function that can be used to dynamically create components,
    make_std_secgroup, as part of the definition of a model.
  - It shows the use of a function, get_flavor, which is a 'callale' object that can provide
    the value of a parameter. Such callables can acquire this value from any source, including
    sources available only via a web service call.
  - It shows how to use context expressions such as 'ctxt.nexus.ns.v.IMAGE' to tell the model
    how to acquire a parameter value from a variable in the namespace.


Supporting modules
------------------
Finally, the demo involves a number of supporting modules that illustrate various ways to
manipulate and access the model for a variety of purposes.

prices.py:
This module provides a static price source for the different cloud platforms to show how the
model can be inspected to look up prices for the model's components. This implementation
assumes a model that only has components for a single cloud platforrm, but it is possible
to create a more general version that accepts models with components from multiple platforms.

zabint.py:
This module provides simple integration with Zabbix, providing a way to add new hosts to monitor,
and to also delete those hosts so they will no longer be monitored.

hreport.py:
This module provides integration with Mongo. It provides functions that capture data for a running
system, an archive for all instances that have run over time, and some query functions for
looking up information on running or terminated systems.

hevent.py and hdisplay.py:
Together, these modules illustrate how an external object can be sent events during Actuator
orchestration operations to allow external systems do additional processes with these events.
hevent.py illustrates an object that implements the event protocol and passes along to a Kivy
app, while hdisplay.py shows the actual Kivy app that creates a visualisation of the events.
