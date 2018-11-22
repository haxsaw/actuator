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
from actuator.exec_agents.core import ExecutionException
from actuator.namespace import NamespaceModel, Role, MultiRole
from actuator.execute import ExecuteModel, MultiTask
from actuator.execute_tasks import (RemoteExecTask, WaitForExecTaskTask, RemoteShellExecTask,
                                    LocalExecTask, LocalShellExecTask)
from actuator.config import with_dependencies
from actuator import ctxt, Var, with_variables
from actuator.exec_agents.paramiko.agent import ParamikoExecutionAgent
from actuator.utils import find_file


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
    cmd1 = RemoteExecTask("ex001-command", "some stuff", task_role=CommonTestNS.role)
    assert True


def test002():
    """
    test002: define an empty execution model
    """
    class EM002(ExecuteModel):
        pass
    assert True


def test003():
    """
    test003: instantiate an empty execution model
    """
    class EM003(ExecuteModel):
        cmd1 = RemoteExecTask("ex003-cmd", "some stuff", task_role=CommonTestNS.role)
    em = EM003("model 003")


def test004():
    """
    test004: try to create some dependencies
    """
    class EM004(ExecuteModel):
        cmd1 = RemoteExecTask("ex004-cmd1", "some stuff", task_role=CommonTestNS.role)
        cmd2 = RemoteExecTask("ex004-cmd2", "some stuff", task_role=CommonTestNS.role)
        with_dependencies(cmd1 | cmd2)
    em4 = EM004("wibble")
    assert len(em4.dependencies) == 1


def test005():
    """
    test005: check to see that multi tasks scale up properly
    """
    class NS(NamespaceModel):
        grid = MultiRole(Role("node", host_ref="127.0.0.1"))
    ns = NS("grid-namespace")

    class Ex(ExecuteModel):
        node_run = MultiTask("node-run", RemoteExecTask("run-task", "the command"),
                             NS.grid)
    ex = Ex("exec")

    for i in range(5):
        _ = ns.grid[i]

    ex.set_namespace(ns)
    ex.node_run.fix_arguments()

    assert len(ex.node_run.instances) == 5


def test006():
    """
    test006: check that all task types are properly handled
    """
    class Ex006(ExecuteModel):
        t1 = RemoteExecTask("t1", "some command", task_role=CommonTestNS.role)
        t2 = RemoteShellExecTask("t2", "another command", task_role=CommonTestNS.role)
        t3 = LocalShellExecTask("t3", "local shell", task_role=CommonTestNS.role)
        t4 = LocalExecTask("t4", "local cmd", task_role=CommonTestNS.role)
        with_dependencies(t1 | t2 | t3 | t4)

    ex = Ex006("ex6")
    assert len(ex.dependencies) == 3
    _ = Ex006.t1
    assert ex.t1.value() is not Ex006.t1.value()
    assert ex.t2.value() is not Ex006.t2.value()
    assert ex.t3.value() is not Ex006.t2.value()
    assert ex.t4.value() is not Ex006.t4.value()


def test007():
    """
    test007: check that commands that involve a Var ref on a roll substitutes properly
    """
    class NS(NamespaceModel):
        with_variables(Var("Var1", "nope!"))
        role = Role("r007", host_ref="127.0.0.1",
                    variables=[Var("Var1", "wibble"),
                               Var("Var2", "wobble")])

    ns = NS("t007")

    class Ex007(ExecuteModel):
        t = RemoteShellExecTask("t", "!{Var1} my !{Var2}", task_role=NS.role)
    ex = Ex007("ex7")
    ex.set_namespace(ns)
    ex.t.fix_arguments()

    assert ex.t.free_form.value() == "wibble my wobble", "value was " + ex.t.free_form.value()


def test008():
    """
    test008: check that commmands that involve a Var ref on a NS substitute properly
    """
    class NS(NamespaceModel):
        with_variables(Var("Var1", "nope!"))
        role = Role("r008", host_ref="127.0.0.1",
                    variables=[Var("Var2", "wobble")])
    ns = NS("t008")

    class Ex008(ExecuteModel):
        t = RemoteShellExecTask("t", "!{Var1} my !{Var2}", task_role=NS.role)
    ex = Ex008("ex8")
    ex.set_namespace(ns)
    ex.fix_arguments()

    assert ex.t.free_form.value() == "nope! my wobble", "value was " + ex.t.free_form.value()


