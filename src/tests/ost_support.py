# 
# Copyright (c) 2014 Tom Carroll
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
Created on 25 Aug 2014

@author: tom
'''
import random
import uuid
import itertools

from faker import Faker
fake = Faker()
fake.seed(22)

class Create(object):
    def __init__(self, get_result):
        self.get_result = get_result
        
    def create(self, *args, **kwargs):
        return self.get_result(*args, **kwargs)
    

class CreateAndList(Create):
    def __init__(self, get_result, list_result):
        super(CreateAndList, self).__init__(get_result)
        self.list_result = list_result
        
    def list(self):
        return self.list_result()
    
    
class FakeOSServer(object):
    pass


class ServerCreate(Create):
    def add_floating_ip(self, *args, **kwargs):
        return
    
    def get(self, server_id):
        return FakeOSServer()
    

class MockNovaClient(object):
    def __init__(self, version, username, password, tenant_name, auth_url):
        self.version = version
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.auth_url = auth_url
        self.floating_ips = Create(self.fip_create_result)
        self.servers = ServerCreate(self.server_create_result)
        self.images = CreateAndList(self.image_create_result, self.image_list_result)
        self.flavors = CreateAndList(self.flavor_create_result, self.flavor_list_result)
        self.security_groups = CreateAndList(self.secgroup_create_result, self.secgroup_list_result)
        self.networks = CreateAndList(None, self.network_list_result)
        self.security_group_rules = Create(self.secgroup_rule_create_result)
        
    class ImageResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
    
    _image_list = [ImageResult(n) for n in (u'CentOS 6.5 x86_64', u'Ubuntu 13.10', u'Fedora 20 x86_64')]
    
    def image_create_result(self, *args, **kwargs):
        return random.choice(self._image_list)
    
    def image_list_result(self):
        return list(self._image_list)
    
    class FlavorResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
            
    _flavor_list = [FlavorResult(n) for n in (u'm1.small', u'm1.medium', u'm1.large')]
    
    def flavor_create_result(self, *args, **kwargs):
        return random.choice(self._flavor_list)
    
    def flavor_list_result(self):
        return list(self._flavor_list)
    
    class SecGroupResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
            
    _secgroup_list = [SecGroupResult(n) for n in (u'default', u'wibbleGroup')]
    
    def secgroup_create_result(self, *args, **kwargs):
        return random.choice(self._secgroup_list)
    
    def secgroup_list_result(self):
        return list(itertools.chain(self._secgroup_list,
                                    [MockNovaClient.SecGroupResult(sgr.id) for sgr in self._secgroup_list]))
    
            
    def secgroup_rule_create_result(self, *args, **kwargs):
        class SecGroupRuleResult(object):
            def __init__(self):
                self.id = fake.md5()
        return SecGroupRuleResult()
        
    def fip_create_result(self, *args, **kwargs):
        class FIPResult(object):
            def __init__(self):
                self.ip = fake.ipv4()
                self.id = fake.md5()
            
        return FIPResult()
    
    class NetworkResult(object):
        def __init__(self, label):
            self.label = label
            self.id = uuid.uuid4()
            
    _networks_list = [NetworkResult(n) for n in (u'wibbleNet', u'wibble', u'test1Net', u'network',
                                                 u'external')]
    
    def network_list_result(self):
        return list(self._networks_list)
    
    def server_create_result(self, *args, **kwargs):
        class ServerResult(object):
            def __init__(self):
                self.id = fake.md5()
                self.addresses = {u"network":[{u'addr':fake.ipv4()}]}
        return ServerResult()


class MockNeutronClient(object):
    def __init__(self, username=None, password=None, auth_url=None, tenant_name=None):
        self.username = username
        self.password = password
        self.auth_url = auth_url
        self.tenant_name = tenant_name
        
    def create_network(self, body=None):
        result = {"network": {"id":fake.md5()}}
        return result
        
    def create_subnet(self, body=None):
        result = {'subnets':[{'id':fake.md5()}]}
        return result
    
    def create_router(self, body=None):
        result = {'router': {'id':fake.md5()}}
        return result
    
    def list_routers(self, *args, **kwargs):
        """{d['name']:d['id'] for d in response["routers"]}"""
        return {'routers':[{'name':'wibbleRouter', 'id':fake.md5()}]}
    
    
