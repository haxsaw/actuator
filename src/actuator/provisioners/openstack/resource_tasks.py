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

'''
Internal to Actuator; responsible for processing Openstack resource objects
'''
import time
import threading
import uuid
import string

import shade
import os_client_config

from actuator.modeling import AbstractModelReference
from actuator.task import TaskEngine, GraphableModelMixin, Task
from actuator.provisioners.openstack import openstack_class_factory as ocf
NovaClient = ocf.get_nova_client_class()
NeutronClient = ocf.get_neutron_client_class()
from actuator.provisioners.core import ProvisionerException, BaseProvisioner
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.support import (_OSMaps,
                                                     OpenstackProvisioningRecord)
from actuator.utils import (capture_mapping, get_mapper, root_logger, LOG_INFO)

_rt_domain = "resource_task_domain"


class RunContext(object):
    def __init__(self, record, username, password, tenant_name, auth_url, cloud_name=None):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url
        self.record = record
        self.maps = _OSMaps(self)
        if cloud_name is not None:
            self.cloud_config = os_client_config.OpenStackConfig().get_one_cloud(cloud_name)
            self.cloud = shade.OpenStackCloud(cloud_config=self.cloud_config)
    
    def _nuclient(self):
        return NeutronClient(username=self.username, password=self.password,
                             auth_url=self.auth_url, tenant_name=self.tenant_name)
        
    nuclient = property(_nuclient)
    
    def _nvclient(self):
        return NovaClient('1.1', self.username, self.password,
                          self.tenant_name, self.auth_url)
        
    nvclient = property(_nvclient)


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
        #self.rsrc has been turned into a property

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
        return ((self.rsrc,), {"repeat_count":self.repeat_count})


@capture_mapping(_rt_domain, Network)
class ProvisionNetworkTask(ProvisioningTask):
    def _perform(self, engine):
        run_context = engine.get_context()
        # msg = {u'network': {u'name':self.rsrc.get_display_name(),
        #                     u'admin_state_up':self.rsrc.admin_state_up}}
        # response = run_context.nuclient.create_network(body=msg)
        # self.rsrc.set_osid(response['network']['id'])
        response = run_context.cloud.create_network(self.rsrc.get_display_name(),
                                                    admin_state_up=self.rsrc.admin_state_up)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_network_id(self.rsrc._id, self.rsrc.osid)
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        netid = self.rsrc.osid
        # run_context.nuclient.delete_network(netid)
        run_context.cloud.delete_network(netid)
        
        
@capture_mapping(_rt_domain, Subnet)
class ProvisionSubnetTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.network]
                if isinstance(self.rsrc.network, Network)
                else [])
        
    def _perform(self, engine):
        run_context = engine.get_context()
        response = run_context.cloud.create_subnet(self.rsrc._get_arg_msg_value(self.rsrc.network,
                                                                                Network,
                                                                                "osid",
                                                                                "network"),
                                                   self.rsrc.cidr, ip_version=self.rsrc.ip_version,
                                                   subnet_name=self.rsrc.get_display_name(),
                                                   dns_nameservers=self.rsrc.dns_nameservers)
        # msg = {'subnets': [{'cidr': self.rsrc.cidr,
        #                     'ip_version': self.rsrc.ip_version,
        #                     'network_id': self.rsrc._get_arg_msg_value(self.rsrc.network,
        #                                                                Network,
        #                                                                "osid",
        #                                                                "network"),
        #                     'dns_nameservers': self.rsrc.dns_nameservers,
        #                     'name': self.rsrc.get_display_name()}]}
        # sn = run_context.nuclient.create_subnet(body=msg)
        # self.rsrc.set_osid(sn["subnets"][0]["id"])
        self.rsrc.set_osid(response["id"])
        run_context.record.add_subnet_id(self.rsrc._id, self.rsrc.osid)
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        #this may not be needed as the subnet may go with the network
        subnet_id = self.rsrc.osid
        # run_context.nuclient.delete_subnet(subnet_id)
        run_context.cloud.delete_subnet(subnet_id)


@capture_mapping(_rt_domain, SecGroup)
class ProvisionSecGroupTask(ProvisioningTask):
    """depends on nothing"""

    #@FIXME: this lock and its use are due to an apparent thread-safety issue
    #down in the novaclient. It would seem that even if there are different
    #client objects being used in different threads to build security groups,
    #nova has some shared state that gets hosed and causes one or the other to
    #fail if they're happening at the same time. For now, this lock will ensure
    #single-threaded operation of this trouble code, and hopefully we can get
    #a bug filed and the problem resolved soon.

    _sg_create_lock = threading.Lock()

    def _perform(self, engine):
        run_context = engine.get_context()
        with self._sg_create_lock:
            #@FIXME: this lock is because nova isn't threadsafe for this
            #call, and until it is we have to single-thread through it
            # response = run_context.nvclient.security_groups.create(name=self.rsrc.get_display_name(),
            #                                                        description=self.rsrc.description)
            response = run_context.cloud.create_security_group(name=self.rsrc.get_display_name(),
                                                               description=self.rsrc.description)
        # try:
        #     #@FIXME: this lock is because nova isn't threadsafe for this
        #     #call, and until it is we have to single-thread through it
        #     self._sg_create_lock.acquire()
        #     response = run_context.nvclient.security_groups.create(name=self.rsrc.get_display_name(),
        #                                                            description=self.rsrc.description)
        # finally:
        #     self._sg_create_lock.release()
        # self.rsrc.set_osid(response.id)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_id(self.rsrc._id, self.rsrc.osid)
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        secgroup_id = self.rsrc.osid
        # run_context.nvclient.security_groups.delete(secgroup_id)
        run_context.cloud.delete_security_group(secgroup_id)


