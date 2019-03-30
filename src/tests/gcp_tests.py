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

from actuator.provisioners.gcp.resources import GCPServer


def test001():
    """
    test001: try making a server object
    """
    s = GCPServer("t1", "ubuntu", "teensy")
    assert s


def test002():
    """
    test002: make a server and ensure that the init values aren't there pre-fixing
    """
    s = GCPServer("t2", "ubuntu", "teensy", description="wibble")
    assert s.disk_image is None
    assert s.machine_type is None
    assert s.description is None


def test003():
    """
    test003: make a server a ensure that init values are there post-fixing
    """
    s = GCPServer("t2", "ubuntu", "teensy", description="wibble")
    s.fix_arguments()
    assert s.disk_image == "ubuntu"
    assert s.machine_type == "teensy"
    assert s.description == "wibble", "description is: {}".format(s.description)


def do_all():
    for k, v in sorted(globals().items()):
        if k.startswith("test") and callable(v):
            try:
                v()
            except Exception as e:
                print(">>>Test {} failed with: {}".format(k, str(e)))


if __name__ == "__main__":
    do_all()

