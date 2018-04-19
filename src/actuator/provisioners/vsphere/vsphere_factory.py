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

import threading
from pyVim import connect
from errator import narrate

_mpl = threading.Lock()


#
# real connection factory
def _real_get_vsphere_connection(host, user, pwd):
    try:
        si = connect.SmartConnect(host=host, user=user, pwd=pwd)
    except Exception as e:
        if "SSL: CERTIFICATE_VERIFY_FAILED" in str(e):
            import ssl
            with _mpl:
                dc = ssl._create_default_https_context
                ssl._create_default_https_context = ssl._create_unverified_context
                si = connect.SmartConnect(host=host, user=user, pwd=pwd)
                ssl._create_default_https_context = dc
        else:
            raise
    return si


#
# monkey-patchable factory; replace with something else for testing
@narrate(lambda h, u, p: "...so we tried to get a vsphere connection to {} for {}".format(h, u))
def get_vsphere_connection(host, user, pwd):
    return _real_get_vsphere_connection(host, user, pwd)
