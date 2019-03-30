#
# Copyright (c) 2019 Tom Carroll
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

from googleapiclient import discovery
from google.cloud import storage
from oauth2client.service_account import ServiceAccountCredentials


class GCPCredentials(object):
    def __init__(self, json_credentials_file_path):
        self.json_credentials_file_path = json_credentials_file_path
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(json_credentials_file_path)


def _real_get_compute_client(credentials):
    return discovery.build("compute", "v1", credentials=credentials.credentials)


def get_compute_client(credentials):
    return _real_get_compute_client(credentials)


def _real_get_storage_client(credentials):
    return storage.Client.from_service_account_json(credentials.json_credentials_file_path)


def get_storage_client(credentials):
    return _real_get_storage_client(credentials)


def _real_get_oslogin_client(credentials):
    return discovery.build("oslogin", "v1", credentials=credentials)


def get_oslogin_client(credentials):
    return _real_get_oslogin_client(credentials)
