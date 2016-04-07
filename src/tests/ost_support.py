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
from distutils.dir_util import mkpath

'''
Created on 25 Aug 2014
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
    
    def get(self, server_id):
        return self.get_result(server_id)


class CreateAndList(Create):
    def __init__(self, get_result, list_result):
        super(CreateAndList, self).__init__(get_result)
        self.list_result = list_result
        
    def list(self):
        return self.list_result()


class CreateListDelete(CreateAndList):
    def __init__(self, get_result, list_result, delete_result):
        super(CreateListDelete, self).__init__(get_result, list_result)
        self.delete_result = delete_result
        
    def delete(self, key):
        return
    
    
class FakeOSServer(object):
    addresses = {"eth0":[{"addr":"127.0.0.1"}]}


class ServerCreate(Create):
    def add_floating_ip(self, *args, **kwargs):
        return
    
    def remove_floating_ip(self, server, fip):
        return
    
    def delete(self, srvr):
        return
    
    def get(self, server_id):
        return FakeOSServer()
    

class MockKeypair(dict):
    def __init__(self, name, public_key=None):
        super(MockKeypair, self).__init__()
        self.name = self.id = name
        self["name"] = self.name
        self["id"] = self.id
        self.public_key = public_key
        self["public_key"] = public_key


class NetworkResult(dict):
    def __init__(self, name):
        super(NetworkResult, self).__init__()
        self.name = name
        self["name"] = self.name
        self.id = uuid.uuid4()
        self["id"] = self.id


class ImageResult(dict):
    def __init__(self, name):
        super(ImageResult, self).__init__()
        self.id = fake.md5()
        self["id"] = self.id
        self.name = name
        self["name"] = self.name


class FIPResult(dict):
    def __init__(self):
        super(FIPResult, self).__init__()
        self.ip = fake.ipv4()
        self["ip"] = self.ip
        self.id = fake.md5()
        self["id"] = self.id

    def delete(self):
        return


class ServerResult(dict):
    def __init__(self, name):
        super(ServerResult, self).__init__()
        self.id = fake.md5()
        self["id"] = self.id
        self.addresses = {u"network":[{u'addr':fake.ipv4()}]}
        self["addresses"] = self.addresses
        self.name = name
        self["name"] = name


class FlavorResult(dict):
    def __init__(self, name):
        super(FlavorResult, self).__init__()
        self.id = fake.md5()
        self["id"] = self.id
        self.name = name
        self["name"] = self.name


class SecGroupResult(dict):
    def __init__(self, name):
        super(SecGroupResult, self).__init__()
        self.id = fake.md5()
        self["id"] = self.id
        self.name = name
        self["name"] = self.name


class SecGroupRuleResult(dict):
    def __init__(self):
        super(SecGroupRuleResult, self).__init__()
        self.id = fake.md5()
        self["id"] = self.id


class _cache(object):
    _keypairs_dict = {n: MockKeypair(n, "startingkey") for n in [u"actuator-dev-key",
                                                                 u"test-key"]}
    _networks_list = [NetworkResult(n) for n in (u'wibbleNet', u'wibble', u'test1Net', u'network',
                                                 u'external')]
    _image_list = [ImageResult(n) for n in (u'CentOS 6.5 x86_64', u'Ubuntu 13.10',
                                            u'Fedora 20 x86_64')]
    _flavor_list = [FlavorResult(n) for n in (u'm1.small', u'm1.medium', u'm1.large')]
    _secgroup_list = [SecGroupResult(n) for n in (u'default', u'wibbleGroup')]
    _keypairs_dict = {n: MockKeypair(n, "startingkey") for n in [u"actuator-dev-key",
                                                                 u"test-key"]}
    _servers_dict = {}


class MockOSCloud(_cache):

    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.floating_ips = Create(self.fip_create_result)
        self.servers = ServerCreate(self.server_create_result)
        self.images = CreateAndList(self.image_create_result, self.image_list_result)
        self.flavors = CreateAndList(self.flavor_create_result, self.flavor_list_result)
        self.security_groups = CreateListDelete(self.secgroup_create_result,
                                                self.secgroup_list_result,
                                                self.secgroup_delete_result)
        self.networks = CreateAndList(None, self.network_list_result)
        self.security_group_rules = Create(self.secgroup_rule_create_result)
        self.keypairs = CreateListDelete(self.keypair_create_result,
                                         self.keypair_list_result,
                                         self.keypair_delete_result)

    ### MOCK CLOUD METHODS
    def create_network(self, name, admin_state_up=True):
        return {"id": self._networks_list[0].id}

    def delete_network(self, _):
        return

    def list_networks(self):
        return self._networks_list

    def create_subnet(self, *args, **kwargs):
        return {"id": fake.md5()}

    def delete_subnet(self, subnet_id):
        return

    def list_subnets(self):
        return {}

    def create_security_group(self, *args, **kwargs):
        return random.choice(self._secgroup_list)

    def delete_security_group(self, secgroup_id):
        return

    def list_security_groups(self):
        return self._secgroup_list

    def create_security_group_rule(self, *args, **kwargs):
        return SecGroupRuleResult()

    def list_flavors(self):
        return self._flavor_list

    def list_images(self):
        return self._image_list

    def create_floating_ip(self, **kwargs):
        return FIPResult()

    def detach_ip_from_server(self, server_id, fip_id):
        return

    def delete_floating_ip(self, fip_id):
        return

    def create_keypair(self, name, public_key):
        mkp = MockKeypair(name, public_key=public_key)
        self._keypairs_dict[name] = mkp
        return mkp

    def list_keypairs(self):
        return list(self._keypairs_dict.values())

    def delete_keypair(self, key):
        lookup = key.name if isinstance(key, MockKeypair) else key
        try:
            del self._keypairs_dict[lookup]
        except KeyError as _:
            pass
        return

    def create_router(self, **kwargs):
        return {"id": fake.md5()}

    def delete_router(self, router_id):
        return

    def get_router(self, rid, **kwargs):
        return {"id": fake.md5()}

    def update_router(self, name_or_id, **kwargs):
        return

    def add_router_interface(self, router, **kwargs):
        return {"port_id": fake.md5}

    def remove_router_interface(self, router, **kwargs):
        return

    def create_server(self, name, image, flavor, **kwargs):
        s = ServerResult(name)
        self._servers_dict[s["name"]] = s
        self._servers_dict[s["id"]] = s
        return s

    def get_server(self, name_or_id=None, **kwargs):
        return self._servers_dict.get(name_or_id)

    def delete_server(self, name_or_id=None, **kwargs):
        s = self._servers_dict.get(name_or_id)
        if s:
            try:
                del self._servers_dict[s["name"]]
            except KeyError:
                pass
            try:
                del self._servers_dict[s["id"]]
            except KeyError:
                pass

    ### TEST SUPPORT METHODS

    def secgroup_rule_create_result(self, *args, **kwargs):
        return SecGroupRuleResult()

    def secgroup_create_result(self, *args, **kwargs):
        return random.choice(self._secgroup_list)

    def secgroup_list_result(self):
        return list(itertools.chain(self._secgroup_list,
                                    [MockNovaClient.SecGroupResult(sgr.id) for sgr in self._secgroup_list]))

    def secgroup_delete_result(self, key):
        return

    def flavor_create_result(self, *args, **kwargs):
        return random.choice(self._flavor_list)

    def flavor_list_result(self):
        return list(self._flavor_list)

    def server_create_result(self, *args, **kwargs):
        return ServerResult()

    def fip_create_result(self, *args, **kwargs):
        return FIPResult()

    def image_create_result(self, *args, **kwargs):
        return random.choice(self._image_list)

    def image_list_result(self):
        return list(self._image_list)

    def keypair_list_result(self):
        return self._keypairs_dict.values()

    def keypair_create_result(self, name, public_key=None):
        mkp = MockKeypair(name, public_key=public_key)
        self._keypairs_dict[name] = mkp
        return mkp

    def keypair_delete_result(self, key):
        lookup = key.name if isinstance(key, self.MockKeypair) else key
        try:
            del self._keypairs_dict[lookup]
        except KeyError, _:
            pass
        return

    def network_list_result(self):
        return list(self._networks_list)


def mock_get_shade_cloud(cloud_name, **kwargs):
    return MockOSCloud(cloud_name, **kwargs)


class MockNovaClient(_cache):
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
        self.security_groups = CreateListDelete(self.secgroup_create_result,
                                                self.secgroup_list_result,
                                                self.secgroup_delete_result)
        self.networks = CreateAndList(None, self.network_list_result)
        self.security_group_rules = Create(self.secgroup_rule_create_result)
        self.keypairs = CreateListDelete(self.keypair_create_result,
                                         self.keypair_list_result,
                                         self.keypair_delete_result)
        
    # _keypairs_dict = {n: MockKeypair(n, "startingkey") for n in [u"actuator-dev-key",
    #                                                              u"test-key"]}
    
    def keypair_list_result(self):
        return self._keypairs_dict.values()
    
    def keypair_create_result(self, name, public_key=None):
        mkp = MockKeypair(name, public_key=public_key)
        self._keypairs_dict[name] = mkp
        return mkp
    
    def keypair_delete_result(self, key):
        lookup = key.name if isinstance(key, self.MockKeypair) else key
        try:
            del self._keypairs_dict[lookup]
        except KeyError, _:
            pass
        return
        
    class ImageResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
    
    # _image_list = [ImageResult(n) for n in (u'CentOS 6.5 x86_64', u'Ubuntu 13.10',
    #                                         u'Fedora 20 x86_64')]
    
    def image_create_result(self, *args, **kwargs):
        return random.choice(self._image_list)
    
    def image_list_result(self):
        return list(self._image_list)
    
    class FlavorResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
            
    # _flavor_list = [FlavorResult(n) for n in (u'm1.small', u'm1.medium', u'm1.large')]
    
    def flavor_create_result(self, *args, **kwargs):
        return random.choice(self._flavor_list)
    
    def flavor_list_result(self):
        return list(self._flavor_list)
    
    class SecGroupResult(object):
        def __init__(self, name):
            self.id = fake.md5()
            self.name = name
            
    # _secgroup_list = [SecGroupResult(n) for n in (u'default', u'wibbleGroup')]
    
    def secgroup_create_result(self, *args, **kwargs):
        return random.choice(self._secgroup_list)
    
    def secgroup_list_result(self):
        return list(itertools.chain(self._secgroup_list,
                                    [MockNovaClient.SecGroupResult(sgr.id) for sgr in self._secgroup_list]))
        
    def secgroup_delete_result(self, key):
        return    
            
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
                
            def delete(self):
                return
            
        return FIPResult()
    
    class NetworkResult(object):
        def __init__(self, label):
            self.label = label
            self.id = uuid.uuid4()
            
    # _networks_list = [NetworkResult(n) for n in (u'wibbleNet', u'wibble', u'test1Net', u'network',
    #                                              u'external')]
    
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
#         result = {"network": {"id":fake.md5()}}
        result = {"network": {"id":MockNovaClient._networks_list[0].id}}
        return result
    
    def delete_network(self, network_id):
        return
        
    def create_subnet(self, body=None):
        result = {'subnets':[{'id':fake.md5()}]}
        return result
    
    def delete_subnet(self, subnet_id):
        return
    
    def create_router(self, body=None):
        result = {'router': {'id':fake.md5()}}
        return result
    
    def delete_router(self, router_id):
        return
    
    def list_routers(self, *args, **kwargs):
        """{d['name']:d['id'] for d in response["routers"]}"""
        return {'routers':[{'name':'wibbleRouter', 'id':fake.md5()}]}
    
    def add_gateway_router(self, *args, **kwargs):
        return {}
    
    def add_interface_router(self, *args, **kwargs):
        return {u'id':uuid.uuid4(), u'port_id':uuid.uuid4()}
    
    def remove_interface_router(self, router_id, args_dict):
        return
