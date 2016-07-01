# 
# Copyright (c) 2015 Tom Carroll
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

"""
Internal to Actuator; responsible for processing Openstack resource objects
"""
import time
import threading
import uuid
import string

from actuator.modeling import AbstractModelReference
from actuator.task import TaskEngine, GraphableModelMixin, Task
from actuator.provisioners.openstack import openstack_class_factory as ocf
from actuator.provisioners.core import BaseProvisioner
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.support import (_OSMaps,
                                                     OpenstackProvisioningRecord)
from actuator.utils import (capture_mapping, get_mapper, root_logger, LOG_INFO)
from errator import (narrate, narrate_cm, get_narration, reset_narration)

_rt_domain = "resource_task_domain"


class RunContext(object):
    def __init__(self, record, os_creds):
        assert isinstance(os_creds, OpenstackCredentials)
        self.os_creds = os_creds
        self.record = record
        self.maps = _OSMaps(self)

    @property
    @narrate("I was trying to load the cloud definitions file")
    def cloud(self):
        if self.os_creds.cloud_name:
            cloud = ocf.get_shade_cloud(self.os_creds.cloud_name,
                                        config_files=self.os_creds.config_files)
        else:
            cloud = None
        return cloud


class ProvisioningTask(Task):
    clone_attrs = False
    _rsrc_by_id = {}
    
    def __init__(self, rsrc, repeat_count=1):
        super(ProvisioningTask, self).__init__("{}_provisioning_{}_task"
                                               .format(rsrc.name,
                                                       rsrc.__class__.__name__),
                                               repeat_count=repeat_count)
        self._rsrc_by_id[rsrc._id] = rsrc
        self.rsrc_id = rsrc._id

    def get_performance_status(self):
        rsrc = self._rsrc_by_id.get(self.rsrc_id)
        if not rsrc:
            raise ProvisionerException("get_performance_status can't find resource %s by id while trying to determine its performance_status"
                                       % self.rsrc_id)
        return rsrc.get_performance_status()

    def set_performance_status(self, status):
        rsrc = self._rsrc_by_id.get(self.rsrc_id)
        if not rsrc:
            raise ProvisionerException("set_performance_status can't find resource %s by id while trying to determine its performance_status" % self.rsrc_id)
        rsrc.set_performance_status(status)

    def _get_rsrc(self):
        return self._rsrc_by_id[self.rsrc_id]
    
    rsrc = property(_get_rsrc)
    
    def get_ref(self):
        return AbstractModelReference.find_ref_for_obj(self.rsrc)
        
    def depends_on_list(self):
        return []
    
    def _perform(self, engine):
        """
        override this method to perform the actual provisioning work. there is
        no return value
        """
        return
    
    def _reverse(self, engine):
        return
    
    def get_init_args(self):
        return (self.rsrc,), {"repeat_count": self.repeat_count}


