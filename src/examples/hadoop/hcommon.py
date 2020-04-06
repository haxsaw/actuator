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

import os
from actuator.namespace import *
from actuator.config import *
from actuator.config_tasks import *
from actuator import ctxt
from actuator.utils import find_file


hadoop_ver = "hadoop-1.2.1"

pkn = "actuator-dev-key"

common_vars = [Var("USER", "ubuntu"),
               Var("BASE", "/home/!{USER}/tmp", in_env=False),
               Var("TEMP_PUB_KEY", "!{BASE}/tpk"),
               Var("COMP_NAME", ctxt.name, in_env=False),
               Var("HADOOP_VER", hadoop_ver, in_env=False),
               Var("HADOOP_TARBALL", "!{HADOOP_VER}.tar.gz", in_env=False),
               Var("HADOOP_REPO", "https://archive.apache.org/dist/hadoop/core", in_env=False),
               Var("HADOOP_URL",
                   "!{HADOOP_REPO}/!{HADOOP_VER}/!{HADOOP_TARBALL}", in_env=False),
               Var("HADOOP_PREP", "!{BASE}/hadoop", in_env=False),
               Var("HADOOP_DATA_HOME", "!{HADOOP_PREP}/data", in_env=False),
               Var("HADOOP_DATA_XACTION", "!{HADOOP_DATA_HOME}/xaction", in_env=False),
               Var("HADOOP_DATA_BLOCKS", "!{HADOOP_DATA_HOME}/blocks", in_env=False),
               Var("HADOOP_TRACKER_HOME", "!{HADOOP_PREP}/tracker", in_env=False),
               Var("HADOOP_TRACKER_SYSTEM", "!{HADOOP_TRACKER_HOME}/system", in_env=False),
               Var("HADOOP_TRACKER_LOCAL", "!{HADOOP_TRACKER_HOME}/local", in_env=False),
               Var("HADOOP_HOME", "!{HADOOP_PREP}/!{HADOOP_VER}"),
               Var("HADOOP_CONF_DIR", "!{HADOOP_HOME}/conf"),
               Var("HADOOP_HEAPSIZE", "1000"),
               # these two work only for CityCloud/Openstack
               Var("JAVA_HOME", "/usr/lib/jvm/java-7-openjdk-amd64"),
               Var("JAVA_VER", "openjdk-7-jre-headless", in_env=False),
               # Ubuntu 10.04 on vSphere needs openjdk-8
               # this next var is a default value only for testing
               # this namespace model in isolation; the wrapper task
               # should redefine NODNAME_IP to be an ip from the
               # provisioned infra
               Var("NAMENODE_IP", "!{IP_ADDR}"),
               # These Vars are also used by the infra model to specify the
               # various ports used for Hadoop and its web interfaces
               Var("NAMENODE_PORT", "50071"),
               Var("NAMENODE_WEBUI_PORT", "50070"),
               Var("JOBTRACKER_PORT", "50031"),
               Var("JOBTRACKER_WEBUI_PORT", "50030"),
               Var("PRIV_KEY_NAME", pkn),
               Var("ZABBIX_SERVER", os.environ.get("ZABBIX_SERVER") or "", in_env=False)]


def host_list(*ctx_exps, sep_char=" "):
    """
    This returns a callable that computes a list of ip addresses separated by
    the indicated character. This is one approach to constructing
    callable arguments that Actuator will invoke when it is needed.

    In this case, the ctx_exp is expected to return a dict-like object when
    "called" with the Actuator-supplied CallContext (the 'ctx' argument to
    host_list_inner()), in this case a MultiRole. We ask for the values() of
    that object to get the list of roles in the dict.
    """

    def host_list_inner(ctx):
        iplist = []
        for ctx_exp in ctx_exps:
            iplist.extend([role.host_ref.get_ip()
                           for role in ctx_exp(ctx).values()
                           if role is not None])
        return sep_char.join(iplist)

    return host_list_inner


class HadoopNamespace(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("SLAVE_IPS", host_list(ctxt.model.slaves)),
                   Var("NAMENODE_IP", ctxt.nexus.inf.name_node_fip.get_ip))
    # set up cloud parameters
    with_variables(Var("IMAGE", "Ubuntu 14.04 - LTS - Trusty Tahr"),
                   Var("EXTNET", "ext-net"),
                   Var("AZ", "Lon1"))

    name_node = Role("name_node",
                     host_ref=ctxt.nexus.inf.name_node_fip)
    slaves = MultiRole(Role("slave",
                            host_ref=ctxt.nexus.inf.slaves[ctxt.name].slave_fip,
                            variables=[Var("COMP_NAME", "slave_!{COMP_KEY}"),
                                       Var("COMP_KEY", ctxt.name)]))

    def create_slaves(self, count):
        """
        This method takes care of the creating the references to additional
        slave Roles, which in turn creates more slave infra resources.
        """
        return [self.slaves[i] for i in range(count)]


