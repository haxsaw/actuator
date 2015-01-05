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

from actuator.provisioners.core import ProvisionerException
from actuator.provisioners.openstack.resources import *
from actuator.provisioners.openstack.resources import _OpenstackProvisionableInfraResource
from actuator.config import _ConfigTask, ConfigModel, with_dependencies
from actuator.modeling import AbstractModelReference
from actuator.utils import capture_mapping, get_mapper

_rt_domain = "resource_task_domain"


class _ProvisioningTask(_ConfigTask):
    def __init__(self, rsrc):
        super(_ProvisioningTask, self).__init__("{}-provisioning-{}-task"
                                                .format(rsrc.name,
                                                        rsrc.__class__.__name__))
        self.rsrc = rsrc
        
    def depends_on_list(self):
        return []
    
    def _fix_arguments(self):
        return
    
    def provision(self, run_context):
        return


@capture_mapping(_rt_domain, Network)
class ProvisionNetworkTask(_ProvisioningTask):
    def provision(self, run_context):
        msg = {u'network': {u'name':self.rsrc.name,
                            u'admin_state_up':self.rsrc.admin_state_up}}
        response = run_context.nuclient.create_network(body=msg)
        self.rsrc.set_osid(response['network']['id'])
        run_context.record.add_network_id(self.rsrc._id, self.rsrc.osid)
        
        
@capture_mapping(_rt_domain, Subnet)
class ProvisionSubnetTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.network]
                if isinstance(self.rsrc.network, AbstractModelReference)
                else [])
        
    def provision(self, run_context):
        msg = {'subnets': [{'cidr':self.rsrc.cidr,
                            'ip_version':self.rsrc.ip_version,
                            'network_id':self.rsrc.network,
                            'dns_nameservers':self.rsrc.dns_nameservers,
                            'name':self.rsrc.name}]}
        sn = run_context.nuclient.create_subnet(body=msg)
        self.rsrc.set_osid(sn["subnets"][0]["id"])
        run_context.record.add_subnet_id(self.rsrc._id, self.rsrc.osid)



@capture_mapping(_rt_domain, SecGroup)
class ProvisionSecGroupTask(_ProvisioningTask):
    "depends on nothing"
    pass


@capture_mapping(_rt_domain, SecGroupRule)
class ProvisionSecGroupRuleTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.secgroup]
                if isinstance(self.rsrc.secgroup, AbstractModelReference)
                else [])


@capture_mapping(_rt_domain, Server)
class ProvisionServerTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([i for i in self.rsrc.secgroup
                if isinstance(i, AbstractModelReference)] +
                [j for j in self.rsrc.nics
                 if isinstance(j, AbstractModelReference)])


@capture_mapping(_rt_domain, Router)
class ProvisionRouterTask(_ProvisioningTask):
    "depends on nothing"
    pass


@capture_mapping(_rt_domain, RouterGateway)
class ProvisionRouterGatewayTask(_ProvisioningTask):
    def depends_on_list(self):
        return ([self.rsrc.router]
                if isinstance(self.rsrc.router, AbstractModelReference)
                else [])


@capture_mapping(_rt_domain, RouterInterface)
class ProvisionRouterInterfaceTask(_ProvisioningTask):
    def depends_on_list(self):
        return [i for i in [self.rsrc.router, self.rsrc.subnet]
                if isinstance(i, AbstractModelReference)]


@capture_mapping(_rt_domain, FloatingIP)
class ProvisionFloatingIPTask(_ProvisioningTask):
    def depends_on_list(self):
        return set([i.get_containing_component_ref()
                    for i in [self.rsrc.server, self.rsrc.associated_ip]
                    if isinstance(i, AbstractModelReference)])


class ResourceTaskSequencer(object):
    def __init__(self, infra_model):
        self.infra_model = infra_model
        self.graph = None
        self.tasks = set()
        self.rsrc_task_map = {}
        
    def get_graph(self):
        all_resources = set(self.infra_model.resources())
        dependencies = []
            
        #first, generate tasks for all the resources
        class_mapper = get_mapper(_rt_domain)
        for rsrc in all_resources:
            rsrc.fix_arguments()
            task_class = class_mapper.get(rsrc.__class__)
            if task_class is None:
                raise ProvisionerException("Unable to find a task class for resource {}, class {}"
                                           .format(rsrc.name, rsrc.__class__.__name__))
            task = task_class(rsrc)
            self.rsrc_task_map[rsrc] = task
        
        #next, find all the dependencies between resources, and hence tasks
        for rsrc in all_resources:
            task = self.rsrc_task_map[rsrc]
            for d in task.depends_on_list():
                if d.value() not in self.rsrc_task_map:
                    raise ProvisionerException("Resource {} says it depends on {}, "
                                               "but the latter isn't in the "
                                               "list of all resources"
                                               .format(rsrc.name, d.name.value()))
                dependencies.append(d.value() | task)
                
        #now we can make a config class with these tasks and dependencies
        class ProvConfig(ConfigModel):
            for rsrc in all_resources:
                exec "%s_%d = rsrc" % (rsrc.name, id(rsrc))
            del rsrc
            with_dependencies(*dependencies)
            
        pc = ProvConfig()
        return pc.get_graph()
                
        