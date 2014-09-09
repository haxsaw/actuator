'''
Created on 7 Sep 2014

@author: tom
'''
from actuator.infra import InfraSpec


class ProvisionerException(Exception):
    def __init__(self, msg, record=None):
        super(ProvisionerException, self).__init__(msg)
        self.record = record


class BaseProvisioner(object):
    def provision_infra_spec(self, infraspec_instance):
        if not isinstance(infraspec_instance, InfraSpec):
            raise ProvisionerException("Provisioner asked to provision something not an InfraSpec")
        _ = infraspec_instance.refs_for_provisionables()
        return self._provision(infraspec_instance)
    
    def _provision(self, infraspec_instance):
        raise TypeError("Derived class must implement _provision()")
    
    def deprovision_infra_from_record(self, record):
        if not isinstance(record, BaseProvisioningRecord):
            raise ProvisionerException("Record must be a kind of BaseProvisioningRecord")
        self._deprovision(record)
        
    def _deprovision(self, record):
        raise TypeError("Derived class must implement _deprovision()")
    
    
class BaseProvisioningRecord(object):
    def __init__(self, id):
        self.id = id
        
    def __getstate__(self):
        return {"id":self.id}
    
    def __setstate__(self, state):
        self.id = state["id"]
        del state["id"]
        
