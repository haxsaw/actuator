import sys
from actuator import StaticServer, adb, InfraModel

class Flagger(object):
    def __init__(self):
        self.flag = False
    def __call__(self, context):
        self.flag = True
        return "127.0.0.1"
flagger = Flagger()

class Model(InfraModel):
    ss = StaticServer("test", adb(flagger))
inst = Model("inst")

inst.ss.fix_arguments()
if flagger.flag:
    sys.exit(0)
else:
    sys.exit(1)
