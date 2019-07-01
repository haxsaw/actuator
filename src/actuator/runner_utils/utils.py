import time
import json
from actuator.task import TaskExecControl, Task
import logging
from pythonjsonlogger import jsonlogger


class ActuatorJsonFormatter(jsonlogger.JsonFormatter):
    eom_marker = "--END--"

    def jsonify_log_record(self, log_record):
        txt = super(ActuatorJsonFormatter, self).jsonify_log_record(log_record)
        return "%s\n%s" % (txt, self.eom_marker)


def setup_json_logging():
    logger = logging.getLogger()
    log_handler = logging.StreamHandler()
    formatter = ActuatorJsonFormatter(fmt="%(name)s:%(levelname)s:%(pathname)s:%(message)s",
                                      timestamp=True)
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)


#
# general form of event JSON messages:
#
# {
#   "version": 1,
#   "event_class": "ORCH_EVENT|ENGINE_EVENT|TASK_EVENT",
#   "event_type": # one of:
#
#                 ## ORCHESTRATION EVENTS
#                 "O_START|O_FINISH|O_PROV_START|O_PROV_FINISH|O_CONFIG_START|"
#                 "O_CONFIG_FINISH|O_EXEC_START|O_EXEC_FINISH"
#
#                 ## ENGINE EVENTS
#                 "E_START|E_FINISH"
#
#                 ## TASK EVENTS
#                 "T_START|T_FINISH|T_FAIL_FINAL|T_FAIL_RETRY",
#   "event": {  # one of:
#
#               # orch events
#               "orchestrator_id": idvalue,
#
#               # engine events
#               "model": {"name": name, "id": id},
#               "graph": {"nodes": [{"task_name": name,
#                                    "task_type": type,
#                                    "task_id": taskid,
#                                    "task_status": status},
#                                   ...],
#                         "edges": [[task1_id, task2_id],
#                                   [task2_id, task4_id],
#                                   ...]
#                        },
#
#               # task events
#               "task_id": taskid,
#               "model_id": modelid,
#               "task_time": timestamp,
#               "task_action": action,
#               "errtext": [list of error strings]
#           }
# }
#


class EventPayload(dict):
    pass


class OrchestrationEventPayload(EventPayload):
    def __init__(self, orch_id, success=None):
        self["orchestration_id"] = orch_id
        self["success"] = success

    def orchestration_id(self):
        return self["orchestration_id"]

    def success(self):
        return self["success"]


class EngineEventPayload(EventPayload):
    def __init__(self, model_name, model_id):
        self["model"] = {"name": model_name, "id": str(model_id)}
        self["graph"] = {"nodes": [], "edges": []}

    def add_task_node(self, task):
        if isinstance(task, TaskExecControl):
            node = task.task
            status = task.status
        else:
            node = task
            if isinstance(task, Task):
                status = task.performance_status
            else:
                status = TaskExecControl.FAIL_FINAL
        self["graph"]["nodes"].append({"task_name": node.name,
                                       "task_type": str(type(node)),
                                       "task_id": str(node._id),
                                       "task_status": status})

    def add_task_edge(self, from_task, to_task):
        from_id = (str(from_task.task._id)
                   if isinstance(from_task, TaskExecControl)
                   else str(from_task._id))
        to_id = (str(to_task.task._id)
                 if isinstance(to_task, TaskExecControl)
                 else str(to_task._id))
        self["graph"]["edges"].append([from_id, to_id])

    def model_name(self):
        return self["model"]["name"]

    def model_id(self):
        return self["model"]["id"]

    def graph_nodes(self):
        return self["graph"]["nodes"]

    def graph_edges(self):
        return self["graph"]["edges"]


class TaskEventPayload(EventPayload):
    def __init__(self, model_id, task, errtext=None):
        if isinstance(task, TaskExecControl):
            status = task.status
            task = task.task
        else:
            status = task.performance_status

        self["task_id"] = str(task._id)
        self["model_id"] = str(model_id)
        self["task_time"] = time.time()
        self["task_action"] = status
        self["errtext"] = errtext if errtext is not None else []

    def task_id(self):
        return self["task_id"]

    def model_id(self):
        return self["model_id"]

    def task_time(self):
        return self["task_time"]

    def task_action(self):
        return self["task_action"]

    def errtext(self):
        return self["errtext"]


class ActuatorEvent(dict):
    # event classes
    orch_event = "ORCH_EVENT"
    eng_event = "ENGINE_EVENT"
    task_event = "TASK_EVENT"
    e_classes = frozenset((orch_event, eng_event, task_event))
    class_payload_map = {orch_event: OrchestrationEventPayload,
                         eng_event: EngineEventPayload,
                         task_event: TaskEventPayload
                        }
    # event types
    O_START = "O_START"  # orchestration start
    O_FINISH = "O_FINISH"  # orchestration finish
    O_PROV_START = "O_PROV_START"  # orchestrator starting provisioning
    O_PROV_FINISH = "O_PROV_FINISH"  # orchestrator finish provisioning
    O_CONFIG_START = "O_CONFIG_START"  # orchestrator start configuration
    O_CONFIG_FINISH = "O_CONFIG_FINISH"  # orchestrator finish configuration
    O_EXEC_START = "O_EXEC_START"  # orchestrator start execution
    O_EXEC_FINISH = "O_EXEC_FINISH"  # orchestrator finish execution
    E_START = "E_START"  # engine start model
    E_FINISH = "E_FINISH"  # engine finish model
    T_START = "T_START"  # task starting
    T_FINISH = "T_FINISH"  # task successfully finish
    T_FAIL_FINAL = "T_FAIL_FINAL"  # task failed after last retry; no more retries
    T_FAIL_RETRY = "T_FAIL_RETRY"  # task failed but will be retried
    _version = 1

    def __init__(self, event_class, event_id, payload):
        self["version"] = self._version
        self["event_class"] = event_class
        self["event_id"] = event_id
        self["event"] = payload

    def to_json(self):
        return json.dumps(self)

    @classmethod
    def from_json(cls, jstr):
        d = json.loads(jstr)
        ep = EventPayload(d["event"])
        ep.__class__ = cls.class_payload_map[d["event_class"]]
        return ActuatorEvent(d["event_class"], d["event_id"], ep)

    def version(self):
        return self["version"]

    def event_class(self):
        return self["event_class"]

    def event_id(self):
        return self["event_id"]

    def event(self):
        return self["event"]