@capture_mapping(_rt_domain, SecGroupRule)
class ProvisionSecGroupRuleTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.slave_secgroup]
                if isinstance(self.rsrc.slave_secgroup, SecGroup)
                else [])
        
    def _perform(self, engine):
        run_context = engine.get_context()
        sg_id = self.rsrc._get_arg_msg_value(self.rsrc.slave_secgroup,
                                             SecGroup,
                                             "osid", "secgroup")
        response = run_context.cloud.create_security_group_rule(sg_id,
                                                                port_range_min=self.rsrc.from_port,
                                                                port_range_max=self.rsrc.to_port,
                                                                protocol=self.rsrc.ip_protocol,
                                                                remote_ip_prefix=self.rsrc.cidr)
        # response = run_context.nvclient.security_group_rules.create(sg_id,
        #                                                             ip_protocol=self.rsrc.ip_protocol,
        #                                                             from_port=self.rsrc.from_port,
        #                                                             to_port=self.rsrc.to_port,
        #                                                             cidr=self.rsrc.cidr)
        # self.rsrc.set_osid(response.id)
        self.rsrc.set_osid(response["id"])
        run_context.record.add_secgroup_rule_id(self.rsrc._id, self.rsrc.osid)
        
    #NO _reverse required; the rules should follow the secgroup



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

    def  _process_server_addresses(self, addr_dict):
        self.rsrc.set_addresses(addr_dict)
        for i, (k, v) in enumerate(addr_dict.items()):
            iface = getattr(self.rsrc, "iface%d" % i)
            iface.name = k
            for j, iface_addr in enumerate(v):
                setattr(iface, "addr%d" % j, iface_addr['addr'])

    def _perform(self, engine):
        run_context = engine.get_context()
        run_context.maps.refresh_images()
        run_context.maps.refresh_flavors()
        run_context.maps.refresh_networks()
        args, kwargs = self.rsrc.get_fixed_args()
        _, image_name, flavor_name = args
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
            run_context.maps.refresh_secgroups()
            for sgname in self.rsrc.security_groups:
                sgname = self.rsrc._get_arg_msg_value(sgname, SecGroup, "osid", sgname)
                sg = run_context.maps.secgroup_map.get(sgname)
                if sg is None:
                    raise ProvisionerException("Security group %s doesn't seem to exist" % sgname,
                                               record=run_context.record)
                secgroup_list.append(sg.id)
            kwargs["security_groups"] = secgroup_list
            
        nics_list = []
        if self.rsrc.nics:
            for nicname in self.rsrc.nics:
                nicname = self.rsrc._get_arg_msg_value(nicname, Network, "osid", nicname)
                nic = run_context.maps.network_map.get(nicname)
                if nic is None:
                    raise ProvisionerException("NIC %s doesn't seem to exist" % nicname,
                                               record=run_context.record)
                nics_list.append({'net-id':nic.id})
            kwargs['nics'] = nics_list
            
        if isinstance(kwargs["key_name"], KeyPair):
            kwargs["key_name"] = kwargs["key_name"].get_key_name()
            
        srvr = run_context.nvclient.servers.create(name, image, flavor, **kwargs)
        self.rsrc.set_osid(srvr.id)
        run_context.record.add_server_id(self.rsrc._id, self.rsrc.osid)
        
        while not srvr.addresses:
            time.sleep(0.25)
            srvr.get()
        self._process_server_addresses(srvr.addresses)
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        server = run_context.nvclient.servers.get(self.rsrc.osid)
        run_context.nvclient.servers.delete(server)

                
@capture_mapping(_rt_domain, Router)
class ProvisionRouterTask(ProvisioningTask):
    "depends on nothing"
    def _perform(self, engine):
        run_context = engine.get_context()
        msg = {u'router': {u'admin_state_up':self.rsrc.admin_state_up,
                           u'name':self.rsrc.get_display_name()}}
        reply = run_context.nuclient.create_router(body=msg)
        self.rsrc.set_osid(reply["router"]["id"])
        run_context.record.add_router_id(self.rsrc._id, self.rsrc.osid)
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc.osid
        run_context.nuclient.delete_router(router_id)