@capture_mapping(_rt_domain, Network)
class ProvisionNetworkTask(ProvisioningTask):
    @narrate(lambda s, _: "I started the provisioning task for the network {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        with narrate_cm("...and tried to create the network"):
            response = run_context.cloud.create_network(self.rsrc.get_display_name(),
                                                        admin_state_up=self.rsrc.admin_state_up)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_network_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "I started the de-prov task for the network {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        netid = self.rsrc.osid
        with narrate_cm("...and tried to delete the network"):
            run_context.cloud.delete_network(netid)
        
        
@capture_mapping(_rt_domain, Subnet)
class ProvisionSubnetTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.network]
                if isinstance(self.rsrc.network, Network)
                else [])

    @narrate(lambda s, _: "I started the provisioning task for the subnet {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        with narrate_cm("...and tried to created the subnet"):
            response = run_context.cloud.create_subnet(self.rsrc._get_arg_msg_value(self.rsrc.network,
                                                                                    Network,
                                                                                    "osid",
                                                                                    "network"),
                                                       self.rsrc.cidr, ip_version=self.rsrc.ip_version,
                                                       subnet_name=self.rsrc.get_display_name(),
                                                       dns_nameservers=self.rsrc.dns_nameservers,
                                                       enable_dhcp=True)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_subnet_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "I started the de-prov task for the subnet {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        # this may not be needed as the subnet may go with the network
        subnet_id = self.rsrc.osid
        run_context.cloud.delete_subnet(subnet_id)


@capture_mapping(_rt_domain, SecGroup)
class ProvisionSecGroupTask(ProvisioningTask):
    """depends on nothing"""

    # @FIXME: this lock and its use are due to an apparent thread-safety issue
    # down in the novaclient. It would seem that even if there are different
    # client objects being used in different threads to build security groups,
    # nova has some shared state that gets hosed and causes one or the other to
    # fail if they're happening at the same time. For now, this lock will ensure
    # single-threaded operation of this trouble code, and hopefully we can get
    # a bug filed and the problem resolved soon.

    _sg_create_lock = threading.Lock()

    @narrate(lambda s, _: "I started the provisioning task for the security group {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        with self._sg_create_lock:
            # @FIXME: this lock is because nova isn't threadsafe for this
            # call, and until it is we have to single-thread through it
            with narrate_cm("So I tried to create the security group"):
                response = run_context.cloud.create_security_group(name=self.rsrc.get_display_name(),
                                                                   description=self.rsrc.description)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "I started the de-prov task for the security group {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        secgroup_id = self.rsrc.osid
        with narrate_cm("...and tried to delete the security group"):
            run_context.cloud.delete_security_group(secgroup_id)


@capture_mapping(_rt_domain, SecGroupRule)
class ProvisionSecGroupRuleTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.secgroup]
                if isinstance(self.rsrc.secgroup, SecGroup)
                else [])

    @narrate(lambda s, _: "I started the provisioning task for the security group rule {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        sg_id = self.rsrc._get_arg_msg_value(self.rsrc.secgroup,
                                             SecGroup,
                                             "osid", "secgroup")
        with narrate_cm("And then tried to create the security group"):
            response = run_context.cloud.create_security_group_rule(sg_id,
                                                                    port_range_min=self.rsrc.from_port,
                                                                    port_range_max=self.rsrc.to_port,
                                                                    protocol=self.rsrc.ip_protocol,
                                                                    remote_ip_prefix=self.rsrc.cidr)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_rule_id(self.rsrc._id, self.rsrc.osid)
        
    # NO _reverse required; the rules should follow the secgroup


