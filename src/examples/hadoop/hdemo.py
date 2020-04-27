#
# Copyright (c) 2018 Tom Carroll
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

import json
import os
import sys
from pprint import pprint
import six
import traceback
from errator import get_narration
from actuator import ActuatorOrchestration
from actuator.reporting import namespace_report, security_check
from actuator.utils import persist_to_dict, reanimate_from_dict
from hcommon import HadoopConfig, HadoopNamespace
from prices import create_price_table
from awshadoop import AWSDemo
from azurehadoop import AzureDemo
from openstackhadoop import OpenstackDemo

with_mongo = False
inst_id = None  # gets set when we are to save in mongo
with_zabbix = False
with_viz = False
zabbix_host_ids = []   # gets set if we inform zabbix of our new hosts
template_list = ["Template App SSH Service", "Template ICMP Ping", "Template OS Linux"]


def do_it(infra_class, proxy,
          num_slaves=1, handler=None, pkf="actuator-dev-key", rempass=None,
          cloud_name="citycloud", overrides=(), client_data={}):
    """
    Stands up a hadoop infra and configures it
    """
    inf = infra_class("hadoop-infra")
    namespace = HadoopNamespace("hadoop-ns")
    namespace.add_override(*overrides)
    namespace.create_slaves(num_slaves)
    conf = HadoopConfig("hadoop-conf", remote_user="ubuntu",
                        private_key_file=pkf,
                        remote_pass=rempass)

    orch = ActuatorOrchestration(infra_model_inst=inf,
                                 provisioner_proxies=[proxy],
                                 namespace_model_inst=namespace,
                                 config_model_inst=conf,
                                 post_prov_pause=10,
                                 num_threads=num_slaves*2+10,
                                 client_keys=client_data,
                                 event_handler=handler)
    try:
        success = orch.initiate_system()
    except KeyboardInterrupt:
        success = False
    return success, inf, namespace, conf, orch


def make_infra_for_forecast(num_slave, infra_class):
    inf = infra_class("forecast")
    ns = HadoopNamespace("hadoop-namespace")
    ns.set_infra_model(inf)
    for i in range(num_slaves):
        _ = inf.slaves[i]
    inf.compute_provisioning_from_refs(inf.refs_for_components())
    for c in inf.components():
        c.fix_arguments()
    return inf


class DemoState(object):
    persist_op = "p=persist model"
    standup_op = "s=stand-up hadoop"
    rerun_op = "r=re-run stand-up"
    teardown_op = "t=teardown known system"
    load_op = "l=load persisted model"
    forecast_op = "f=forecast"
    namespace_op = "n=namespace report"
    security_op = "u=security report"
    quit_op = "q=quit"
    base_ops = [quit_op, load_op, forecast_op, namespace_op, security_op]

    def __init__(self):
        self.success = None
        self.infra = None
        self.ns = None
        self.conf = None
        self.ao = None
        self.ao_was_loaded = False
        self.quit = False
        self.inst_id = None
        self.json_file = None
        self.current_ops = list(self.base_ops)

    def populate_from_orchestrator(self):
        self.infra = self.ao.infra_model_inst
        self.ns = self.ao.namespace_model_inst
        self.conf = self.ao.config_model_inst

    def capture_orchestration_run_results(self, success, infra, ns, conf, ao):
        self.success, self.infra, self.ns, self.conf, self.ao = \
            success, infra, ns, conf, ao

    @staticmethod
    def cmd_char(command):
        """pass in one of the class-level command constants"""
        return command[0]

    def reset_ops(self):
        self.current_ops = list(self.base_ops)
        return self

    def set_available_ops(self):
        if self.ao:
            self.current_ops.extend([self.persist_op, self.teardown_op, self.rerun_op])
        elif not self.json_file:
            self.current_ops.append(self.standup_op)

    def get_current_prompt(self):
        return self.current_ops

    def is_allowed(self, cmd_chr):
        return cmd_chr and (cmd_chr[0] in self.get_current_cmd_chrs())

    def is_cmd(self, actual, possible):
        return actual and (actual[0] == possible[0])

    def get_current_cmd_chrs(self):
        return [c[0] for c in self.current_ops]


def prompt_until(prompt, response_type):
    """
    prompts the user for a piece of data and doesn't return until a response of the correct type
    is entered. returns with the response of the proper type
    :param prompt: string to prompt the user
    :param response_type: type that the response will be converted to
    :return: user entered data coerced to response_type
    """
    while True:
        six.print_(prompt,)
        response = sys.stdin.readline().strip()
        try:
            final = response_type(response)
            break
        except:
            six.print_("Wrong data type")
    return final


platform_map = {'a': AWSDemo(),
                'z': AzureDemo(),
                'o': OpenstackDemo()}


