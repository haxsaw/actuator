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

import time
from actuator.provisioners.core import ProvisioningTask, ProvisionerException
from actuator.provisioners.gcp.resources import *
from actuator.utils import capture_mapping

_gcp_domain = "GCP"


@capture_mapping(_gcp_domain, GCPServer)
class GCPServerTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        compute = run_context.compute
        config = {'name': self.rsrc.name,
                  'machineType': self.rsrc.machine_type,
                  'disks': [{'boot': True,
                             'autoDelete': True,
                             'initializeParams': {
                                 'sourceImage': self.rsrc.disk_image
                             }
                             }],
                  'networkInterfaces': [{'network': 'global/networks/default',
                                         "accessConfigs": [{'type': 'ONE_TO_ONE_NAT',
                                                            'name': 'External NAT'}]
                                         }],
                  'metadata': {'enable-oslogin': "TRUE",
                               "items": [{'enable-oslogin': "TRUE"}]}
                  }
        proj = proxy.project
        zone = proxy.get_zone(self.rsrc)
        result = compute.instances().insert(project=proj,
                                            zone=zone,
                                            body=config).execute()

        while True:   # @FIXME; should be while not quit!
            watch = compute.zoneOperations().get(project=proj,
                                                 zone=zone,
                                                 operation=result['name']).execute()
            if watch['status'] == 'DONE':
                if 'error' in watch:
                    raise ProvisionerException("GCPServer provisioning failed: %s" % watch['error'])
                break
            time.sleep(5)
        # now get the data for the instance
        inst = compute.instances().get(project=proj,
                                       zone=zone,
                                       instance=self.rsrc.name).execute()
        self.rsrc.gcp_id = inst["id"]
        self.rsrc.self_link = inst["selfLink"]
        self.rsrc.gcp_data = inst
        # public IP is at:
        # inst['networkInterfaces'][0]['accessConfigs'][0]['natIP']
        _ = 0

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        compute = run_context.compute
        proj = proxy.project
        zone = proxy.get_zone(self.rsrc)
        result = compute.instances().delete(instance=self.rsrc.name,
                                            project=proj,
                                            zone=zone).execute()
        _ = 0


@capture_mapping(_gcp_domain, GCPIPAddress)
class GCPIPAddressTask(ProvisioningTask):
    def _perform(self, proxy):
        # this will need to become more complex when we don't just
        # take the default-generated external IP address, but for now
        # this will be good enough
        rsrc = self.rsrc
        assert isinstance(rsrc, GCPIPAddress)
        inst = rsrc.instance
        if inst is not None:
            assert isinstance(inst, GCPServer)
            inst_data = inst.get_gcp_data()
            ip = (inst_data['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                  if inst_data is not None
                  else None)
        else:
            ip = None
        rsrc.set_ip(ip)


@capture_mapping(_gcp_domain, GCPSSHPublicKey)
class GCPSSHPublicKeyTask(ProvisioningTask):
    def _peform(self, proxy):
        rsrc = self.rsrc
        assert isinstance(rsrc, GCPSSHPublicKey)
        # FIXME: the oslogin might be something to get from a different credentials set
        oslogin = proxy.oslogin
        creds = proxy.creds
        if rsrc.public_key_data is not None:
            key_data = rsrc.public_key_data
        else:
            try:
                key_data = open(rsrc.public_key_fileame, 'r').read().strip()
            except IOError as e:
                raise ProvisionerException("Couldn't open the public_key_filename %s; %s" %
                                           (rsrc.public_key_fileame, str(e)))
        profile = oslogin.users().getLoginProfile(name="users/" + creds.service_account_email).execute()

        # look through the existing keys; if you find this one already then you're done
        if not any(key_data in v['key'] for v in profile['sshPublicKeys'].values()):
            body = {'key': key_data,
                    'expirationTimeUsec': time.time() + 1000000 * rsrc.expirationTimeInSecs}
            result = oslogin.users().importSshPublicKey(parent='users/' + creds.service_account_email,
                                                        body=body).execute()
            # FIXME need a check for failure here...

    def _reverse(self, proxy):
        pass
