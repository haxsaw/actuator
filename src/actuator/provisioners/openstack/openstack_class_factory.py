'''
Created on 7 Sep 2014

@author: tom
'''
from novaclient import client as NovaClient
from neutronclient.v2_0 import client as NeutronClient

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