@capture_mapping(_rt_domain, Server)
class ProvisionServerTask(ProvisioningTask):
    def depends_on_list(self):
        return ([i for i in self.rsrc.security_groups
                if isinstance(i, SecGroup)] +
                [j for j in self.rsrc.nics
                 if isinstance(j, Network)] +
                ([self.rsrc.key_name]
                 if isinstance(self.rsrc.key_name, KeyPair)
                 else []))

    def _process_server_addresses(self, addr_dict):
        self.rsrc.set_addresses(addr_dict)
        for i, (k, v) in enumerate(addr_dict.items()):
            iface = getattr(self.rsrc, "iface%d" % i)
            iface.name = k
            for j, iface_addr in enumerate(v):
                setattr(iface, "addr%d" % j, iface_addr['addr'])

    @narrate(lambda s, _: "I started the provisioning task for the server {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        with narrate_cm("I tried to refresh the list of images that I can use"):
            run_context.maps.refresh_images()
        with narrate_cm("I tried to refresh the list of os flavors I can use"):
            run_context.maps.refresh_flavors()
        with narrate_cm("I tried to refresh the list of networks that exist"):
            run_context.maps.refresh_networks()

        with narrate_cm("I tried to get the already-fixed arguments to the server"):
            args, kwargs = self.rsrc.get_fixed_args()
        _, image_name, flavor_name = args
        with narrate_cm("I tried to get the display name of the server"):
            name = self.rsrc.get_display_name()
        image = run_context.maps.image_map.get(image_name)
        if image is None:
            raise ProvisionerException("Image %s doesn't seem to exist" % image_name,
                                       record=run_context.record)
        flavor = run_context.maps.flavor_map.get(flavor_name)
        if flavor is None:
            raise ProvisionerException("Flavor %s doesn't seem to exist" % flavor_name,
                                       record=run_context.record)
        secgroup_list = []
        if self.rsrc.security_groups:
            with narrate_cm("I tried to refresh the list of existing security groups"):
                run_context.maps.refresh_secgroups()
            for sgname in self.rsrc.security_groups:
                sgname = self.rsrc._get_arg_msg_value(sgname, SecGroup, "osid", "sec group name/id")
                sg = run_context.maps.secgroup_map.get(sgname)
                if sg is None:
                    raise ProvisionerException("Security group %s doesn't seem to exist" % sgname,
                                               record=run_context.record)
                secgroup_list.append(sg["id"])
            kwargs["security_groups"] = secgroup_list
            
        nics_list = []
        if self.rsrc.nics:
            for nicname in self.rsrc.nics:
                nicname = self.rsrc._get_arg_msg_value(nicname, Network, "osid", "network name/id")
                nic = run_context.maps.network_map.get(nicname)
                if nic is None:
                    raise ProvisionerException("NIC %s doesn't seem to exist" % nicname,
                                               record=run_context.record)
                nics_list.append({'net-id': nic["id"]})
            kwargs['nics'] = nics_list
            
        if isinstance(kwargs["key_name"], KeyPair):
            kwargs["key_name"] = kwargs["key_name"].get_key_name()

        with narrate_cm("After getting all the arguments ready, I tried to create the server"):
            srvr = run_context.cloud.create_server(name, image, flavor, **kwargs)
        self.rsrc.set_osid(srvr["id"])
        run_context.record.add_server_id(self.rsrc._id, self.rsrc.osid)
        
        # while not srvr.addresses:
        with narrate_cm("After creating the server, I'm trying to get its addresses so I know I can finish processing"):
            while not srvr["addresses"]:
                time.sleep(0.25)
                srvr = run_context.cloud.get_server(srvr["id"])
        with narrate_cm("Finally, I'm processing the server's addresses"):
            self._process_server_addresses(srvr["addresses"])

    @narrate(lambda s, _: "I'm starting the de-prov task for the server {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        run_context.cloud.delete_server(self.rsrc.osid)

                
@capture_mapping(_rt_domain, Router)
class ProvisionRouterTask(ProvisioningTask):
    # depends on nothing

    @narrate(lambda s, _: "I started the provisioning task for the router {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        with narrate_cm(lambda r: "Then I tried to actually create the router {}".format(r.get_display_name()),
                        self.rsrc):
            reply = run_context.cloud.create_router(name=self.rsrc.get_display_name(),
                                                    admin_state_up=self.rsrc.admin_state_up)
        self.rsrc.set_osid(reply["id"])
        run_context.record.add_router_id(self.rsrc._id, self.rsrc.osid)

    @narrate(lambda s, _: "I started the de-prov task for the router {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc.osid
        with narrate_cm(lambda rid: "and then tried to delete the router with osid {}".format(rid),
                        router_id):
            run_context.cloud.delete_router(router_id)


@capture_mapping(_rt_domain, RouterGateway)
class ProvisionRouterGatewayTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.router]
                if isinstance(self.rsrc.router, Router)
                else [])

    @narrate(lambda s, _: "I started the provisioning task for the the router gateway {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm("First I have to refresh the network maps"):
            run_context.maps.refresh_networks()
        ext_net = run_context.maps.network_map.get(self.rsrc.external_network_name)
        with narrate_cm(lambda nid: "Then I tried to update the router with the gateway id {}".format(nid),
                        ext_net["id"]):
            run_context.cloud.update_router(router_id, ext_gateway_net_id=ext_net["id"])
        
    # no reversing; assume it goes with the router


@capture_mapping(_rt_domain, RouterInterface)
class ProvisionRouterInterfaceTask(ProvisioningTask):
    def depends_on_list(self):
        deps = []
        if isinstance(self.rsrc.router, Router):
            deps.append(self.rsrc.router)
        if isinstance(self.rsrc.subnet, Subnet):
            deps.append(self.rsrc.subnet)
        return deps

    @narrate(lambda s, _: "I started the provisioning task for router interface {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm(lambda rid: "First I looked up the router with osid {}".format(rid),
                        router_id):
            router = run_context.cloud.get_router(router_id)
        snid = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        with narrate_cm(lambda s, r: "Then I tried to add a router interface to router {} for "
                                     "subnet {}".format(r, s),
                        snid, str(router)):
            response = run_context.cloud.add_router_interface(router, subnet_id=snid)
        self.rsrc.set_osid(response[u'port_id'])
        run_context.record.add_router_iface_id(self.rsrc._id, response[u'port_id'])

    @narrate(lambda s, _: "I started the de-prov task for the router interface {}".format(s.rsrc.name))
    def _reverse(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        with narrate_cm(lambda r: "First I tried to look up the router with osid {}".format(r),
                        router_id):
            router = run_context.cloud.get_router(router_id)
        snid = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        with narrate_cm(lambda s, r: "Then I tried to remove the interface for router {} "
                                     "to subnet {}".format(r, s),
                        str(router), snid):
            run_context.cloud.remove_router_interface(router, subnet_id=snid)


@capture_mapping(_rt_domain, FloatingIP)
class ProvisionFloatingIPTask(ProvisioningTask):
    def depends_on_list(self):
        return [self.rsrc.server] if isinstance(self.rsrc.server, Server) else []

    @narrate(lambda s, _: "I started the provisioning task for floating ip {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        self.rsrc._refix_arguments()
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            with narrate_cm(lambda s: "I tried to server {} to associate it with the ip".format(s),
                            servername):
                server = run_context.cloud.get_server(servername)
        else:
            server = None
        with narrate_cm(lambda s, p: "and then I tried to create the floating ip on pool {} for server {}"
                                     .format(p, str(s)),
                        self.rsrc.pool, str(server)):
            fip = run_context.cloud.create_floating_ip(network=self.rsrc.pool, server=server)
        self.rsrc.set_addresses(fip["floating_ip_address"])
        self.rsrc.set_osid(fip["id"])
        run_context.record.add_floating_ip_id(self.rsrc._id, self.rsrc.osid)

    def _reverse(self, engine):
        run_context = engine.get_context()
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            run_context.cloud.detach_ip_from_server(servername, self.rsrc.osid)
        run_context.cloud.delete_floating_ip(self.rsrc.osid)

            
@capture_mapping(_rt_domain, KeyPair)
class ProvisionKeyPairTask(ProvisioningTask):
    # KeyPairs depend on nothing

    @narrate(lambda s, e: "I started the provisioning task for keypair {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
        name = self.rsrc.get_key_name()
        if self.rsrc.pub_key_file is not None:
            try:
                public_key = open(self.rsrc.pub_key_file, "r").read()
            except Exception, e:
                raise ProvisionerException("Couldn't open/read the public key file %s "
                                           "for KeyPair %s; %s" % (self.rsrc.pub_key_file,
                                                                   self.rsrc.name,
                                                                   e.message))
        else:
            public_key = self.rsrc.pub_key
        run_context.maps.refresh_keypairs()
        kp = run_context.maps.keypair_map.get(name)
        if kp is not None:
            if self.rsrc.force:
                with narrate_cm("and since it was a forced create, I tried deleting the existing keypair first"):
                    run_context.cloud.delete_keypair(name)
                with narrate_cm("and after deleting the existing keypair (it was a forced create), I tried "
                                "creating the keypair"):
                    run_context.cloud.create_keypair(name, public_key)
        else:
            with narrate_cm("I started crearting a new key pair"):
                run_context.cloud.create_keypair(name, public_key)


class OpenstackCredentials(object):
    def __init__(self, cloud_name=None, config_files=None):
        self.cloud_name = cloud_name
        self.config_files = config_files


class ResourceTaskSequencerAgent(TaskEngine, GraphableModelMixin):
    no_punc = string.maketrans(string.punctuation, "_"*len(string.punctuation))
    exception_class = ProvisionerException
    exec_agent = "rsrc_provisioner"
    repeat_count = 3

    def __init__(self, infra_model, os_creds, num_threads=5, log_level=LOG_INFO,
                 no_delay=True):
        self.logger = root_logger.getChild("os_prov_agent")
        self.infra_model = infra_model
        super(ResourceTaskSequencerAgent, self).__init__("{}-engine".format(infra_model.name),
                                                         self,
                                                         num_threads=num_threads,
                                                         log_level=log_level,
                                                         no_delay=no_delay)
        self.run_contexts = {}  # keys are threads, values are RunContext objects
        self.record = OpenstackProvisioningRecord(uuid.uuid4())
        self.os_creds = os_creds
        self.rsrc_task_map = {}

    @narrate("I was asked to collect the tasks involved in provisioning the resources")
    def get_tasks(self):
        """
        Returns a list of all the tasks for provisioning the resources
        
        Looks to the resources in the infra_model and creates appropriate
        tasks to provision each. Returns a list of the created tasks. A new
        list with the same task will be returned for subsequent calls.
        Raises an exception if a task can't be determined for a resource.
        
        @raise ProvisionerException: Raised if a resource is found for which
            there is no corresponding task.
        """
        with narrate_cm("I started by looking in the infra model for all the components that I have to provision"):
            all_resources = set(self.infra_model.components())
        tasks = []
        self.logger.info("%s resources to provision" % len(all_resources))
        with narrate_cm(lambda dname: "Now I'm getting the resource to task mapper for task domain {}".format(dname),
                        _rt_domain):
            class_mapper = get_mapper(_rt_domain)
        for rsrc in all_resources:
            if rsrc in self.rsrc_task_map:
                tasks.append(self.rsrc_task_map[rsrc])
                continue
            rsrc.fix_arguments()
            with narrate_cm(lambda cls: "I was looking for the task class for resource class {}".format(cls.__name__),
                            rsrc.__class__):
                task_class = class_mapper.get(rsrc.__class__)
                if task_class is None:
                    ref = AbstractModelReference.find_ref_for_obj(rsrc)
                    path = ref.get_path() if ref is not None else "NO PATH"
                    raise self.exception_class("Could not find a task for resource "
                                               "%s named %s at path %s" %
                                               (rsrc.__class__.__name__,
                                                rsrc.name, path))
            task = task_class(rsrc, repeat_count=self.repeat_count)
            tasks.append(task)
            self.rsrc_task_map[rsrc] = task
        return tasks

    @narrate("Then I started to get the dependencies between the resources")
    def get_dependencies(self):
        """
        Returns a list of _Dependency objects for the tasks in the model
        
        This method creates and returns a list of _Dependency objects that
        represent the dependencies in the resource provisioning graph. If the
        method comes across a dependent resource that wasn't represented by
        the tasks returned by get_tasks(), an exception is raised.
        
        @raise ProvisionerException: Raised if a dependency is discovered that
            involves a resource not considered by get_tasks()
        """
        # now, self already contains a rsrc_task_map, but that's meant to be
        # used as a cache for multiple calls to get_tasks so that the tasks
        # returned are always tghe same. However, we can't assume in this
        # method that get_tasks() has already been called, or that doing
        # so causes the side-effect that self.rsrc_task_map gets populated
        # (or that it even exists). So we get the tasks and construct our own
        # map, just to be on the safe side.
        rsrc_task_map = {task.rsrc: task for task in self.get_tasks()}
        dependencies = []
        for rsrc, task in rsrc_task_map.items():
            for d in task.depends_on_list():
                with narrate_cm(lambda r:
                                "I checked to see if resource {}, class {} is in my set of known resources"
                                .format(r.name, r.__class__.__name__), rsrc):
                    if d not in rsrc_task_map:
                        ref = AbstractModelReference.find_ref_for_obj(d)
                        path = ref.get_path() if ref is not None else "NO PATH"
                        raise self.exception_class("Resource {} named {} path {}"
                                                   " says it depends on {}, "
                                                   "but the latter isn't in the "
                                                   "list of all components"
                                                   .format(rsrc.__class__.__name__,
                                                           rsrc.name, path,
                                                           d.name))
                dtask = rsrc_task_map[d]
                dependencies.append(dtask | task)
        self.logger.info("%d resource dependencies" % len(dependencies))
        return dependencies
        
    def get_context(self):
        context = self.run_contexts.get(threading.current_thread())
        if context is None:
            context = RunContext(self.record, self.os_creds)
            self.run_contexts[threading.current_thread()] = context
        return context

    @narrate(lambda _, t, **kw: "...when the OpenStack task engine was asked to start preforming task {}".format(t.name))
    def _perform_task(self, task, logfile=None):
        self.logger.info("Starting provisioning task %s named %s, id %s" %
                         (task.__class__.__name__, task.name, str(task._id)))
        try:
            task.perform(self)
        finally:
            self.logger.info("Completed provisioning task %s named %s, id %s" %
                             (task.__class__.__name__, task.name, str(task._id)))
                        

class OpenstackProvisioner(BaseProvisioner):
    """
    This flavor of Actuator provisioner is meant operate against an Openstack-
    equipped cloud API. It will take an Actuator infra model and provsion
    all Openstack resources it finds in it.
    
    The provisioner is conventionally used within the Actuator orchestrator,
    but can be used independently to simply provsion Openstack infrastructure.
    
    See the doc for L{BaseProvisioner} for the rest of the details to run
    the provisioner independently.
    """
    LOG_SUFFIX = "os_provisioner"

    def __init__(self, cloud_name=None, config_files=None, num_threads=5, log_level=LOG_INFO):
        """
        @param username: String; the Openstack user name
        @param password: String; the Openstack password for username
        @param tenant_name: String, the Openstack tenant's name
        @param auth_url: String; the Openstack authentication URL. This will
            authenticate the username/password to allow them to perform the
            resource provisioning tasks.
        @keyword num_threads: Optional. Integer, default 5. The number of threads
            to spawn to handle parallel provisioning tasks
        @keyword log_level: Optional; default LOG_INFO. One of the logging values
            from actuator: LOG_CRIT, LOG_ERROR, LOG_WARN, LOG_INFO, LOG_DEBUG.
        """
        with narrate_cm(lambda cn, cf:
                        "When initializing the OpenStack provisioner for cloud {} and config_files {},"
                        " I tried creating the credentials object"
                        .format(cn, str(cf)), cloud_name, config_files):
            self.os_creds = OpenstackCredentials(cloud_name=cloud_name, config_files=config_files)
        self.agent = None
        self.num_threads = num_threads
        self.log_level = log_level
        # root_logger.setLevel(log_level)
        self.logger = root_logger.getChild(self.LOG_SUFFIX)
        self.logger.setLevel(self.log_level)

    @narrate("I began the OpenStack-specific provisioning work")
    def _provision(self, inframodel_instance):
        self.logger.info("Starting to provision...")
        if self.agent is None:
            self.agent = ResourceTaskSequencerAgent(inframodel_instance,
                                                    self.os_creds,
                                                    num_threads=self.num_threads,
                                                    log_level=self.log_level)
        self.agent.perform_tasks()
        self.logger.info("...provisioning complete.")
        return self.agent.record
    
    def _deprovision(self, inframodel_instance, record=None):
        self.logger.info("Starting to deprovision...")
        if self.agent is None:
            self.agent = ResourceTaskSequencerAgent(inframodel_instance,
                                                    self.os_creds,
                                                    num_threads=self.num_threads)
        self.agent.perform_reverses()
        self.logger.info("Deprovisioning complete.")
        return self.agent.record
