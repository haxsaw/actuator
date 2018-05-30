from actuator import InfraModel, ctxt
from actuator.provisioners.azure.resources import *
from rbacplug import *

# assume that the resources package contains pre-defined role objects that
# can be used to in role assignments as well a string names of roles:
#   Owner
#   Contributor
#   Reader
#   SecurityAdmin
#   ...etc


rempass = "C0rnD0ggi3"

common_server_args = dict(publisher="Canonical",
                          offer="UbuntuServer",
                          sku="16.04.0-LTS",
                          version="latest",
                          vm_size='Standard_DS1_v2',
                          admin_user="ubuntu",
                          admin_password=rempass)


class RBAC(InfraModel):
    rg = AzResourceGroup("group", "westus")
    network = AzNetwork("network", ctxt.model.rg, ["10.0.0.0/16"])
    subnet = AzSubnet("subnet", ctxt.model.rg, ctxt.model.network, "10.0.0.0/24")

    nic = AzNIC("nic", ctxt.model.rg, ctxt.model.network, [ctxt.model.subnet], public_ip=ctxt.model.pubip)
    pubip = AzPublicIP("pubip", ctxt.model.rg)
    server = AzServer("server", ctxt.model.rg, [ctxt.model.nic], **common_server_args)

    # Give the group net-admin-group the Contributor role to the network
    network_mgr = AzRoleAssignment("network-mgr", ctxt.model.network, Contributor, "net-admin-group")

    # Give the group prod-mgmt-group the Owner role to the entire resource group
    prod_mgr = AzRoleAssignment("prod-mgr", ctxt.model.rg, Owner, "prod-mgmt-group", can_delegate=False)

    # Give the group app-monitor-group the Reader role for the server
    monitor = AzRoleAssignment("monitor", ctxt.model.server, Reader, "app-monitor-group", can_delegate=True)

    # Give the server principle control-plane a custom role to the server
    control_plane_role = AzRole("cp-role", ctxt.model.server, "roleType",
                                actions=["Microsoft.Compute/virtualMachines/*"])
    control_plane = AzRoleAssignment("control-plane", ctxt.model.server, ctxt.model.control_plane_role,
                                     "control-plane", can_delegate=True)
