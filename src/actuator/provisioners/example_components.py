'''
Created on 7 Sep 2014

@author: tom
'''
from actuator.infra import Provisionable


class Server(Provisionable):
    def __init__(self, logicalName, **kwargs):
        super(Server, self).__init__(logicalName)
        self.provisionedName = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs
        
    def get_init_args(self):
        return ((self.logicalName,), self.kwargs)
    
    
class Database(Provisionable):
    def __init__(self, logicalName, **kwargs):
        super(Database, self).__init__(logicalName)
        self.provisionedName = None
        self.port = None
        self.adminUser = None
        self.adminPassword = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs
        
    def get_init_args(self):
        return ((self.logicalName,), self.kwargs)
    
    
class Queue(Provisionable):
    def __init__(self, logicalName, **kwargs):
        super(Queue, self).__init__(logicalName)
        self.provisionedName = None
        self.qmanager = None
        self.host = None
        self.port = None
        object.__getattribute__(self, "__dict__").update(kwargs)
        self.kwargs = kwargs

    def get_init_args(self):
        return((self.logicalName,), self.kwargs)
    
        
