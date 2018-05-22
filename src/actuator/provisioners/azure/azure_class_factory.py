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

"""
This module contains constructors for various Azure management clients, and provides a
way to override them mocking the clients out for tests
"""

import os
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient


class AzureCredentials(object):
    def __init__(self, subscription_id=None, client_id=None, secret=None, tenant=None):
        if subscription_id is None:
            subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if subscription_id is None:
            raise Exception("Missing subscription id in args or env")

        if client_id is None:
            client_id = os.environ.get("AZURE_CLIENT_ID")
        if client_id is None:
            raise Exception("Missing client id in args or env")

        if secret is None:
            secret = os.environ.get("AZURE_SECRET")
        if secret is None:
            raise Exception("Missing secret in args or env")

        if tenant is None:
            tenant = os.environ.get("AZURE_TENANT")
        if tenant is None:
            raise Exception("Missing tenant in args or env")

        self.subscription_id = subscription_id
        self.creds = ServicePrincipalCredentials(client_id=client_id,
                                                 secret=secret,
                                                 tenant=tenant)


def _real_get_azure_credentials(subscription_id=None, client_id=None, secret=None, tenant=None):
    # can be replaced to provide mocked credentials objects
    return AzureCredentials(subscription_id=subscription_id, client_id=client_id,
                            secret=secret, tenant=tenant)


def get_azure_credentials(subscription_id=None, client_id=None, secret=None, tenant=None):
    """
    Constructs an AzureCredentials instance to use when provisioning resources

    :param subscription_id: optional string; Azure subscription id. If missing, looks to the
        environment for AZURE_SUBSCRIPTION_ID
    :param client_id: optional string; Azure client id. If missing, looks to the
        environment for AZURE_CLIENT_ID.
    :param secret: optional string; Azure secret. If missing, looks to the
        environment for AZURE_SECRET.
    :param tenant: optional string; Azure tenant. If missing, looks to the
        environment for AZURE_TENENT.
    :return: AzureCredentials instance

    Raises an exception if any of the arg values can't be determined.
    """
    return _real_get_azure_credentials(subscription_id=subscription_id,
                                       client_id=client_id,
                                       secret=secret,
                                       tenant=tenant)


def _real_get_resource_client(creds):
    # returns an Azure resource client for the creds
    return ResourceManagementClient(creds.creds, creds.subscription_id)


def get_resource_client(creds):
    return _real_get_resource_client(creds)


def _real_get_compute_client(creds):
    return ComputeManagementClient(creds.creds, creds.subscription_id)


def get_compute_client(creds):
    return _real_get_compute_client(creds)


def _real_get_network_client(creds):
    return NetworkManagementClient(creds.creds, creds.subscription_id)


def get_network_client(creds):
    return _real_get_network_client(creds)
