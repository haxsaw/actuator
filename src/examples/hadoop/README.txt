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



3. Structure
============
The example is broken into three source files more to illustrate organizational
options than to serve some actual need. The overall model is held in hadoop.py,
while Vars and specific config tasks for a single node are in hadoop_node.py. The
overall example is run with hrun.py, while a single node can be run with
hadoop_node.py.

hadoop.py
---------
This module contains the main models: infra, namespace, and config. Some things
to note here are that some resources, namely the networking and basic security
resources, are factored out into some global ResourceGroups. They've been pulled
out of the model as they are boilerplate for a number of different models, and
as such they can easily be extracted to a global variable, or even an external
module, where they can easily be imported and reused. This makes the infra
model only contain the pieces that make it unique for this purpose.

Another thing to note is that the Vars used in the namespace are actually from
an external resource (they are imported from hadoop_node.py). This was done so that
it was easier to develop the single-node configuration model in a place where
it could be bench-tested on fixed infra during its development (more on this
below).

Finally, it's worth noting that the config model in this module includes a
MultiTask task that has a ConfigClassTask as its template. The ConfigClassTask
wraps the second config model that is used to setup any Hadoop node; this 
model is in hadoop_node.py The result of this is that the overall config model
is quite simple, and provides a quick overview of the config work needed to
stand up a node.

hadoop_node.py
--------------
This module contains three important features: the Vars that are used in the
namespace in hadoop.py as well as the development namespace, a config model for
a single Hadoop node, regardless of whether it is the name node or a slave,
and a "main" section and development namespace that allows the single node
config model to be developed and tested in isolation of the main model. This
last piece is a particularly useful pattern, as it shows how you can work though
getting your config tasks right without having to go through the trouble of 
provisioning some infra everytime you want to test something.

In particular note the values supplied to the HadoopNodeConfig instance being
created at the bottom; here, values such as user, task role, and private key
file can be specified for a model that otherwise doesn't have them.

Testing of the config model can be done simply by running:

python hadoop_node.py (hostname or ip)

Using a host that respects the SSH login user and keys provided.

hrun.py
-------
This module is the "main" for the example; it processes environment variables
and command line arguments, and then calls the "do_it()" function. Here is
where the use of the models and orchestrator take place, as well as where the
number of slaves is established.

