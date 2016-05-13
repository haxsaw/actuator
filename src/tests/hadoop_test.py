__author__ = 'tom'
import json
import sys
import os.path

here, _ = os.path.split(__file__)
sys.path.append(os.path.join(here, "..", "examples", "hadoop"))

import ost_support
from actuator.provisioners.openstack import openstack_class_factory as ocf
# mock out shade cloud
ocf.get_shade_cloud = ost_support.mock_get_shade_cloud

from actuator import ActuatorOrchestration

# from hadoop HadoopInfra, HadoopNamespace