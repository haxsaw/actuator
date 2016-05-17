Hadoop 1.2.1 cluster model
==========================
IMPORTANT:

If you want to try running this with the keys provided, be sure to "chmod 600"
the "actuator-dev-key*" files first.

Also, if you want to base your provisioning of Hadoop on this example, be sure
to change the values of the keys if your instance will be in a public cloud!

=====================

This is an Actuator example that illustrates the use of Actuator in modeling a
Hadoop cluster of arbitrary size. While it doesn't configure every last corner
of Hadoop (for example, while SSH security is present, other Hadoop security is
ignored), it does illustrate a broad range of Actuator features in the
infra, namespace, and config modeling spaces.

1. Quick start; what you need to do first if you want to run this
2. Execution
3. Structure

1. Quick start; what you need to do first if you want to run this
==============================================================
Besides installing Actuator and its dependendencies, you also need to perform a
couple of prep steps to make the example work on your Openstack installation.
You should also review all tasks in the config models to ensure that none are
contraindicated in your situation.

SSH keys:
Make sure the permissions on the private key (actuator-dev-key) are 600!

User:
Actuator was developed on an Openstack site where a default user named "ubuntu"
was created for each server instance. You will probably need to change this
name to whatever default user your Openstack installation creates on new
servers. You can do this by modifying the value of the Var "USER" in
the hadoop_node.py module. NOTE: this user must have sudo permissions on new
instances otherwise some of the tasks will fail.

Environment vars:
The example looks for login info in environment variables (you'd probably want
to do this differently in an environment where security was an issue). These
variables are in the example file henv.sh. Set these for your installation and
source this script before running the example.

Hadoop install:
One of the tasks in the config model is to do a 'wget' on the Hadoop repository
to fetch the hadoop tarball. If you wish to fetch it somewhere else, you'll
need to adjust some of the Vars you'll find in hadoop_node.py. In particular,
look at HADOOP_VER, HADOOP_TARBALL, and HADOOP_URL. Bear in mind that the
rest of the model expects the paths that result from extracting the tarball,
so if you have your own packaging you may need to modify other Vars as well.

Unneeded commands:
The Openstack site used to develop Actuator has some older Ubuntu images that
need updating and Java to be installed. These tasks can be seen in the 
HadoopNodeConfig model in hadoop_node.py. If your setup doesn't require these
steps, comment out these tasks in that model, being sure to also eliminate
them from any dependency expressions (any good IDE will highlight references
to non-existant tasks being used in expressions).


2. Execution
============
Execution is pretty simple. Assuming you've taken care of matters noted in 1.
above, make sure that you've set the environment vars named in henv.sh with the
proper values. Once that's been done, run the example with:

python hrun.py

This will provision two servers, one for the name node and one slave. If you
want more slaves, add the number of slaves as an argument to hrun.py:

python hrun.py 7 #for seven slaves

Finally, you can get help for the required envs with

python hrun.py -h


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

