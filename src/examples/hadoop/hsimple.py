import sys
from actuator import ActuatorOrchestration
from actuator.provisioners.openstack.resource_tasks import OpenstackProvisioner
from hadoop import HadoopInfra, HadoopNamespace, HadoopConfig


def do_it(num_slaves=1, handler=None, pkf="actuator-dev-key", rempass=None,
          infra_class=HadoopInfra,
          provisioner=OpenstackProvisioner(num_threads=10, cloud_name="citycloud"),
          overrides=()):
    inf = infra_class("infra", event_handler=handler)
    namespace = HadoopNamespace()
    namespace.add_override(*overrides)
    namespace.create_slaves(num_slaves)
    conf = HadoopConfig(remote_user="ubuntu",
                        private_key_file=pkf,
                        remote_pass=rempass,
                        event_handler=handler)

    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 provisioner=provisioner,
                                 namespace_model_inst=namespace,
                                 config_model_inst=conf,
                                 post_prov_pause=10,
                                 num_threads=20)
    try:
        success = orch.initiate_system()
    except KeyboardInterrupt:
        success = False
    return success, inf, namespace, conf, orch


if __name__ == "__main__":
    success, inf, ns, conf, orch = do_it(1)
    sys.stdout.write("Hit ctrl-d to decommission")
    sys.stdin.read()
    orch.teardown_system()