@capture_mapping(_rt_domain, RouterGateway)
class ProvisionRouterGatewayTask(ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.router]
                if isinstance(self.rsrc.router, Router)
                else [])
        
    def _perform(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        run_context.maps.refresh_networks()
        ext_net = run_context.maps.network_map.get(self.rsrc.external_network_name)
        msg = {u'network_id':ext_net.id}
        _ = run_context.nuclient.add_gateway_router(router_id, msg)
        
    #no reversing; assume it goes with the router


@capture_mapping(_rt_domain, RouterInterface)
class ProvisionRouterInterfaceTask(ProvisioningTask):
    def depends_on_list(self):
        deps = []
        if isinstance(self.rsrc.router, Router):
            deps.append(self.rsrc.router)
        if isinstance(self.rsrc.subnet, Subnet):
            deps.append(self.rsrc.subnet)
        return deps
        
    def _perform(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        subnet = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        response = run_context.nuclient.add_interface_router(router_id,
                                                      {u'subnet_id':subnet,
                                                       u'name':self.rsrc.get_display_name()})
        self.rsrc.set_osid(response[u'port_id'])
        run_context.record.add_router_iface_id(self.rsrc._id, response[u'port_id'])
        
    def _reverse(self, engine):
        run_context = engine.get_context()
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        run_context.nuclient.remove_interface_router(router_id,
                                                     {u'port_id':self.rsrc.osid})


@capture_mapping(_rt_domain, FloatingIP)
class ProvisionFloatingIPTask(ProvisioningTask):
    def depends_on_list(self):
        return [self.rsrc.server] if isinstance(self.rsrc.server, Server) else []
        
    def _perform(self, engine):
        run_context = engine.get_context()
        self.rsrc._refix_arguments()
        fip = run_context.nvclient.floating_ips.create(self.rsrc.pool)
        self.rsrc.set_addresses(fip.ip)
        self.rsrc.set_osid(fip.id)
        run_context.record.add_floating_ip_id(self.rsrc._id, self.rsrc.osid)
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            server = run_context.nvclient.servers.get(servername)
            run_context.nvclient.servers.add_floating_ip(server, fip, associated_ip)
            
    def _reverse(self, engine):
        run_context = engine.get_context()
        fip = run_context.nvclient.floating_ips.get(self.rsrc.osid)
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            server = run_context.nvclient.servers.get(servername)
            run_context.nvclient.servers.remove_floating_ip(server, fip)
        fip.delete()
            
            
@capture_mapping(_rt_domain, KeyPair)
class ProvisionKeyPairTask(ProvisioningTask):
    "KeyPairs depend on nothing"
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
                run_context.nvclient.keypairs.delete(name)
                run_context.nvclient.keypairs.create(name, public_key=public_key)
        else:
            run_context.nvclient.keypairs.create(name, public_key=public_key)
                

class OpenstackCredentials(object):
    def __init__(self, username, password, tenant_name, auth_url, cloud_name=None):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url
        self.cloud_name = cloud_name


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
        self.run_contexts = {}  #keys are threads, values are RunContext objects
        self.record = OpenstackProvisioningRecord(uuid.uuid4())
        self.os_creds = os_creds
        self.rsrc_task_map = {}
        
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
        all_resources = set(self.infra_model.components())
        tasks = []
        self.logger.info("%s resources to provision" % len(all_resources))
        class_mapper = get_mapper(_rt_domain)
        for rsrc in all_resources:
            if rsrc in self.rsrc_task_map:
                tasks.append( self.rsrc_task_map[rsrc] )
                continue
            rsrc.fix_arguments()
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
        #now, self already contains a rsrc_task_map, but that's meant to be
        #used as a cache for multiple calls to get_tasks so that the tasks
        #returned are always tghe same. However, we can't assume in this
        #method that get_tasks() has already been called, or that doing
        #so causes the side-effect that self.rsrc_task_map gets populated
        #(or that it even exists). So we get the tasks and construct our own
        #map, just to be on the safe side.
        rsrc_task_map = {task.rsrc:task for task in self.get_tasks()}
        dependencies = []
        for rsrc, task in rsrc_task_map.items():
            for d in task.depends_on_list():
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
            context = RunContext(self.record, self.os_creds.username,
                                 self.os_creds.password,
                                 self.os_creds.tenant_name,
                                 self.os_creds.auth_url,
                                 cloud_name=self.os_creds.cloud_name)
            self.run_contexts[threading.current_thread()] = context
        return context
    
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
    def __init__(self, username, password, tenant_name, auth_url, cloud_name=None,
                 num_threads=5, log_level=LOG_INFO):
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
        self.os_creds = OpenstackCredentials(username, password, tenant_name, auth_url, cloud_name=cloud_name)
        self.agent = None
        self.num_threads = num_threads
        root_logger.setLevel(log_level)
        self.logger = root_logger.getChild(self.LOG_SUFFIX)
        
    def _provision(self, inframodel_instance):
        self.logger.info("Starting to provision...")
        if self.agent is None:
            self.agent = ResourceTaskSequencerAgent(inframodel_instance,
                                                    self.os_creds,
                                                    num_threads=self.num_threads)
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
    