def test009():
    """
    test009: check that each kind of exec task does role/global Var substitution properly
    """
    class NS(NamespaceModel):
        with_variables(Var("Var1", "nope!"))
        role = Role("r008", host_ref="127.0.0.1",
                    variables=[Var("Var2", "wobble")])
    ns = NS("t009")

    class Ex009(ExecuteModel):
        t1 = RemoteExecTask("t1", "!{Var1} my !{Var2}", task_role=NS.role)
        t2 = RemoteShellExecTask("t2", "!{Var1} my !{Var2}", task_role=NS.role)
        t3 = LocalShellExecTask("t3", "!{Var1} my !{Var2}", task_role=NS.role)
        t4 = LocalExecTask("t4", "!{Var1} my !{Var2}", task_role=NS.role)

    ex = Ex009("ex9")
    ex.set_namespace(ns)
    ex.fix_arguments()

    assert ex.t1.free_form.value() == "nope! my wobble"
    assert ex.t2.free_form.value() == "nope! my wobble"
    assert ex.t3.free_form.value() == "nope! my wobble"
    assert ex.t4.free_form.value() == "nope! my wobble"


def test010():
    """
    test010: try writing a context expr the using the command from another task through the model
    """
    class Ex010(ExecuteModel):
        t1 = RemoteShellExecTask("t1", "t1's command", task_role=CommonTestNS.role)
        t2 = RemoteShellExecTask("t2", ctxt.nexus.exe.t1.free_form, task_role=CommonTestNS.role)
    ex = Ex010("ex10")
    ex.set_namespace(CommonTestNS("ns"))
    ex.t1.fix_arguments()
    ex.t2.fix_arguments()
    # NOTE: this isn't optimal. we would prefer to do our fixing according to dependencies implied
    # by the arguments, but typically this is done with with_dependencies, and not another way.
    # this is kind of a crazy example that is unlikely to be used in any real situation; we just
    # wanted a test that used both ctxt expressions and saw that the model could be reached via
    # the nexus
    # ex.fix_arguments()

    assert ex.t2.free_form.value() == "t1's command", "comand is " + ex.t2.free_form.value()


def test011():
    """
    test011: try running an execution agent directly to perform an exec model
    """
    class NS11(NamespaceModel):
        r = Role("r11", host_ref="127.0.0.1")

    class EM11(ExecuteModel):
        t0 = RemoteShellExecTask("t11-0", "/bin/rm -rf /tmp/test11.txt", task_role=ctxt.nexus.ns.r)
        t = RemoteShellExecTask("t11", "echo bingo > /tmp/test11.txt", task_role=ctxt.nexus.ns.r)
        with_dependencies(t0 | t)

    ns = NS11("ns11")
    ns.fix_arguments()
    ex = EM11("ex11", remote_user="lxle1", private_key_file=find_file("lxle1-dev-key"))
    ex.set_namespace(ns)
    ex.fix_arguments()
    pea = ParamikoExecutionAgent(task_model_instance=ex,
                                 namespace_model_instance=ns,
                                 no_delay=True)
    pea.start_performing_tasks()


def test012():
    """
    test012: Try to run an execution agent using command tasks
    """
    class NS12(NamespaceModel):
        r = Role("r12", host_ref="127.0.0.1")

    class EM12(ExecuteModel):
        t0 = RemoteExecTask("cleanup", "/bin/rm -rf /tmp/test12.txt", task_role=ctxt.nexus.ns.r)
        t1 = RemoteExecTask("clean-check", "test ! -e /tmp/test12.txt", task_role=ctxt.nexus.ns.r)
        t2 = RemoteExecTask("create", "touch /tmp/test12.txt", task_role=ctxt.nexus.ns.r)
        t3 = RemoteExecTask("create-check", "test -e /tmp/test12.txt",
                            task_role=ctxt.nexus.ns.r)
        with_dependencies(t0 | t1 | t2 | t3)

    ns = NS12("ns12")
    ns.fix_arguments()
    ex = EM12("ex12", remote_user="lxle1", private_key_file=find_file("lxle1-dev-key"))
    ex.set_namespace(ns)
    ex.fix_arguments()
    pea = ParamikoExecutionAgent(task_model_instance=ex,
                                 namespace_model_instance=ns,
                                 no_delay=True)

    # nothing to assert; the method below will raise with messages if there's an error
    pea.start_performing_tasks()


def do_all():
    for k, v in sorted(globals().items()):
        if callable(v) and k.startswith("test"):
            try:
                v()
            except Exception as e:
                print(">>>> Test {} failed:".format(e))
                traceback.print_exception(*sys.exc_info())


if __name__ == "__main__":
    do_all()
