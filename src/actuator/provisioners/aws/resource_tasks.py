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

from actuator.provisioners.core import ProvisioningTask
from actuator.provisioners.aws.resources import *
# from actuator.provisioners.aws import AWSRunContext
from actuator.utils import capture_mapping

_aws_domain = "AWS_DOMAIN"


@capture_mapping(_aws_domain, VPC)
class VPCTask(ProvisioningTask):
    def _perform(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, VPC)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        vpc = ec2.create_vpc(CidrBlock=rsrc.cidr_block,
                             AmazonProvidedIpv6CidrBlock=rsrc.amazon_provided_ipv6_cidr_block,
                             InstanceTenancy=rsrc.instance_tenancy)
        vpc.wait_until_exists()
        rsrc.aws_id = vpc.vpc_id

    def _reverse(self, proxy):
        run_context = proxy.get_context()
        rsrc = self.rsrc
        assert isinstance(rsrc, VPC)
        ec2 = run_context.ec2(region_name=rsrc.cloud)
        vpc = ec2.Vpc(rsrc.aws_id)
        vpc.delete()
