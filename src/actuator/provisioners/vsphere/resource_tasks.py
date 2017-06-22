import random
import time
from errator import narrate
from pyVmomi import vim
from pyVim import connect
from actuator.utils import capture_mapping
from actuator.provisioners.vsphere.resources import (Datastore, TemplatedServer,
                                                     ResourcePool)
from actuator.provisioners.core import (ProvisioningTask, ProvisionerException, BaseTaskSequencerAgent,
                                        BaseProvisioner)
from actuator.provisioners.vsphere.utils import wait_for_task, get_obj
from actuator.utils import LOG_INFO, root_logger

_vs_domain = "vsphere_task_domain"


@capture_mapping(_vs_domain, Datastore)
class ProvisionDatastoreTask(ProvisioningTask):
    @narrate(lambda s, _: "...which started the provisioning of the datastore {}".format(s.rsrc.get_dspath()))
    def _perform(self, engine):
        run_context = engine.get_context()
        vcenter = run_context.vcenter
        datastore = get_obj(vcenter.RetrieveContent(), [vim.Datastore], self.rsrc.get_dspath())
        if datastore is None:
            raise ProvisionerException("Couldn't find data store %s" % self.rsrc.get_dspath())
        self.rsrc.set_vs_datastore(datastore)

    @narrate(lambda s, _: "...which started the de-provisioning of the datastore {}".format(s.rsrc.name))
    def _reverse(self, engine):
        return


@capture_mapping(_vs_domain, ResourcePool)
class ProvisionResourcePoolTask(ProvisioningTask):
    @narrate(lambda s, _: "...and that initiated provisioning resource pool {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
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
    def _reverse(self, engine):
        return


@capture_mapping(_vs_domain, TemplatedServer)
class ProvisionTemplatedServer(ProvisioningTask):
    def depends_on_list(self):
        deps = []
        if isinstance(self.rsrc.get_data_store(), Datastore):
            deps.append(self.rsrc.get_data_store())
        if isinstance(self.rsrc.get_resource_pool(), ResourcePool):
            deps.append(self.rsrc.get_resource_pool())
        return deps

    @staticmethod
    def dot2dash(text):
        return text.replace(".", "-")

    @narrate(lambda s, _: "...which started the process of provisioning templated server {}".format(s.rsrc.name))
    def _perform(self, engine):
        run_context = engine.get_context()
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

        clonespec = vim.vm.CloneSpec()
        clonespec.location = relospec
        clonespec.powerOn = True

        task = template.Clone(folder=datacenter.vmFolder,
                              name=self.dot2dash(self.rsrc.get_display_name()),
                              spec=clonespec)
        # FIXME: we're not looking at returns here!
        wait_for_task(task)

        guest_ip = None
        while not guest_ip:
            vm = get_obj(content, [vim.VirtualMachine], self.dot2dash(self.rsrc.get_display_name()))
            guest_ip = vm.summary.guest.ipAddress
            if not guest_ip:
                time.sleep(0.25)
        self.rsrc.set_ip(guest_ip)

    def _reverse(self, engine):
        run_context = engine.get_context()
        vcenter = run_context.vcenter
        content = vcenter.RetrieveContent()
        vm = get_obj(content, [vim.VirtualMachine],
                     self.dot2dash(self.rsrc.get_display_name()))
        if not vm:
            raise ProvisionerException("Can't find vm %s to deprovision it" % self.rsrc.get_display_name())
        if format(vm.runtime.powerState) == "poweredOn":
            t = vm.PowerOffVM_Task()
            wait_for_task(t)
        t = vm.Destroy_Task()
        wait_for_task(t)


class VSphereCredentials(object):
    def __init__(self, host, username, pwd):
        self.host = host
        self.username = username
        self.pwd = pwd


class VSphereRunContext(object):
    def __init__(self, credentials):
        assert isinstance(credentials, VSphereCredentials)
        self.credentials = credentials
        self._vcenter = None

    @property
    def vcenter(self):
        if not self._vcenter:
            try:
                si = connect.SmartConnect(host=self.credentials.host,
                                          user=self.credentials.username,
                                          pwd=self.credentials.pwd)
            except Exception as e:
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(e):
                    try:
                        import ssl
                        dc = ssl._create_default_https_context
                        ssl._create_default_https_context = ssl._create_unverified_context
                        si = connect.SmartConnect(host=self.credentials.host,
                                                  user=self.credentials.username,
                                                  pwd=self.credentials.pwd)
                        ssl._create_default_https_context = dc
                    except Exception as e1:
                        raise Exception(e1)
                else:
                    raise
            self._vcenter = si
        return self._vcenter


class VSRunContextFactory(object):
    def __init__(self, credentials):
        assert isinstance(credentials, VSphereCredentials)
        self.credentials = credentials

    def __call__(self):
        return VSphereRunContext(self.credentials)


class VSphereTaskSequencerAgent(BaseTaskSequencerAgent):
    def __init__(self, infra_model, run_context_factory, num_threads=5,
                 log_level=LOG_INFO, no_delay=True):
        super(VSphereTaskSequencerAgent, self).__init__(infra_model, _vs_domain, run_context_factory,
                                                        num_threads=num_threads, log_level=log_level,
                                                        no_delay=no_delay)


class VSphereProvisioner(BaseProvisioner):
    LOG_SUFFIX = "vs_provisioner"

    def __init__(self, creds=None, host=None, username=None, pwd=None, num_threads=5,
                 log_level=LOG_INFO):
        if not creds and not (host and username and pwd):
            raise ProvisionerException("you must supply either a VSphereCredentials instance or else "
                                       "a host/username/pwd credentials set for vCenter")
        if not creds:
            creds = VSphereCredentials(host, username, pwd)
        elif not isinstance(creds, VSphereCredentials):
            raise ProvisionerException("The supplied creds object is not a kind of VSphereCredentials")

        self.ctxt_factory = VSRunContextFactory(creds)
        self.num_threads = num_threads
        self.log_level = log_level
        self.logger = root_logger.getChild(self.LOG_SUFFIX)
        self.logger.setLevel(self.log_level)
        self.agent = None

    @narrate("...which initiated the vSphere provisioning work")
    def _provision(self, inframodel_instance):
        self.logger.info("Starting to provision...")
        if self.agent is None:
            self.agent = VSphereTaskSequencerAgent(inframodel_instance, self.ctxt_factory,
                                                   num_threads=self.num_threads, log_level=self.log_level)
        self.agent.perform_tasks()
        self.logger.info("...provisioning complete")

    def _deprovision(self, inframodel_instance, record=None):
        self.logger.info("Starting to deprovision...")
        if self.agent is None:
            self.agent = VSphereTaskSequencerAgent(inframodel_instance, self.ctxt_factory,
                                                   num_threads=self.num_threads, log_level=self.log_level)
        self.agent.perform_reverses()
        self.logger.info("...deprovisioning complete.")
