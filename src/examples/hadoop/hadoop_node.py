# 
# Copyright (c) 2015 Tom Carroll
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

import sys
from actuator import *
from actuator.utils import find_file

hadoop_ver = "hadoop-1.2.1"

pkn = "actuator-dev-key"

common_vars = [Var("USER", "ubuntu"),
               Var("BASE", "/home/!{USER}/tmp", in_env=False),
               Var("TEMP_PUB_KEY", "!{BASE}/tpk"),
               Var("COMP_NAME", ctxt.name, in_env=False),
               Var("HADOOP_VER", hadoop_ver, in_env=False),
               Var("HADOOP_TARBALL", "!{HADOOP_VER}.tar.gz", in_env=False),
               Var("HADOOP_URL",
                   "http://mirror.ox.ac.uk/sites/rsync.apache.org/hadoop/"
                   "common/!{HADOOP_VER}/!{HADOOP_TARBALL}", in_env=False),
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
               Var("JAVA_HOME", "/usr/lib/jvm/java-7-openjdk-amd64"),
               Var("JAVA_VER", "openjdk-7-jre-headless", in_env=False),
               #this next var is a default value only for testing
               #this namespace model in isolation; the wrapper task
               #should redefine NODNAME_IP to be an ip from the
               #provisioned infra
               Var("NAMENODE_IP", "!{IP_ADDR}"),
               #this next Var is a default value only for testing
               #the value of the webport should ultimately come from the
               #infra model which will be setting up the security group rule
               #that explains how to reach the web server
               Var("NAMENODE_PORT", "50071"),
               Var("JOBTRACKER_PORT", "50031"),
               Var("PRIV_KEY_NAME", pkn)]


class DevNamespace(NamespaceModel):
    with_variables(*common_vars)
    with_variables(Var("IP_ADDR", None))
    s = Role("me", "!{IP_ADDR}")
    

class HadoopNodeConfig(ConfigModel):
    #first describe all the tasks; order isn't important
    ping = PingTask("ping_to_check_alive", repeat_count=5)
    send_priv_key = CopyFileTask("send_priv_key", "!{HADOOP_PREP}/!{PRIV_KEY_NAME}",
                                 src=find_file(pkn, "."),
                                 mode="0600"
                                 )
    update = CommandTask("update_linux",
                         "/usr/bin/sudo -h localhost /usr/bin/apt-get -y update",
                         repeat_count=3)
    jdk_install = CommandTask("jdk_install",
                              "/usr/bin/sudo -h localhost "
                              "/usr/bin/apt-get -y install !{JAVA_VER}",
                              repeat_count=3)
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
                                    repeat_count=3)
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
    fetch_hadoop = CommandTask("fetch_hadoop", "/usr/bin/wget -q !{HADOOP_URL}",
                               chdir="!{HADOOP_PREP}",
                               repeat_count=3)
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
                                  "cat !{TEMP_PUB_KEY} >> ~/.ssh/authorized_keys; rm !{TEMP_PUB_KEY}",
                                  repeat_count=3)
                                   
    #template processing tasks
    #compute the template search root from the current directory
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
    
    #now express the dependencies between the tasks. each call to
    #with_dependencies() is additive; the set dependencies are captured in
    #the metadata for the class, and evaluated in total at the proper time
    with_dependencies(ping | (reset & add_hostname))
    
    with_dependencies(reset | make_home | (send_priv_key & fetch_hadoop &
                                           copy_public_key & append_public_key) |
                      unpack | (send_env & send_core_site & send_hdfs_site &
                       send_mapred_site))
    
    with_dependencies(add_hostname | update | jdk_install)
    
    with_dependencies(make_home | make_data_home | (make_transactions &
                                                    make_block_home))
    
    with_dependencies(make_home | make_tracker_home | (make_tracker_system &
                                                       make_tracker_local))
        

if __name__ == "__main__":
    #this is just to test out the above configs on a single host
    #specifed by the user; normally this would be imported into the main
    #hadoop model
    if len(sys.argv) < 2:
        print "Usage: %s <FQDN or IP addr to run config on>"
        sys.exit(1)
    routable_host_or_ip = sys.argv[1]
    print "Using %s as the host to run the config on" % routable_host_or_ip
    
    ns = DevNamespace()
    ns.add_variable(Var("IP_ADDR", routable_host_or_ip))
    
    cfg = HadoopNodeConfig(remote_user="ubuntu", default_task_role=ns.s,
                           private_key_file=pkn)
    ea = AnsibleExecutionAgent(config_model_instance=cfg,
                               namespace_model_instance=ns)
    try:
        ea.perform_config()
        print "\n...all done!"
    except ExecutionException, e:
        print
        print "it blowed up with: ", e.message
        import traceback
        for t, et, ev, tb in ea.get_aborted_tasks():
            print ("Task %s (id %s) failed with the following:" %
                   (t.name, str(t._id)))
            traceback.print_exception(et, ev, tb)
            print

    