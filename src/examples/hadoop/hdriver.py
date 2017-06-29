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

import matplotlib
matplotlib.use("module://kivy.garden.matplotlib.backend_kivy")
import time
import threading
import random
import networkx
from hevent import TaskEventManager
from actuator.task import Task, TaskExecControl

g = networkx.DiGraph()
nodes = [TaskExecControl(Task("task%d" % i)) for i in range(4)]
g.add_nodes_from([tec.task for tec in nodes])
g.add_edges_from([(nodes[0].task, nodes[1].task),
                  (nodes[0].task, nodes[2].task),
                  (nodes[2].task, nodes[3].task),
                  (nodes[1].task, nodes[3].task)])

tem = None

events = {TaskExecControl.PERFORMING: TaskEventManager.task_starting,
          TaskExecControl.FAIL_FINAL: TaskEventManager.task_failed,
          TaskExecControl.FAIL_RETRY: TaskEventManager.task_retry,
          TaskExecControl.SUCCESS: TaskEventManager.task_finished}


quit = False


def send_events():
    time.sleep(2)
    event_info = list(events.items())
    while not quit:
        tec = random.choice(nodes)
        assert isinstance(tec, TaskExecControl)
        status, func = random.choice(event_info)
        print("sending %s to %s" % (status, str(func)))
        tec.status = status
        func(tem, tec)
        time.sleep(1.5)


if __name__ == "__main__":
    t = threading.Thread(target=send_events, args=())
    t.start()
    tem = TaskEventManager()
    tem._fireup_display(None, g)
    quit = True

