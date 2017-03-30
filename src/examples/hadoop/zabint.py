from zabbix_client import ZabbixServerProxy
from actuator.provisioners.openstack.resources import Server, FloatingIP


class Zabact(object):
    def __init__(self, ipaddr, user, pw):
        """
        Set up Actuator/Zabbix integration
        :param ipaddr: local address of the Zabbix server. This may be different from the
            address used by the agents, in particular if the server is behind a firewall.
        :param user: Zabbix login user name
        :param pw: password for the user
        """
        self.zapi = ZabbixServerProxy("http://%s/zabbix" % ipaddr)
        self.token = self.zapi.user.login(user=user, password=pw)

    def _server_params(self, fip, groups, templates):
        assert isinstance(fip, FloatingIP)
        fip.server.get_display_name()
        params = {"host": fip.server.get_display_name(),
                  "groups": [{'groupid': g} for g in groups],
                  "templates": [{"templateid": t} for t in templates],
                  "interfaces": [
                      {"type": 1,
                       "main": 1,
                       "useip": 1,
                       "ip": fip.get_ip(),
                       "dns": "",
                       "port": "10050"}
                  ]}
        return params

    def register_servers_in_group(self, grouppame, server_fips, templates=()):
        matching = [d["groupid"] for d in self.zapi.hostgroup.get({})
                    if d.get("name") == grouppame]
        if not matching:
            raise Exception("Can't find the group %s" % grouppame)
        tids = [d["templateid"] for d in self.zapi.template.get({})
                if d.get("name") in templates]
        hgid = [matching[0]]
        results = []
        for f in server_fips:
            parms = self._server_params(f, hgid, tids)
            results.append(self.zapi.host.create(parms))
        return [d["hostids"][0] for d in results]

    def deregister_servers(self, host_id_list):
        if host_id_list:
            self.zapi.host.delete(*host_id_list)

