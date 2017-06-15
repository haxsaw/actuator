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