here, _ = os.path.split(__file__)
zabbix_conf_template = os.path.join(here, "zabbix-templates", "zabbix_agentd.conf")


class ZabbixConfig(ConfigModel):
    fetch_metadata = CommandTask("fetch_zabbix_pkg_metadata",
                                 "wget http://repo.zabbix.com/zabbix/3.0/ubuntu/pool/main/z/zabbix-release/"
                                 "zabbix-release_3.0-2+bionic_all.deb",
                                 # "zabbix-release_3.0-1+trusty_all.deb",
                                 repeat_count=4, chdir="/tmp")
    add_repo_task = CommandTask("add_zabbix_repo",
                                "/usr/bin/sudo dpkg -i zabbix-release_3.0-2+bionic_all.deb",
                                # "/usr/bin/sudo dpkg -i zabbix-release_3.0-1+trusty_all.deb",
                                repeat_count=3, chdir="/tmp")
    update_apt_task = CommandTask("update_repos",
                                  "/usr/bin/sudo apt-get -y update",
                                  repeat_count=4)
    install_zabbix = CommandTask("install_zabbix",
                                 "/usr/bin/sudo apt-get -y install zabbix-agent",
                                 repeat_count=4)
    # the template here relies on:
    # ZABBIX_SERVER as the ip of the Zabbix server
    # HOST for the name of the host the agent should report as
    zabbix_config = ProcessCopyFileTask("copy-zabbix-config",
                                        "/tmp/zabbix_agentd.conf",
                                        src=zabbix_conf_template,
                                        repeat_count=3)
    move_config = ShellTask("move_config",
                            "/usr/bin/sudo /bin/rm -f /etc/zabbix/zabbix_agentd.conf.old;"
                            "/usr/bin/sudo /bin/mv /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agentd.conf.old;"
                            "/usr/bin/sudo /bin/cp /tmp/zabbix_agentd.conf /etc/zabbix/zabbix_agentd.conf",
                            repeat_count=4)
    restart_zabbix = CommandTask("restart-zabbix",
                                 "/usr/bin/sudo service zabbix-agent restart",
                                 repeat_count=3)
    with_dependencies(fetch_metadata | add_repo_task | update_apt_task | install_zabbix)
    with_dependencies(install_zabbix | zabbix_config)
    with_dependencies(zabbix_config | move_config | restart_zabbix)


