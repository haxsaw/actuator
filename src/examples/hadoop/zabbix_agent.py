import os.path
from actuator import *  # @UnusedWildImport
from actuator.provisioners.openstack.resources import *
from actuator.utils import find_file

zabbix_agent_secgroup = ResourceGroup("zabbix_rsrcs",
                                      zabbix_group=SecGroup("zabbix", "ZabbixGroup"),
                                      zabbix_tcp_rule=SecGroupRule("zabbix_tcp_rule",
                                                                   ctxt.comp.container.zabbix_group,
                                                                   ip_protocol="tcp",
                                                                   from_port=10050,
                                                                   to_port=10050)
                                      )


here, _ = os.path.split(__file__)
zabbix_conf_template = os.path.join(here, "zabbix-templates", "zabbix_agentd.conf")


class ZabbixConfig(ConfigModel):
    fetch_metadata = CommandTask("fetch_zabbix_pkg_metadata",
                                 "wget http://repo.zabbix.com/zabbix/3.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_3.0-1+trusty_all.deb",
                                 repeat_count=3, chdir="/tmp")
    add_repo_task = CommandTask("add_zabbix_repo",
                                "/usr/bin/sudo dpkg -i zabbix-release_3.0-1+trusty_all.deb",
                                repeat_count=3, chdir="/tmp")
    update_apt_task = CommandTask("update_repos",
                                  "/usr/bin/sudo apt-get -y update",
                                  repeat_count=3)
    install_zabbix = CommandTask("install_zabbix",
                                 "/usr/bin/sudo apt-get -y install zabbix-agent",
                                 repeat_count=3)
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
                            repeat_count=3)
    restart_zabbix = CommandTask("restart-zabbix",
                                 "/usr/bin/sudo service zabbix-agent restart",
                                 repeat_count=3)
    with_dependencies(fetch_metadata | add_repo_task | update_apt_task | install_zabbix)
    with_dependencies(install_zabbix | zabbix_config)
    with_dependencies(zabbix_config | move_config | restart_zabbix)
