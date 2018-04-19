#
# Copyright (c) 2017 Tom Carroll
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

import random
import time
from errator import narrate
from pyVmomi import vim
from actuator.infra import StaticServer
from actuator.utils import capture_mapping
from actuator.provisioners.vsphere.resources import (Datastore, TemplatedServer,
                                                     ResourcePool)
from actuator.provisioners.core import (ProvisioningTask, ProvisionerException)
from actuator.provisioners.vsphere.utils import wait_for_task, get_obj

_vs_domain = "vsphere_task_domain"


@capture_mapping(_vs_domain, StaticServer)
class ProvisionStaticServerTask(ProvisioningTask):
    @narrate(lambda s, _: "...which started the placeholder task for the already provisioned "
                          "static server {}".format(s.rsrc.name))
    def _perform(self, proxy):
        return

    @narrate(lambda s, _: "...thus starting the placeholder de-provision for static "
                          "server {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        return


@capture_mapping(_vs_domain, Datastore)
class ProvisionDatastoreTask(ProvisioningTask):
    @narrate(lambda s, _: "...which started the provisioning of the datastore {}".format(s.rsrc.get_dspath()))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        vcenter = run_context.vcenter
        datastore = get_obj(vcenter.RetrieveContent(), [vim.Datastore], self.rsrc.get_dspath())
        if datastore is None:
            raise ProvisionerException("Couldn't find data store %s" % self.rsrc.get_dspath())
        self.rsrc.set_vs_datastore(datastore)

    @narrate(lambda s, _: "...which started the de-provisioning of the datastore {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        return


@capture_mapping(_vs_domain, ResourcePool)
class ProvisionResourcePoolTask(ProvisioningTask):
    @narrate(lambda s, _: "...and that initiated provisioning resource pool {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        vcenter = run_context.vcenter  # this is a SmartConnect object
        content = vcenter.RetrieveContent()
        datacenter = content.rootFolder.childEntity[0]
        hosts = datacenter.hostFolder.childEntity
        if len(hosts) == 0:
            raise ProvisionerException("There are no host resource pools available in which to put the guest")
        pool_name = self.rsrc.get_pool_name()
        if pool_name is None:
            # then pick a pool at random
            pool = random.choice(hosts).resourcePool
        else:
            # find this pool and use it
            for h in hosts:
                if h.name == pool_name:
                    pool = h.resourcePool
                    break
            else:
                raise ProvisionerException("Unable to locate resource pool named %s" % pool_name)
        self.rsrc.set_resource_pool(pool)

    @narrate(lambda s, _: "...when we started to de-provision resource pool {}".format(s.rsrc.name))
    def _reverse(self, proxy):
        return


@capture_mapping(_vs_domain, TemplatedServer)
class ProvisionTemplatedServer(ProvisioningTask):
    def depends_on_list(self):
        the_things = set(super(ProvisionTemplatedServer, self).depends_on_list())
        if isinstance(self.rsrc.get_data_store(), Datastore):
            the_things.add(self.rsrc.get_data_store())
        if isinstance(self.rsrc.get_resource_pool(), ResourcePool):
            the_things.add(self.rsrc.get_resource_pool())
        return list(the_things)

    @staticmethod
    def dot2dash(text):
        return text.replace(".", "-")

    @narrate(lambda s, _: "...which started the process of provisioning templated server {}".format(s.rsrc.name))
    def _perform(self, proxy):
        run_context = proxy.get_context()
        vcenter = run_context.vcenter
        content = vcenter.RetrieveContent()
        pool = self.rsrc.get_resource_pool().get_resource_pool()
        ds = self.rsrc.get_data_store().get_vs_datastore()
        template = get_obj(content, [vim.VirtualMachine], self.rsrc.get_template_name())
        if not template:
            raise ProvisionerException("Can't find template %s from which to make a new server" %
                                       self.rsrc.get_template_name())
        datacenter = content.rootFolder.childEntity[0]
        relospec = vim.vm.RelocateSpec()
        relospec.datastore = ds
        relospec.pool = pool

        # this chunk is supposed to instruct vSphere to be sure to make a new
        # MAC address for the network interface in the template
        vsd = vim.vm.device.VirtualDeviceSpec()
        vsd.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        # now find the existing network device and make that the device to update
        for dev in template.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualVmxnet):
                vsd.device = dev
                break
        else:
            raise ProvisionerException("Can't find an existing network device on the template")
        vmconf = vim.vm.ConfigSpec(numCPUs=1, memoryMB=1024)
        vmconf.cpuHotAddEnabled = True
        vmconf.memoryHotAddEnabled = True
        vmconf.deviceChange = [vsd]

        clonespec = vim.vm.CloneSpec(config=vmconf)
        clonespec.location = relospec
        clonespec.powerOn = True

        task = template.Clone(folder=datacenter.vmFolder,
                              name=self.dot2dash(self.rsrc.get_display_name()),
                              spec=clonespec)
        res = wait_for_task(task)
        if res:
            raise ProvisionerException("Creating the cloned VM failed with %s" % str(res))

        guest_ip = None
        while not guest_ip:
            vm = get_obj(content, [vim.VirtualMachine], self.dot2dash(self.rsrc.get_display_name()))
            guest_ip = vm.summary.guest.ipAddress
            if not guest_ip:
                time.sleep(0.25)
        self.rsrc.set_ip(guest_ip)

    @narrate(lambda s, _: "...and then the deprovision of %s started" % s.rsrc.name)
    def _reverse(self, proxy):
        run_context = proxy.get_context()
        vcenter = run_context.vcenter
        content = vcenter.RetrieveContent()
        vm = get_obj(content, [vim.VirtualMachine],
                     self.dot2dash(self.rsrc.get_display_name()))
        if not vm:
            raise ProvisionerException("Can't find vm %s to deprovision it" % self.rsrc.get_display_name())
        if format(vm.runtime.powerState) == "poweredOn":
            t = vm.PowerOffVM_Task()
            res = wait_for_task(t)
            if res:
                raise ProvisionerException("PowerOff VM task failed with %s" % str(res))
        t = vm.Destroy_Task()
        res = wait_for_task(t)
        if res:
            raise ProvisionerException("Destroy VM task failed with %s" % str(res))