class HadoopNodeConfig(ConfigModel):
    # first describe all the tasks; order isn't important
    ping = PingTask("ping_to_check_alive", repeat_count=5)
    send_priv_key = CopyFileTask("send_priv_key", "!{HADOOP_PREP}/!{PRIV_KEY_NAME}",
                                 src=find_file(pkn, "."),
                                 mode=384  # dec for octal 0600
                                 )
    zabbix_setup = ConfigClassTask("zabbix-install", ZabbixConfig, init_args=("zabbix-config",))
    update = CommandTask("update_all",
                         "/usr/bin/sudo -h localhost "
                         "/usr/bin/apt-get -y update",
                         repeat_count=3)
    jdk_install = CommandTask("jdk_install",
                              "/usr/bin/sudo -h localhost "
                              "/usr/bin/apt-get -y install !{JAVA_VER}",
                              repeat_count=5)
    reset = CommandTask("reset", "/bin/rm -rf !{HADOOP_PREP}",
                        repeat_count=3)
    make_home = CommandTask("make_home", "/bin/mkdir -p !{HADOOP_PREP}",
                            creates="!{HADOOP_PREP}",
                            repeat_count=3)
    make_data_home = CommandTask("make_data_home", "/bin/mkdir -p !{HADOOP_DATA_HOME}",
                                 creates="!{HADOOP_DATA_HOME}",
                                 repeat_count=3)
    make_transactions = CommandTask("make_transactions", "/bin/mkdir -p !{HADOOP_DATA_XACTION}",
                                    creates="!{HADOOP_DATA_XACTION}",
                                    repeat_count=5)
    make_block_home = ShellTask("make_block_home",
                                "/bin/mkdir -p !{HADOOP_DATA_BLOCKS}; /bin/chmod 755 !{HADOOP_DATA_BLOCKS}",
                                creates="!{HADOOP_DATA_BLOCKS}",
                                repeat_count=3)
    make_tracker_home = CommandTask("make_tracker_home", "/bin/mkdir -p !{HADOOP_TRACKER_HOME}",
                                    creates="!{HADOOP_TRACKER_HOME}",
                                    repeat_count=3)
    make_tracker_system = CommandTask("make_tracker_system", "/bin/mkdir -p !{HADOOP_TRACKER_SYSTEM}",
                                      creates="!{HADOOP_TRACKER_SYSTEM}",
                                      repeat_count=3)
    make_tracker_local = CommandTask("make_tracker_local", "/bin/mkdir -p !{HADOOP_TRACKER_LOCAL}",
                                     creates="!{HADOOP_TRACKER_LOCAL}",
                                     repeat_count=3)
    fetch_hadoop = CommandTask("fetch_hadoop", "/usr/bin/wget !{HADOOP_URL}",
                               chdir="!{HADOOP_PREP}",
                               repeat_count=4)
    unpack = CommandTask("unpack_hadoop", "/bin/tar -xf !{HADOOP_TARBALL}",
                         chdir="!{HADOOP_PREP}",
                         repeat_count=3)
    add_hostname = ShellTask("add_hostname",
                             "/usr/bin/sudo -h localhost /bin/bash -c "
                             "'/bin/echo 127.0.1.1 `/bin/hostname` >> /etc/hosts'",
                             repeat_count=3)
    copy_public_key = CopyFileTask("copy_public_key",
                                   "!{TEMP_PUB_KEY}",
                                   src=find_file("%s.pub" % pkn, "."),
                                   repeat_count=3)
    append_public_key = ShellTask("append_public_key",
                                  "cat !{TEMP_PUB_KEY} >> ~/.ssh/authorized_keys; rm -f !{TEMP_PUB_KEY}",
                                  repeat_count=3)

    # template processing tasks
    # compute the template search root from the current directory
    search_root = os.path.join(os.getcwd(),
                               "{}-templates".format(hadoop_ver))
    send_env = ProcessCopyFileTask("send_env", "!{HADOOP_CONF_DIR}/hadoop-env.sh",
                                   src=find_file("hadoop-env.sh", search_root),
                                   backup=True
                                   )
    send_core_site = ProcessCopyFileTask("send_core_site",
                                         "!{HADOOP_CONF_DIR}/core-site.xml",
                                         src=find_file("core-site.xml",
                                                       search_root),
                                         backup=True)
    send_hdfs_site = ProcessCopyFileTask("send_hdfs_site",
                                         "!{HADOOP_CONF_DIR}/hdfs-site.xml",
                                         src=find_file("hdfs-site.xml",
                                                       search_root),
                                         backup=True)
    send_mapred_site = ProcessCopyFileTask("send_mapred_site",
                                           "!{HADOOP_CONF_DIR}/mapred-site.xml",
                                           src=find_file("mapred-site.xml",
                                                         search_root),
                                           backup=True)

    # now express the dependencies between config tasks. each call to
    # with_dependencies() is additive; the set of dependencies are captured in
    # the metadata for the class, and evaluated in total at the proper time
    with_dependencies(ping | update | jdk_install | (reset & add_hostname))

    with_dependencies(reset | make_home | (send_priv_key & fetch_hadoop &
                                           (copy_public_key | append_public_key)) |
                      unpack | (send_env & send_core_site & send_hdfs_site &
                                send_mapred_site))

    with_dependencies(add_hostname | zabbix_setup)

    with_dependencies(make_home | make_data_home | (make_transactions &
                                                    make_block_home))

    with_dependencies(make_home | make_tracker_home | (make_tracker_system &
                                                       make_tracker_local))


class HadoopConfig(ConfigModel):

    namenode_setup = ConfigClassTask("nn_suite", HadoopNodeConfig, init_args=("namenode-setup",),
                                     task_role=HadoopNamespace.name_node)

    slaves_setup = MultiTask("slaves_setup",
                             ConfigClassTask("setup_suite", HadoopNodeConfig, init_args=("slave-setup",)),
                             HadoopNamespace.q.slaves.all())

    slave_ips = ShellTask("slave_ips",
                          "for i in localhost !{SLAVE_IPS}; do echo $i; done"
                          " > !{HADOOP_CONF_DIR}/slaves",
                          task_role=HadoopNamespace.name_node)

    format_hdfs = CommandTask("format_hdfs",
                              "bin/hadoop namenode -format -nonInteractive -force",
                              chdir="!{HADOOP_HOME}", repeat_count=3,
                              task_role=HadoopNamespace.name_node)

    with_dependencies(namenode_setup | format_hdfs)
    with_dependencies((namenode_setup & slaves_setup) | slave_ips)


class DemoPlatform(object):
    """
    provides some common management of supplying demo-able objects for the Hadoop demo
    """
    def get_infra_instance(self, inst_name):
        raise TypeError("Derived class must implement")

    def get_platform_proxy(self):
        raise TypeError("Derived class must implement")

    def get_supplemental_vars(self):
        raise TypeError("Derived class must implement")

    def get_infra_class(self):
        raise TypeError("Derived class must implement")

    def platform_name(self):
        raise TypeError("Derived class must implement")

    def get_config_kwargs(self):
        return dict(pkf="actuator-dev-key", rempass=None)

