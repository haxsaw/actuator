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

import traceback
import sys
from errator import reset_all_narrations, set_default_options
from actuator.namespace import NamespaceModel, Role
from actuator.execute import ExecModel, SimpleCommand
from actuator.config import with_dependencies


def setup_module():
    reset_all_narrations()
    set_default_options(check=True)


def teardown_module():
    reset_all_narrations()


class CommonTestNS(NamespaceModel):
    role = Role("testrole", host_ref=None)


def test001():
    """
    test001: check creation of a basic execution command
    """
    cmd1 = SimpleCommand("ex001-command", CommonTestNS.role, "some stuff")
    assert True


def test002():
    """
    test002: define an empty execution model
    """
    class EM002(ExecModel):
        pass
    assert True


def test003():
    """
    test003: instantiate an empty execution model
    """
    class EM003(ExecModel):
        cmd1 = SimpleCommand("ex003-cmd", CommonTestNS.role, "some stuff")
    em = EM003("model 003")


def test004():
    """
    test004: try to create some dependencies
    """
    class EM004(ExecModel):
        cmd1 = SimpleCommand("ex004-cmd1", CommonTestNS.role, "some stuff")
        cmd2 = SimpleCommand("ex004-cmd2", CommonTestNS.role, "some stuff")
        with_dependencies(cmd1 | cmd2)


def do_all():
    # test003()
    for k, v in sorted(globals().items()):
        if callable(v) and k.startswith("test"):
            try:
                v()
            except Exception as e:
                print(">>>> Test {} failed:".format(e))
                traceback.print_exception(*sys.exc_info())


if __name__ == "__main__":
    do_all()
