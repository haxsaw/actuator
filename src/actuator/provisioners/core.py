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

"""
Base classes for all Actuator provisioners.
"""
from actuator.infra import InfraModel
from errator import narrate


class ProvisionerException(Exception):
    def __init__(self, msg, record=None):
        super(ProvisionerException, self).__init__(msg)
        self.record = record


class BaseProvisioner(object):
    """
    Base class for all provisioners.
    """
    @narrate(lambda _, imi: "When I was provisioning the inframodel '{}'".format(imi.name))
    def provision_infra_model(self, inframodel_instance):
        """
        Instructs the provisioner to do the work to provision the supplied
        infra model
        
        @param inframodel_instance: An instance of a derived class of InfraModel
        """
        if not isinstance(inframodel_instance, InfraModel):
            raise ProvisionerException("Provisioner asked to provision something not an InfraModel")
        _ = inframodel_instance.refs_for_components()
        return self._provision(inframodel_instance)
    
    def _provision(self, inframodel_instance):
        raise TypeError("Derived class must implement _provision()")
    
    def deprovision_infra_from_record(self, record):
        """
        Not implemented.
        """
        if not isinstance(record, BaseProvisioningRecord):
            raise ProvisionerException("Record must be a kind of BaseProvisioningRecord")
        self._deprovision(record)
        
    def deprovision_infra_model(self, inframodel_instance):
        if not isinstance(inframodel_instance, InfraModel):
            raise ProvisionerException("Deprovision must be supplied an InfraModel"
                                       " instance, not %s" % str(inframodel_instance))
        _ = inframodel_instance.refs_for_components()
        return self._deprovision(inframodel_instance)
        
    def _deprovision(self, inframodel_instance, record=None):
        raise TypeError("Derived class must implement _deprovision()")
    
    
class BaseProvisioningRecord(object):
    """
    Captures the details of provisioning a single resource.
    """
    def __init__(self, rid):
        self.id = rid
        
    def __getstate__(self):
        return {"id": self.id}
    
    def __setstate__(self, state):
        self.id = state["id"]
        del state["id"]
