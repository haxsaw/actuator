# 
# Copyright (c) 2014 Tom Carroll
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
"""
Amazon Web Services provisioner for Actuator
"""
import threading
from collections import defaultdict
from actuator.provisioners.core import (BaseProvisionerProxy, AbstractRunContext)
from actuator.provisioners.aws import aws_class_factory
from actuator.provisioners.aws.resource_tasks import _aws_domain

# boto3 resources are not thread safe, so we're going to make a per-thread cache
# for each type of resource so we re-use resources within a single thread

_session_by_thread_cache = defaultdict(lambda: aws_class_factory.get_aws_factory())

_session_resource_cache = defaultdict(dict)

_session_client_cache = defaultdict(dict)

_cache_lock = threading.RLock()

# AWS resource names
S3 = 's3'
EC2 = 'ec2'
SQS = 'sqs'
SNS = 'sns'
OPSWORKS = 'opsworks'
IAM = 'iam'
LAMBDA = 'lambda'
GLACIER = 'glacier'
DYNAMODB = 'dynamodb'
CLOUDWATCH = 'cloudwatch'
CLOUDFORMATION = 'cloudformation'


def _make_resource_key(resource_name, region_name, access_key_id, secret_access_key):
    return resource_name, region_name, access_key_id, secret_access_key


def get_resource(resource_name, region_name=None, aws_access_key_id=None, aws_secret_access_key=None):
    with _cache_lock:
        session = _session_by_thread_cache[threading.current_thread()]
    resource_cache = _session_resource_cache[session]
    key = _make_resource_key(resource_name, region_name, aws_access_key_id, aws_secret_access_key)
    resource = resource_cache.get(key)
    if resource is None:
        resource = session.resource(resource_name, region_name=region_name,
                                    aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        resource_cache[key] = resource
    return resource


def get_client(resource_name, region_name=None, aws_access_key_id=None, aws_secret_access_key=None):
    with _cache_lock:
        session = _session_by_thread_cache[threading.current_thread()]
    client_cache = _session_client_cache[session]
    key = _make_resource_key(resource_name, region_name, aws_access_key_id, aws_secret_access_key)
    client = client_cache.get(key)
    if client is None:
        client = session.client(resource_name, region_name=region_name,
                                aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        client_cache[key] = client
    return client


class _AWSCredentials(object):
    def __init__(self, region, aws_access_key, aws_secret_key):
        self.region = region
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key


class AWSRunContext(AbstractRunContext):
    def __init__(self, default_creds):
        self.default_creds = default_creds

    def ec2(self, region_name=None):
        return get_resource(EC2, self.default_creds.region if region_name is None else region_name,
                            self.default_creds.aws_access_key, self.default_creds.aws_secret_key)

    def lambda_(self, region_name=None):
        return get_client(LAMBDA, self.default_creds.region if region_name is None else region_name,
                            self.default_creds.aws_access_key, self.default_creds.aws_secret_key)

    def iam(self, region_name=None):
        return get_resource(IAM, self.default_creds.region if region_name is None else region_name,
                            self.default_creds.aws_access_key, self.default_creds.aws_secret_key)

    def ec2_client(self, region_name=None):
        return get_client(EC2, self.default_creds.region if region_name is None else region_name,
                          self.default_creds.aws_access_key, self.default_creds.aws_secret_key)


class AWSProvisionerProxy(BaseProvisionerProxy):
    mapper_domain_name = _aws_domain

    def __init__(self, name, default_region=None, aws_access_key=None, aws_secret_access_key=None):
        super(AWSProvisionerProxy, self).__init__(name)
        self.creds = _AWSCredentials(default_region, aws_access_key, aws_secret_access_key)

    def run_context_factory(self):
        return AWSRunContext(self.creds)


__all__ = ["AWSProvisionerProxy"]
