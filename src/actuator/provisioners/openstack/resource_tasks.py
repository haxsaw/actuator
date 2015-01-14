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
Created on Jan 5, 2015
'''
import time
import threading
import uuid
import string
import logging

from actuator.namespace import NamespaceModel
from actuator.provisioners.openstack import openstack_class_factory as ocf
NovaClient = ocf.get_nova_client_class()
NeutronClient = ocf.get_neutron_client_class()
from actuator.provisioners.core import ProvisionerException, BaseProvisioner
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.support import (_OSMaps,
                                                     OpenstackProvisioningRecord)
from actuator.config import _ConfigTask, ConfigModel, with_dependencies
from actuator.exec_agents.core import ExecutionAgent
from actuator.utils import (capture_mapping, get_mapper, root_logger, LOG_INFO,
                            LOG_WARN)

_rt_domain = "resource_task_domain"


class RunContext(object):
    def __init__(self, record, username, password, tenant_name, auth_url):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url
        self.record = record
        self.maps = _OSMaps(self)
    
    def _nuclient(self):
        return NeutronClient(username=self.username, password=self.password,
                             auth_url=self.auth_url, tenant_name=self.tenant_name)
        
    nuclient = property(_nuclient)
    
    def _nvclient(self):
        return NovaClient("1.1", self.username, self.password,
                          self.tenant_name, self.auth_url)
        
    nvclient = property(_nvclient)


class _ProvisioningTask(_ConfigTask):
    clone_attrs = False
    def __init__(self, rsrc, repeat_count=1):
        super(_ProvisioningTask, self).__init__("{}_provisioning_{}_task"
                                                .format(rsrc.name,
                                                        rsrc.__class__.__name__),
                                                repeat_count=1)
        self.rsrc = rsrc
        
    def depends_on_list(self):
        return []
    
    def provision(self, run_context):
        self._provision(run_context)
    
    def _provision(self, run_context):
        return
    
    def get_init_args(self):
        return ((self.rsrc,), {"repeat_count":self.repeat_count})


@capture_mapping(_rt_domain, Network)
class ProvisionNetworkTask(_ProvisioningTask):
    def _provision(self, run_context):
        msg = {u'network': {u'name':self.rsrc.name,
                            u'admin_state_up':self.rsrc.admin_state_up}}
        response = run_context.nuclient.create_network(body=msg)
        self.rsrc.set_osid(response['network']['id'])
        run_context.record.add_network_id(self.rsrc._id, self.rsrc.osid)
        
        
@capture_mapping(_rt_domain, Subnet)
class ProvisionSubnetTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.network]
                if isinstance(self.rsrc.network, Network)
                else [])
        
    def _provision(self, run_context):
        msg = {'subnets': [{'cidr':self.rsrc.cidr,
                            'ip_version':self.rsrc.ip_version,
#                             'network_id':self.rsrc.network,
                            'network_id':self.rsrc._get_arg_msg_value(self.rsrc.network,
                                                                      Network,
                                                                      "osid",
                                                                      "network"),
                            'dns_nameservers':self.rsrc.dns_nameservers,
                            'name':self.rsrc.name}]}
        sn = run_context.nuclient.create_subnet(body=msg)
        self.rsrc.set_osid(sn["subnets"][0]["id"])
        run_context.record.add_subnet_id(self.rsrc._id, self.rsrc.osid)


@capture_mapping(_rt_domain, SecGroup)
class ProvisionSecGroupTask(_ProvisioningTask):
    "depends on nothing"
    def _provision(self, run_context):
        response = run_context.nvclient.security_groups.create(name=self.rsrc.name,
                                                               description=self.rsrc.description)
        self.rsrc.set_osid(response.id)
        run_context.record.add_secgroup_id(self.rsrc._id, self.rsrc.osid)


@capture_mapping(_rt_domain, SecGroupRule)
class ProvisionSecGroupRuleTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.secgroup]
                if isinstance(self.rsrc.secgroup, SecGroup)
                else [])
        
    def _provision(self, run_context):
        response = run_context.nvclient.security_group_rules.create(self.rsrc._get_arg_msg_value(self.rsrc.secgroup,
                                                                                                 SecGroup,
                                                                                                 "osid", "secgroup"),
                                                                    ip_protocol=self.rsrc.ip_protocol,
                                                                    from_port=self.rsrc.from_port,
                                                                    to_port=self.rsrc.to_port,
                                                                    cidr=self.rsrc.cidr)
        self.rsrc.set_osid(response.id)
        run_context.record.add_secgroup_rule_id(self.rsrc._id, self.rsrc.osid)



@capture_mapping(_rt_domain, Server)
class ProvisionServerTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([i for i in self.rsrc.security_groups
                if isinstance(i, SecGroup)] +
                [j for j in self.rsrc.nics
                 if isinstance(j, Network)])

    def  _process_server_addresses(self, addr_dict):
        self.rsrc.set_addresses(addr_dict)
        for i, (k, v) in enumerate(addr_dict.items()):
            iface = getattr(self.rsrc, "iface%d" % i)
            iface.name = k
            for j, iface_addr in enumerate(v):
                setattr(iface, "addr%d" % j, iface_addr['addr'])

    def _provision(self, run_context):
        run_context.maps.refresh_images()
        run_context.maps.refresh_flavors()
        run_context.maps.refresh_networks()
        args, kwargs = self.rsrc.get_fixed_args()
        name, image_name, flavor_name = args
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
            
        srvr = run_context.nvclient.servers.create(name, image, flavor, **kwargs)
        self.rsrc.set_osid(srvr.id)
        run_context.record.add_server_id(self.rsrc._id, self.rsrc.osid)
        
        while not srvr.addresses:
            time.sleep(0.25)
            srvr.get()
        self._process_server_addresses(srvr.addresses)

                
@capture_mapping(_rt_domain, Router)
class ProvisionRouterTask(_ProvisioningTask):
    "depends on nothing"
    def _provision(self, run_context):
        msg = {u'router': {u'admin_state_up':self.rsrc.admin_state_up,
                           u'name':self.rsrc.name}}
        reply = run_context.nuclient.create_router(body=msg)
        self.rsrc.set_osid(reply["router"]["id"])
        run_context.record.add_router_id(self.rsrc._id, self.rsrc.osid)


@capture_mapping(_rt_domain, RouterGateway)
class ProvisionRouterGatewayTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.router]
                if isinstance(self.rsrc.router, Router)
                else [])
        
    def _provision(self, run_context):
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        run_context.maps.refresh_networks()
        ext_net = run_context.maps.network_map.get(self.rsrc.external_network_name)
        msg = {u'network_id':ext_net.id}
        _ = run_context.nuclient.add_gateway_router(router_id, msg)


@capture_mapping(_rt_domain, RouterInterface)
class ProvisionRouterInterfaceTask(_ProvisioningTask):
    def depends_on_list(self):
        deps = []
        if isinstance(self.rsrc.router, Router):
            deps.append(self.rsrc.router)
        if isinstance(self.rsrc.subnet, Subnet):
            deps.append(self.rsrc.subnet)
        return deps
        
    def _provision(self, run_context):
        router_id = self.rsrc._get_arg_msg_value(self.rsrc.router, Router, "osid", "router")
        subnet = self.rsrc._get_arg_msg_value(self.rsrc.subnet, Subnet, "osid", "subnet")
        response = run_context.nuclient.add_interface_router(router_id,
                                                      {u'subnet_id':subnet,
                                                       u'name':self.rsrc.name})
        run_context.record.add_router_iface_id(self.rsrc._id, response[u'id'])


@capture_mapping(_rt_domain, FloatingIP)
class ProvisionFloatingIPTask(_ProvisioningTask):
    def depends_on_list(self):
        return [self.rsrc.server] if isinstance(self.rsrc.server, Server) else []
        
    def _provision(self, run_context):
        self.rsrc.refix_arguments()
        fip = run_context.nvclient.floating_ips.create(self.rsrc.pool)
        self.rsrc.set_addresses(fip.get_ip)
        self.rsrc.set_osid(fip.id)
        run_context.record.add_floating_ip_id(self.rsrc._id, self.rsrc.osid)
        associated_ip = self.rsrc.associated_ip
        if associated_ip is not None:
            servername = self.rsrc._get_arg_msg_value(self.rsrc.server, Server,
                                                      "osid", "server")
            server = run_context.nvclient.servers.get(servername)
            run_context.nvclient.servers.add_floating_ip(server, fip, associated_ip)
            
            
class OpenstackCredentials(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url


class ResourceTaskSequencerAgent(ExecutionAgent):
    no_punc = string.maketrans(string.punctuation, "_"*len(string.punctuation))
    exception_class = ProvisionerException
    def __init__(self, infra_model, os_creds, num_threads=5):
        self.logger = root_logger.getChild("os_prov_agent")
        self.infra_config_model = self.compute_model(infra_model)
        class ShutupNamespace(NamespaceModel): pass
        nmi = ShutupNamespace()
        super(ResourceTaskSequencerAgent, self).__init__(config_model_instance=self.infra_config_model,
                                                         namespace_model_instance=nmi,
                                                         no_delay=True,
                                                         num_threads=num_threads,
                                                         log_level=self.logger.getEffectiveLevel())
        self.run_contexts = {}  #keys are threads, values are RunContext objects
        self.record = OpenstackProvisioningRecord(uuid.uuid4())
        self.os_creds = os_creds
        
    def get_context(self):
        context = self.run_contexts.get(threading.current_thread())
        if context is None:
            context = RunContext(self.record, self.os_creds.username,
                                 self.os_creds.password,
                                 self.os_creds.tenant_name,
                                 self.os_creds.auth_url)
            self.run_contexts[threading.current_thread()] = context
        return context
    
    def _perform_task(self, task, logfile=None):
        self.logger.info("Starting provisioning task %s named %s, id %s" %
                         (task.__class__.__name__, task.name, str(task._id)))
        try:
            task.provision(self.get_context())
        finally:
            self.logger.info("Completed provisioning task %s named %s, id %s" %
                             (task.__class__.__name__, task.name, str(task._id)))
        
    def get_graph(self, with_fix=False):
        return self.infra_config_model.get_graph(with_fix=with_fix)
    
    def compute_model(self, infra_mi):
        all_resources = set(infra_mi.resources())
        self.logger.info("%d resources to provision" % len(all_resources))
        dependencies = []
        rsrc_task_map = {}
            
        #first, generate tasks for all the resources
        class_mapper = get_mapper(_rt_domain)
        for rsrc in all_resources:
            rsrc.fix_arguments()
            task_class = class_mapper.get(rsrc.__class__)
            if task_class is None:
                raise ProvisionerException("Unable to find a task class for resource {}, class {}"
                                           .format(rsrc.name, rsrc.__class__.__name__))
            task = task_class(rsrc, repeat_count=1)
            rsrc_task_map[rsrc] = task
        
        #next, find all the dependencies between resources, and hence tasks
        for rsrc in all_resources:
            task = rsrc_task_map[rsrc]
            for d in task.depends_on_list():
                if d not in rsrc_task_map:
                    raise ProvisionerException("Resource {} says it depends on {}, "
                                               "but the latter isn't in the "
                                               "list of all resources"
                                               .format(rsrc.name, d.name))
                dtask = rsrc_task_map[d]
                dependencies.append(dtask | task)
                
        self.logger.info("%d resource dependencies" % len(dependencies))
                
        #now we can make a config class with these tasks and dependencies
        class ProvConfig(ConfigModel):
            for rsrc in rsrc_task_map.values():
                exec "%s_%d = rsrc" % (string.translate(rsrc.name, self.no_punc),
                                       id(rsrc))
            del rsrc
            with_dependencies(*dependencies)
            
        return ProvConfig()
                

class OpenstackProvisioner(BaseProvisioner):
    LOG_SUFFIX = "os_provisioner"
    def __init__(self, username, password, tenant_name, auth_url, num_threads=5,
                 log_level=LOG_INFO):
        self.os_creds = OpenstackCredentials(username, password, tenant_name, auth_url)
        self.agent = None
        self.num_threads = num_threads
        root_logger.setLevel(log_level)
        self.logger = root_logger.getChild(self.LOG_SUFFIX)
        
    def _provision(self, inframodel_instance):
        self.logger.info("Starting to provision...")
        self.agent = ResourceTaskSequencerAgent(inframodel_instance,
                                                self.os_creds,
                                                num_threads=self.num_threads)
        self.agent.perform_config()
        self.logger.info("...provisioning complete.")
        return self.agent.record