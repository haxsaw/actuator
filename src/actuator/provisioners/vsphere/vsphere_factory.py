import threading
from pyVim import connect

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
def get_vsphere_connection(host, user, pwd):
    return _real_get_vsphere_connection(host, user, pwd)
