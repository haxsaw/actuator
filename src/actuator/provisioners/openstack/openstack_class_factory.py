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
This module contains simple factories for Openstack Neutron and Nova clients.
It exists so that mocks can easily be supplied for testing.

Created on 7 Sep 2014
'''
from novaclient import client as NovaClient
from neutronclient.v2_0 import client as NeutronClient
import shade
import os_client_config



_neutron_client_class = NeutronClient.Client
_nova_client_class = NovaClient.Client

def set_neutron_client_class(aClass):
    global _neutron_client_class
    _neutron_client_class = aClass


def set_nova_client_class(aClass):
    global _nova_client_class
    _nova_client_class = aClass


def get_neutron_client_class():
    return _neutron_client_class


def get_nova_client_class():
    return _nova_client_class


# support for the acquiring shade cloud objects configured with os_client_config
def _real_get_os_cloud(cloud_name, config_files=None, vendor_files=None, override_defaults=None,
                       force_ipv4=None, envvar_prefix=None, secure_files=None):
    config = os_client_config.OpenStackConfig(config_files=config_files, vendor_files=vendor_files,
                                              override_defaults=override_defaults,
                                              force_ipv4=force_ipv4, envvar_prefix=envvar_prefix,
                                              secure_files=secure_files).get_one_cloud(cloud_name)
    return shade.OpenStackCloud(cloud_config=config)


# public function for getting a shade.OpenStackCloud-like object. Tests may assign a mock implementation
# to this function name to support testing
def get_shade_cloud(cloud_name, config_files=None, vendor_files=None, override_defaults=None,
                    force_ipv4=None, envvar_prefix=None, secure_files=None):
    return _real_get_os_cloud(cloud_name, onfig_files=config_files, vendor_files=vendor_files,
                              override_defaults=override_defaults, force_ipv4=force_ipv4,
                              envvar_prefix=envvar_prefix, secure_files=secure_files)
