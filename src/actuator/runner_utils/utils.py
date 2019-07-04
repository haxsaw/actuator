import json
import datetime
from actuator import ActuatorException
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
        self["timestamp"] = datetime.datetime.now().isoformat()

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


class JSONableDictMeta(type):
    signature_map = {}

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(JSONableDictMeta, mcs).__new__(mcs, name, bases, attr_dict)
        mcs.signature_map["name"] = newbie
        return newbie


class JSONableDict(dict, metaclass=JSONableDictMeta):
    signature = None

    def __init__(self, src_dict=None):
        if src_dict is None:
            super(JSONableDict, self).__init__()
            self["signature"] = self.signature
        else:
            super(JSONableDict, self).__init__(src_dict)

    def to_json(self):
        return json.dumps(self)

    def patch_class(self, d):
        jd = JSONableDict(d)
        jd.__class__ = JSONableDictMeta.signature_map[jd["signature"]]

    @classmethod
    def from_json(cls, json_str):
        d = json.loads(json_str)
        jd = JSONableDict(d)
        jd.__class__ = JSONableDictMeta.signature_map[jd["signature"]]


class JSONModuleDetails(JSONableDict):
    signature = "JSONModuleDetails"

    def __init__(self, content=None, source_file=None):
        super(JSONModuleDetails, self).__init__()
        if content is None and source_file is None:
            raise ActuatorException("You must specify at least one of content or source_file")

        if content is not None and source_file is not None:
            raise ActuatorException("You must specify only one of content or source_file")

        if content:
            self["content"] = content
        else:
            try:
                self["content"] = open(source_file, 'r').read()
            except Exception as e:
                raise ActuatorException("Couldn't open or read the file {} with module contents: {}"
                                        .format(source_file, str(e)))

    @property
    def content(self):
        return self["content"]


_kind_details_map = {"json": JSONModuleDetails}


class ModuleDescriptor(JSONableDict):
    signature = "ModuleDescriptor"

    def __init__(self, kind, module_name, module_details):
        super(ModuleDescriptor, self).__init__()
        self["module_name"] = module_name
        if kind not in {"json"}:
            raise ActuatorException("Unrecognised value for 'kind': {} in module {}"
                                    .format(kind, module_name))
        self["kind"] = kind

        if not isinstance(module_details, _kind_details_map[kind]):
            raise ActuatorException("Wrong type of details object for kind '{}': {}".format(kind,
                                                                                    module_details.__class__.__name__))
        self["details"] = module_details

    @property
    def module_name(self):
        return self["module_name"]

    @property
    def kind(self):
        return self["kind"]

    @property
    def details(self):
        return self["details"]


class ModelModuleDescriptor(ModuleDescriptor):
    signature = "ModelModuleDescriptor"

    def __init__(self, kind, module_name, module_details, classname):
        super(ModelModuleDescriptor, self).__init__(kind, module_name, module_details)
        self["classname"] = classname

    @property
    def classname(self):
        return self["classname"]


class Arguments(JSONableDict):

    signature = "Arguments"

    def __init__(self, *positional, **keyword):
        """
        Holds the positional and keyword arguments used for invoking a function or method
        @param positional: a sequence of postional args for the func/meth
        @param keyword: a dict of keyword args for the func/meth

        As always, you can use the *args **kwargs calling notation for this, or list each
        positional and keyword argument separately.
        """
        super(Arguments, self).__init__()
        self["positional"] = positional
        self["keyword"] = keyword
        x = y = z = 0
        if 1 == x == y == z:
            pass


class ModelSetup(JSONableDict):
    signature = "ModelSetup"

    def __init__(self, init_args, methods=None, keys=None):
        """
        Create the object that describes how to set up the model class
        @param init_args: an instance of Arguments
        @param methods:
        @param keys:
        """
        if not isinstance(init_args, Arguments):
            raise ActuatorException("ModelSetup requires an Arguments instance in init_args")


class JSONModelProcessor(JSONableDict):
    signature = "JSONModelProcessor"

    def __init__(self, model_mod_desc, support=None):
        pass
