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

from faker import Faker
fake = Faker()
fake.seed(22)


class FakeOSServer(object):
    addresses = {"eth0":[{"addr":"127.0.0.1"}]}


class MockKeypair(dict):
    def __init__(self, name, public_key=None):
        super(MockKeypair, self).__init__()
        self["name"] = name
        self["id"] = name
        self["public_key"] = public_key


class NetworkResult(dict):
    def __init__(self, name):
        super(NetworkResult, self).__init__()
        self["name"] = name
        self["id"] = uuid.uuid4()


class ImageResult(dict):
    def __init__(self, name):
        super(ImageResult, self).__init__()
        self["id"] = fake.md5()
        self["name"] = name


class FIPResult(dict):
    def __init__(self):
        super(FIPResult, self).__init__()
        self["floating_ip_address"] = fake.ipv4()
        self["id"] = fake.md5()


class ServerResult(dict):
    def __init__(self, name):
        super(ServerResult, self).__init__()
        self["id"] = fake.md5()
        self["addresses"] = {u"network":[{u'addr':fake.ipv4()}]}
        self["name"] = name


class FlavorResult(dict):
    def __init__(self, name):
        super(FlavorResult, self).__init__()
        self["id"] = fake.md5()
        self["name"] = name


class SecGroupResult(dict):
    def __init__(self, name):
        super(SecGroupResult, self).__init__()
        self["id"] = fake.md5()
        self["name"] = name


class SecGroupRuleResult(dict):
    def __init__(self):
        super(SecGroupRuleResult, self).__init__()
        # self.id = fake.md5()
        self["id"] = fake.md5()


class MockOSCloud(object):
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

    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs

    ### MOCK CLOUD METHODS
    def create_network(self, name, admin_state_up=True):
        return {"id": self._networks_list[0]["id"]}

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

    def list_routers(self, *args, **kwargs):
        return [{'name': 'wibbleRouter', 'id': fake.md5()}]

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


def mock_get_shade_cloud(cloud_name, **kwargs):
    return MockOSCloud(cloud_name, **kwargs)