if __name__ == "__main__":
    # this is all command line and environment processing overhead
    if len(sys.argv) == 2:
        arg1 = sys.argv[1].lower()
        with_mongo = "m" in arg1
        with_zabbix = "z" in arg1
        with_viz = "v" in arg1

    if with_zabbix:
        six.print_("You must set the ZABBIX_SERVER environment var to the public IP of the server,")
        six.print_("and ZABBIX_PRIVATE is set to the internal IP of the server")
        if not os.environ.get("ZABBIX_SERVER") or not os.environ.get("ZABBIX_PRIVATE"):
            six.print_("...variables missing; exiting.")
            sys.exit(1)

    if with_mongo:
        six.print_("Ensure that mongod is running")

    if with_viz:
        import time
        import zmq
        from event_sender import TaskEventForwarder
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.connect("tcp://127.0.0.1:5001")
        time.sleep(0.1)
        handler = TaskEventForwarder(socket)
        six.print_("Visualisation activated")
    else:
        handler = None

    demo = DemoState()

    quit = False
    while not quit:
        demo.reset_ops().set_available_ops()
        six.print_("%s" % (", ".join(demo.get_current_prompt())))
        six.print_("/".join(demo.get_current_cmd_chrs()), ": ",)
        cmd = sys.stdin.readline().strip().lower()
        if not demo.is_allowed(cmd):
            six.print_("Command not recognised at this this time or unknown: %s" % cmd)

        if demo.is_cmd(cmd, DemoState.quit_op):
            six.print_("goodbye")
            sys.exit(0)

        # ################## generate namespace report
        if demo.is_cmd(cmd, DemoState.namespace_op):
            if demo.ao:
                six.print_("Using namespace from last orchestration")
                namespace = demo.ao.namespace_model_inst
            else:
                num_slaves = prompt_until("No current namespace; one will be created. How many slaves? ",
                                          int)
                namespace = HadoopNamespace("TrialNamespace")
                namespace.create_slaves(num_slaves)
            report = namespace_report(namespace)
            for l in report:
                six.print_(l)
            del namespace
            continue

        # ################## generate security report
        if demo.is_cmd(cmd, DemoState.security_op):
            if demo.ao:
                six.print_("Using infra from last orchestration")
                infra = demo.ao.infra_model_inst
                namespace = demo.ao.namespace_model_inst
            else:
                platform = prompt_until("Enter A for AWS, O for OpenStack, Z for Azure: ", str).lower()
                while not platform or platform[0] not in platform_map:
                    platform = prompt_until("Enter A for AWS, O for OpenStack, Z for Azure: ", str).lower()
                num_slaves = prompt_until("No current namespace; one will be created. How many slaves? ",
                                          int)
                infra = platform_map[platform[0]].get_infra_class()("SecTestInfra")
                namespace = HadoopNamespace("SecTestNamespace")
                namespace.set_infra_model(infra)
                namespace.create_slaves(num_slaves)
            six.print_("Security report for {} instance:".format(infra.__class__.__name__))
            pprint(security_check(infra))
            del namespace, infra
            continue

        # ################## standup hadoop
        if demo.is_cmd(cmd, DemoState.standup_op):
            num_slaves = prompt_until("How many slaves? ", int)
            platform = prompt_until("Enter A for AWS, O for OpenStack, Z for Azure: ", str).lower()
            while not platform or platform[0] not in platform_map:
                platform = prompt_until("Enter A for AWS, O for OpenStack, Z for Azure: ", str).lower()
            dp = platform_map[platform[0]]
            infra_class = dp.get_infra_class()
            config_kwargs = dp.get_config_kwargs()
            mykeys = {"platform": platform[0]}
            demo.capture_orchestration_run_results(*do_it(infra_class,
                                                          dp.get_platform_proxy(),
                                                          num_slaves=num_slaves,
                                                          handler=handler,
                                                          overrides=dp.get_supplemental_vars(),
                                                          client_data=mykeys,
                                                          **config_kwargs))
            # standup complete; do supplemental reporting & sibling notification
            if demo.success:
                if with_mongo:
                    from hreport import capture_running
                    six.print_("Storing model in Mongo...")
                    inst_id = capture_running(demo.ao, "hadoop_demo")
                    six.print_("...done. Instance id is '%s'" % inst_id)
                if with_zabbix:
                    six.print_("Updating Zabbix with new hosts to monitor...")
                    from zabint import Zabact
                    try:
                        za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                        zabbix_host_ids = za.register_servers_in_group("Linux servers", [demo.infra.name_node_fip.value()] +
                                                                       [s.slave_fip.value() for s in demo.infra.slaves.values()],
                                                                       templates=template_list)
                        six.print_("...done")
                    except Exception as e:
                        six.print_("\nZABBIX UPDATED FAILED with %s:" % str(e))
                        six.print_("...traceback:")
                        traceback.print_exception(*sys.exc_info())
                        six.print_()
                try:
                    six.print_("---Namespace report:")
                    for l in namespace_report(demo.ao.namespace_model_inst):
                        six.print_(l)
                except:
                    six.print_("PRINTING NAMESPACE REPORT FAILED:")
                    traceback.print_exc()
                try:
                    six.print_("---Security report:")
                    pprint(security_check(demo.ao.infra_model_inst))
                except:
                    six.print_("PRINTING SECURITY REPORT FAILED:")
                    traceback.print_exc()
                six.print_("---You can reach the assets at the following IPs:")
                six.print_(">>>namenode: %s" % demo.infra.name_node_fip.get_ip())
                six.print_(">>>slaves:")
                for s in demo.infra.slaves.values():
                    six.print_("\t%s" % s.slave_fip.get_ip())
                six.print_("\nExecution prices for this infra:\n")
                six.print_(create_price_table(demo.infra, dp.platform_name()))
            else:
                six.print_("Standup failed; see the log for details")

            continue

        # ################## teardown system
        if demo.is_cmd(cmd, DemoState.teardown_op):
            platform_key = demo.ao.client_keys["platform"]
            dp = platform_map[platform_key]
            proxy = dp.get_platform_proxy()
            demo.ao.set_provisioner_proxies([proxy])
            success = demo.ao.teardown_system()
            # teardown complete; update sibling systems
            if success:
                if inst_id is not None and with_mongo:
                    from hreport import capture_terminated
                    six.print_("Recording instance terminated in Mongo")
                    capture_terminated(demo.ao, inst_id)
                    six.print_("...done")
                if zabbix_host_ids and with_zabbix:
                    six.print_("Removing hosts from zabbix")
                    from zabint import Zabact
                    za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                    za.deregister_servers(zabbix_host_ids)
                    six.print_("...done")
                demo.success = demo.ao = demo.ns = demo.conf = demo.infra = demo.json_file = None
                six.print_("\n...done! Your system has been de-commissioned")
            else:
                six.print_("Teardown failed; see the log for errors")
            continue

        # ################## re-run standup
        if demo.is_cmd(cmd, DemoState.rerun_op):
            six.print_("RE-RUNNING initiate")
            demo.success = demo.ao.initiate_system()
            # retry attempt complete; do optional reporting
            if demo.success:
                if with_mongo:
                    from hreport import capture_running

                    six.print_("Storing model in Mongo...")
                    inst_id = capture_running(demo.ao, "hadoop_demo")
                    six.print_("...done. Instance id is '%s'" % inst_id)
                if with_zabbix:
                    six.print_("Updating Zabbix with new hosts to monitor...")
                    from zabint import Zabact

                    try:
                        za = Zabact(os.environ.get("ZABBIX_PRIVATE"), "Admin", "zabbix")
                        zabbix_host_ids = za.register_servers_in_group("Linux servers", [infra.name_node_fip.value()] +
                                                                       [s.slave_fip.value() for s in infra.slaves.values()],
                                                                       templates=template_list)
                        six.print_("...done")
                    except Exception as e:
                        six.print_("\nZABBIX UPDATED FAILED with %s:" % str(e))
                        six.print_("...traceback:")
                        traceback.print_exception(*sys.exc_info())
                        six.print_()
                six.print_("\n...done! You can reach the assets at the following IPs:")
                six.print_(">>>namenode: %s" % demo.infra.name_node_fip.get_ip())
                six.print_(">>>slaves:")
                for s in demo.infra.slaves.values():
                    six.print_("\t%s" % s.slave_fip.get_ip())
                    six.print_("\nExecution prices for this infra:\n")
                    six.print_(create_price_table(demo.infra, dp.platform_name()))
            else:
                six.print_("Retry of standup failed; see log for errors")
            continue

        # ################## generate forecast report
        if demo.is_cmd(cmd, DemoState.forecast_op):
            num_slaves = prompt_until("No current namespace; one will be created. How many slaves? ",
                                      int)
            for dp in platform_map.values():
                infra = make_infra_for_forecast(num_slaves, dp.get_infra_class())
                six.print_(">>>>>>For %s" % dp.platform_name())
                six.print_(create_price_table(infra, dp.platform_name()))
                six.print_()
            continue

        # ################## persist an orchestrator
        if demo.is_cmd(cmd, DemoState.persist_op):
            fname = prompt_until("Enter name of the file to save to: ", str)
            while not fname:
                fname = prompt_until("Enter name of the file to save to: ", str)
            six.print_("Creating persistable form...")
            try:
                d = persist_to_dict(demo.ao)
                json_dict = json.dumps(d)
            except Exception as e:
                six.print_("FAILED GETTING PERSISTED FORM; t = %s, v = %s" % (type(e), str(e)))
                six.print_("the story is:")
                for s in get_narration():
                    six.print_(s)
            else:
                six.print_("Writing persisted form out...")
                f = open(fname, "w")
                f.write(json_dict)
                six.print_("Orchestrator persisted!")
            continue

        # ################## reanimate an orchestrator
        if demo.is_cmd(cmd, DemoState.load_op):
            fname = prompt_until("Enter name of file to load: ", str)
            while not fname:
                fname = prompt_until("Enter name of file to load: ", str)
            if not os.path.exists(fname):
                six.print_("File can't be found! (%s)" % fname)
            else:
                try:
                    json_dict = open(fname, "r").read()
                except Exception as e:
                    six.print_("Got an exception reading %s: %s" % (fname, str(e)))
                else:
                    d = json.loads(json_dict)
                    demo.ao = reanimate_from_dict(d)
                    demo.populate_from_orchestrator()
                    demo.ao.set_event_handler(handler)
                    six.print_("Orchestrator reanimated!")
    if with_viz:
        socket.send('quit')

