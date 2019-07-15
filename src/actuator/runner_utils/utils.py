import json
import datetime
from actuator import ActuatorException
from actuator.task import TaskExecControl, Task
import logging
from collections import Iterable
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
#   "event": {  # the actual 'payload' of the event; one of:
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
        """
        Defines the contents of orchestration event payloads

        :param orch_id: string; typically the '_id' attribute of an ActuatorOrchestrator
        :param success: optional, bool; used for the orchestration finished event to indicate if
            the orchestrator finsished successfully.
        """
        super(OrchestrationEventPayload, self).__init__()
        self["orchestration_id"] = orch_id
        self["success"] = success

    def orchestration_id(self):
        """
        returns the previously supplied orchestration_id

        :return: string; orchestration id
        """
        return self["orchestration_id"]

    def success(self):
        """
        returns the previously supplied (if any) success code for the run of the orchestrator.

        :return: either bool if a success code was supplied or else None
        """
        return self["success"]


class EngineEventPayload(EventPayload):
    def __init__(self, model_name, model_id):
        """
        Defines the payload for engine events

        The object also defines storage for the graph the engine will process; this is
        only populated for the engine starting event

        :param model_name: string; name of the model this engine is processing
        :param model_id: string; typically the '_id' attribute of some kind of model
        """
        super(EngineEventPayload, self).__init__()
        self["model"] = {"name": model_name, "id": str(model_id)}
        self["graph"] = {"nodes": [], "edges": []}

    def add_task_node(self, task):
        """
        Add a task to the set of tasks that the engine will be processing
        :param task: Either a Task instance or a TaskExecControl instance; if the latter,
            the task being processed is retrieved from the TaskExecControl object and this
            is what will be stored in the event payload
        """
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
        """
        records the ids of a pair of tasks that represent a directed edge (processing dependency)
        from one task to the next.

        :param from_task: Either a Task instance or a TaskExecControl instance from where the
            Task instance is retrieved. Represents the 'from' (independent) side of a dependency
            relationship between two nodes (tasks) in a directed graph. Although not checked, this
            task should have been made available to this object in a previous add_task_node()
            call.
        :param to_task: Either a Task instance or a TaskExecControl instance from where the
            Task instance is retrieved. Represents the 'to' (dependent) side of a dependency
            relationship between two nodes (tasks) in a directed graph. Although not checked, this
            task should have been made available to this object in a previous add_task_node()
        """
        from_id = (str(from_task.task._id)
                   if isinstance(from_task, TaskExecControl)
                   else str(from_task._id))
        to_id = (str(to_task.task._id)
                 if isinstance(to_task, TaskExecControl)
                 else str(to_task._id))
        self["graph"]["edges"].append([from_id, to_id])

    def model_name(self):
        """
        Get the name of the model the engine is processing

        :return: string
        """
        return self["model"]["name"]

    def model_id(self):
        """
        Get the id of the model that the engine is processing

        :return: string
        """
        return self["model"]["id"]

    def graph_nodes(self):
        """
        Get the list of dicts describing the tasks in the graph

        :return: list of dicts; each dict contains:
            {"task_name": name of the task (string),
             "task_type": type of the task (string),
             "task_id": id of the task (string),
             "task_status": status of the tasks (string)}
        """
        return self["graph"]["nodes"]

    def graph_edges(self):
        """
        Get the list of edges for the dependencies in the graph

        :return: list of lists; each inner list is comprised of two strings,
            which are the ids of the tasks that make up the edge. The first is the
            'from' task (independent), and the second the 'to' task (dependent).
            All ids should be resolvable against the nodes returned by graph_nodes().
        """
        return self["graph"]["edges"]


class TaskEventPayload(EventPayload):
    def __init__(self, model_id, task, errtext=None):
        """
        Defines the content of the payload for a task event.

        :param model_id: string; id of the model the task event is for
        :param task: either a Task or a TaskExecControl, from which the Task is retrieved. This
            is the task that the event is in regards to.
        :param errtext: optional, list of strings. This is a list of strings describing any
            errors that were encountered in processing the task.
        """
        super(TaskEventPayload, self).__init__()
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
        """
        Returns the id of the task

        :return: string
        """
        return self["task_id"]

    def model_id(self):
        """
        Returns the model id of the model that the task is part of

        :return: string
        """
        return self["model_id"]

    def task_action(self):
        """
        Returns the current action status of the task

        :return: Either an integer or a string, depending on the kind of object the payload
            was created with.
        """
        return self["task_action"]

    def errtext(self):
        """
        Returns a list of error messages associated with this task event.
        :return: list of strings. if the list is empty then there were not errors.
        """
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

    def __init__(self, event_class, event_id, payload, timestamp=None):
        """
        Create a new event envelope for one of the above payloads.

        :param event_class: string; class of the event
        :param event_id: string; id of the specific type of event
        :param payload: an EventPayload, a dict of data describing the details of the event.
        :param timestamp: optional, otherwise a string in datetime.datetime().isoformat()
            if not supplied (value of timestamp is None), then the value of
            datetime.datetime.now().isoformat() is used for the timestamp. Otherwise, the
            timestamp is used exactly as passed in.
        """
        super(ActuatorEvent, self).__init__()
        self["version"] = self._version
        self["event_class"] = event_class
        self["event_id"] = event_id
        self["event"] = payload
        self["timestamp"] = (datetime.datetime.now().isoformat()
                             if timestamp is None
                             else timestamp)

    def to_json(self):
        """
        Turns the entire event object into a JSON string

        :return: string; JSON representation of self.
        """
        return json.dumps(self)

    @classmethod
    def from_json(cls, jstr):
        """
        Re-creates the event object graph from a JSON string.

        :param jstr: string; JSON-formatted string, generally created with the to_json() method.
        :return: an
        """
        d = json.loads(jstr)
        ep = EventPayload(d["event"])
        ep.__class__ = cls.class_payload_map[d["event_class"]]
        return ActuatorEvent(d["event_class"], d["event_id"], ep, timestamp=d["timestamp"])

    def version(self):
        """
        returns the version string for the version of the message format
        :return: string
        """
        return self["version"]

    def event_class(self):
        """
        returns the string describing the class of event
        :return: string
        """
        return self["event_class"]

    def event_id(self):
        """
        returns the string id (type) of the event
        :return: string
        """
        return self["event_id"]

    def event(self):
        """
        returns the payload of the event itself
        :return: Some derived class of EventPayload in form. The actual type depends on the
            event class
        """
        return self["event"]

    def timestamp(self):
        """
        string timestamp of the event in datetime isoformat()
        :return: string is datetime.isoformat()
        """
        return self["timestamp"]


class JSONableDictMeta(type):
    """
    This metaclass is used to create mappings between the values of special dict
    keys and the class that provided the value. There's no reason to make it a metaclass
    of any user-defined class
    """
    signature_map = {}

    def __new__(mcs, name, bases, attr_dict):
        newbie = super(JSONableDictMeta, mcs).__new__(mcs, name, bases, attr_dict)
        mcs.signature_map[newbie.signature] = newbie
        return newbie


class JSONableDict(dict, metaclass=JSONableDictMeta):
    """
    Base class for 'typed' dicts that are used to fill JSON structures more cleanly.
    """
    signature = "JSONableDict"
    SIGKEY = "__RUNNERSIG__"

    def __init__(self, src_dict=None):
        """
        make a new typed dict

        :param src_dict: if provided, this is a dict whose content should be absorbed into
            the new instance; typically this is done for dicts that have been re-created from
            JSON messages.
        """
        if src_dict is None:
            super(JSONableDict, self).__init__()
            self[self.SIGKEY] = self.signature
        else:
            super(JSONableDict, self).__init__(src_dict)

    def to_json(self):
        """
        serialize self into a JSON string

        :return: string of JSON representing this dict
        """
        return json.dumps(self)

    @classmethod
    def patch_class(cls, d):
        """
        This class method uses the metaclass's map to create a JSONableDict subclass with the proper class object
        :param d: a dict that came from a JSON message of a JSONableDict. NOTE: the dict d must
            have a key in it named cls.SIGKEY; the caller is responsible for ensuring this.
        :return: a JSONableDict subclass that contains the same data as the source dict, but which
            supports the methods of that subclass
        """
        jd = JSONableDict(d)
        jd.__class__ = JSONableDictMeta.signature_map[jd[cls.SIGKEY]]
        return jd

    @classmethod
    def process_dict(cls, d):
        """
        This class method recursively transforms a plain dict into as set of JSONableDict subclasses

        :param d: A dict that is potentially from a serialized JSONableDict, though it will
            accept plain dicts as well.
        :return: An instance of an JSONableDict subclass with all internal JSONableDict instances
            similarly converted.
        """
        jd = cls.patch_class(d) if cls.SIGKEY in d else d
        for k, v in jd.items():
            if isinstance(v, dict):
                jd[k] = cls.process_dict(v)
            elif isinstance(v, list):
                for i, o in enumerate(v):
                    if isinstance(o, dict):
                        v[i] = cls.process_dict(o)
        return jd

    @classmethod
    def from_json(cls, json_str):
        """
        Takes JSON string and transforms it into an instance of a JSONableDict subclass (if appropriate)

        :param json_str: string of JSON containing a single top-level 'object' (this will fail with a list)
            The object the string describes normally is the output of a previous to_json call, but
            the method will work with a JSON for a plain dict.
        :return: Some subclass of JSONableDict
        """
        d = json.loads(json_str)
        jd = cls.process_dict(d)
        return jd


class JSONModuleDetails(JSONableDict):
    signature = "JSONModuleDetails"

    def __init__(self, content=None, source_file=None):
        """
        For modules whose contents will arrive in the JSON message; must supply just one
        of the following two arguments:
        :param content: actual content of the module as a string
        :param source_file: path to a file whose contents are to be read into a string
            and used in the message
        """
        super(JSONModuleDetails, self).__init__()
        if content is None and source_file is None:
            raise ActuatorException("You must specify at least one of content or source_file")

        if content:
            self["content"] = content
        elif source_file:
            try:
                self["content"] = open(source_file, 'r').read()
            except Exception as e:
                raise ActuatorException("Couldn't open or read the file {} with module contents: {}"
                                        .format(source_file, str(e)))
        else:
            raise ActuatorException("You must specify only one of content or source_file")

    @property
    def content(self):
        return self["content"]


_kind_details_map = {"json": JSONModuleDetails}


class ModuleDescriptor(JSONableDict):
    signature = "ModuleDescriptor"

    def __init__(self, kind, module_name, module_details):
        """
        Holds data that describes the content of a module

        :param kind: string; describes the type of details that this descriptor holds.
            Legal vs recognized values are:
            json: means the module code is in the message itself (recognized)
            db: means the details for fetching the module from the model store are include (not recognized)
            repo: means the details for access the repo where the moduel is stored are included (not recognized)
            path: means the path to where the module can be found on the local file system are included
                    (not recognized)
        :param module_name: The name to give the module when the local version is created.
        :param module_details: A JSONableDict subclass whose type matches the value of kind
        """
        super(ModuleDescriptor, self).__init__()
        self["module_name"] = module_name
        if kind not in _kind_details_map:
            raise ActuatorException("Unrecognised value for 'kind': {} in module {}"
                                    .format(kind, module_name))
        self["kind"] = kind

        if not isinstance(module_details, _kind_details_map[kind]):
            raise ActuatorException("Wrong type of details object for kind '{}': {}".format(kind,
                                                                                    module_details.__class__.__name__))
        self["details"] = module_details

    @property
    def module_name(self):
        """
        returns the module name value
        :return: string
        """
        return self["module_name"]

    @property
    def kind(self):
        """
        returns the 'kind' of the descriptor
        :return: string
        """
        return self["kind"]

    @property
    def details(self):
        """
        returns the details object that provides the specifics for creating the module according
            to the kind
        :return: an instance of a JSONableDict subclass that matches the kind value
        """
        return self["details"]


class Arguments(JSONableDict):
    signature = "Arguments"

    def __init__(self, *positional, **keyword):
        """
        Holds the positional and keyword arguments used for invoking a function or method
        @param positional: a sequence of positional args for the func/meth
        @param keyword: a dict of keyword args for the func/meth

        As always, you can use the *args **kwargs calling notation for this, or list each
        positional and keyword argument separately.
        """
        super(Arguments, self).__init__()
        self["positional"] = positional
        self["keyword"] = keyword

    @property
    def positional(self):
        """
        return the list containing the positional arguments
        :return: a list of argument values
        """
        return self["positional"]

    @property
    def keyword(self):
        """
        return the dict containing the keyword arguments
        :return: a dict with argument values, and whose keys are keyword parameter names
        """
        return self["keyword"]


class Method(JSONableDict):
    signature = "Method"

    def __init__(self, method_name, arguments):
        """
        info for invoking a method on a model
        :param method_name: string; name of the method to invoke on the model
        :param arguments: instance of Arguments
        """
        super(Method, self).__init__()
        if not isinstance(arguments, Arguments):
            raise ActuatorException("Incorrect type for the 'arguments' parameter ({}); should "
                                    "be Arguments".format(type(arguments)))
        self["method"] = method_name
        self["arguments"] = arguments

    @property
    def method(self):
        """
        returns the name of a method in a string

        :return: string
        """
        return self["method"]

    @property
    def arguments(self):
        """
        returns an Arguments object describing the arguments to use with the method

        :return: an instance of Arguments
        """
        return self["arguments"]


class Keyset(JSONableDict):
    signature = "Keyset"

    def __init__(self, path, keys):
        """
        names a path from the model root to an element where the keys should be applied

        :param path: list of strings, each one is an attribute starting from the model instance
            the ending component of the path must be some kind of MultiComponent such as a
            MultiRole
        :param keys: list of keys to apply to the final element in the above path. Keys must
            be JSON-compatible types
        """
        super(Keyset, self).__init__()
        self["path"] = path
        self["keys"] = keys

    @property
    def path(self):
        """
        Returns the list of strings naming the path to the multi component

        :return: list of strings.
        """
        return self["path"]

    @property
    def keys(self):
        """
        Returns the list of keys to apply to the multi component at the end of the path

        :return: list of key values (may be strings or ints)
        """
        return self["keys"]


class ModelSetup(JSONableDict):
    signature = "ModelSetup"

    def __init__(self, init_args, methods=None, keys=None):
        """
        Create the object that describes how to set up the model class

        @param init_args: an instance of Arguments
        @param methods: a sequence of Method instances
        @param keys: a sequence of Keyset instances
        """
        super(ModelSetup, self).__init__()
        if not isinstance(init_args, Arguments):
            raise ActuatorException("ModelSetup requires an Arguments instance in init_args")

        if methods and any(not isinstance(m, Method) for m in methods):
            raise ActuatorException("Not all objects in 'methods' are Method instances")

        if keys and any(not isinstance(k, Keyset) for k in keys):
            raise ActuatorException("Not all objects in 'keys' are Keyset intsances")

        self["init"] = init_args
        self["methods"] = methods if methods is not None else []
        self["keys"] = keys if keys is not None else []

    @property
    def init(self):
        """
        Returns the Arguments object to use when initializing the model cloass
        :return: Arguments instance
        """
        return self["init"]

    @property
    def methods(self):
        """
        Returns a list of Methods objects for each method that should be invoked on the new
            model instance

        :return: list of Method instances
        """
        return self["methods"]

    @property
    def keys(self):
        """
        Returns the list of Keyset objects to use to apply keys to multi components on the new instance

        :return: list of Keyset instances
        """
        return self["keys"]


class ModelDescriptor(ModuleDescriptor):
    signature = "ModelDescriptor"

    def __init__(self, kind, module_name, module_details, classname, setup, support=None):
        """
        A specialization of ModuleDescriptor that provides additional details that support modules
        containing model classes.

        :param kind: as in ModuleDescriptor
        :param module_name: as in ModuleDescritptor
        :param module_details: as in ModuleDescriptor
        :param classname: name of the model class within the module that is to be instantiated
        :param setup: an instance of ModelSetup that describes how to properly instantiate and
            condition the class instance
        :param support: a list of ModuleDescriptor instances that the describe support modules
            that this module requires. These modules will be created before the model module
            is imported in order to ensure that all references will resolve
        """
        super(ModelDescriptor, self).__init__(kind, module_name, module_details)
        if support and any(not isinstance(s, ModuleDescriptor) for s in support):
            raise ActuatorException("Not all objects in 'support' are ModuleDescriptor instances")
        if not isinstance(setup, ModelSetup):
            raise ActuatorException("the setup argument isn't an instance of ModelSetup")
        self["classname"] = classname
        self["support"] = support if support is not None else []
        self["setup"] = setup

    @property
    def classname(self):
        """
        returns the name of the class within the module that is to be instantiated.

        :return: string
        """
        return self["classname"]

    @property
    def support(self):
        """
        returns the list of ModuleDescriptor instances that provide support to the model module

        :return: list of ModuleDescriptor instances
        """
        return self["support"]

    @property
    def setup(self):
        """
        returns the ModelSetup instance for the model class

        :return: a ModelSetup instance
        """
        return self["setup"]


class ModelSet(JSONableDict):
    signature = "ModelSet"

    def __init__(self, infra=None, namespace=None, config=None, exe=None):
        """
        Aggregates a set of related ModelDescriptors together into a single structure

        :param infra: optional, ModelDescriptor. Describes the infrastructure model module
        :param namespace: optional, ModelDescriptor. Describes the namespace model module
        :param config: optional, ModelDescriptor. Describes the configuration model module.
        :param exe: optional, ModelDescriptor. Describes the execution model module
        """
        super(ModelSet, self).__init__()
        if not isinstance(infra, (type(None), ModelDescriptor)):
            raise ActuatorException("The infra argument is not an instance of ModelDescriptor")

        if not isinstance(namespace, (type(None), ModelDescriptor)):
            raise ActuatorException("The namespace argument is not an instance of ModelDescriptor")

        if not isinstance(config, (type(None), ModelDescriptor)):
            raise ActuatorException("The config argument is not an instance of ModelDescriptor")

        if not isinstance(exe, (type(None), ModelDescriptor)):
            raise ActuatorException("The exe argument is not an instance of ModelDescriptor")

        self["infra"] = infra
        self["config"] = config
        self["namespace"] = namespace
        self["exec"] = exe

    @property
    def exe(self):
        """
        returns the execution ModelDescriptor

        :return: a ModelDescriptor
        """
        return self["exec"]

    @property
    def infra(self):
        """
        returns the infra ModelDescriptor

        :return: a ModelDescriptor
        """
        return self["infra"]

    @property
    def namespace(self):
        """
        returns the namespace ModelDescriptor

        :return: a ModelDescriptor
        """
        return self["namespace"]

    @property
    def config(self):
        """
        returns the configuration ModelDescriptor

        :return: a ModelDescriptor
        """
        return self["config"]


class RunVar(JSONableDict):
    signature = "RunVar"

    def __init__(self, varpath, name, value, isoverride=False):
        """
        Supplies last-minute Var values to apply to the namespace model

        :param varpath: sequence of strings that name a path through a namespace model instance
            to a component where the variable should be applied.
        :param name: string; the name of the variable to set
        :param value: string; the value of the variable (this will be coerced to a string)
        :param isoverride: optional, bool (default False); if True, sets the value as an override
            to the Var's value rather than replacing the old value with a new one.
        """
        super(RunVar, self).__init__()
        self["varpath"] = varpath
        self["name"] = name
        self["value"] = str(value)
        self["isoverride"] = isoverride

    @property
    def varpath(self):
        """
        return the sequence of strings to the component where the Var is to be set

        :return: sequence of strings
        """
        return self["varpath"]

    @property
    def name(self):
        """
        returns the name of the Var to set

        :return: string
        """
        return self["name"]

    @property
    def value(self):
        """
        returns the value to set the Var to

        :return: string
        """
        return self["value"]

    @property
    def isoverride(self):
        """
        returns the isoverride flag

        :return: bool
        """
        return self["isoverride"]


class Proxy(JSONableDict):
    signature = "Proxy"

    def __init__(self, kind, args):
        """
        describes the kind and arguments to a provisioner proxy that will be needed to provision
        the cloud resources specified in the ModelDescriptors
        :param kind: string; one of:
            gcp  # for Google Cloud Platform (not supported currently)
            aws  # for AWS
            az   # for Azure
            os   # for OpenStack
            vmw  # for VSphere
        :param args: an instance of Arguments containing the required arguments for creating the
            associated ProvisionerProxy as indicated by the 'kind'
        """
        super(Proxy, self).__init__()
        if kind not in ("gcp", "aws", "az", "os", "vmw"):
            raise ActuatorException("Unrecognised kind {}".format(kind))
        if not isinstance(args, Arguments):
            raise ActuatorException("The 'args' parameter isn't an instance of Arguments")
        self["kind"] = kind
        self["args"] = args

    @property
    def kind(self):
        """
        return the 'kind' of proxy to create

        :return: string
        """
        return self["kind"]

    @property
    def args(self):
        """
        return the Arguments to use to create the proxy

        :return: instance of Arguments
        """
        return self["args"]


class OrchestratorArgs(JSONableDict):
    signature = "OrchestratorArgs"

    def __init__(self, no_delay=False, num_threads=5, post_prov_pause=60, client_keys=None):
        """
        Collects any arguments to pass on to the ActuatorOrchestration instance
        :param no_delay: optional, bool, default False. If True, then the orchestrator won't
            pause betweeen provisioning and configuration to allow all networking settings in the
            cloud to properly propagate. The default is False, ensure a delay between these
            steps.
        :param num_threads: optional, int, default 5. The number of threads to spawn to concurrently
            process tasks in the orchestration. Typically you'd want at least one thread per
            server that you are provisioning, and possibly more depending on the number of
            configuration tasks you can process in parallel.
        :param post_prov_pause: optional, int, default 60. This is the number of seconds to
            pause after provisioning before configuration is to start. If no_delay is True then
            this value is ignored. Some clouds
        :param client_keys: optional, dict. This provides a place where a client can add
            additional structured data in a dict that will accompany the orchestrator though its
            lifetime, including being persistence. This can be nested dicts, but be aware that
            all data types in the dict *must* be able to be rendered as JSON.
        """
        super(OrchestratorArgs, self).__init__()
        if not isinstance(client_keys, (type(None), dict)):
            raise ActuatorException("The client_keys param must be a JSON-compatible dict")
        self["no_delay"] = no_delay
        self["num_threads"] = num_threads
        self["post_prov_pause"] = post_prov_pause
        self["client_keys"] = client_keys if client_keys is not None else {}

    @property
    def no_delay(self):
        """
        return the value of no_delay.

        :return: bool
        """
        return self["no_delay"]

    @property
    def num_threads(self):
        """
        return the value of num_threads

        :return: int
        """
        return self["num_threads"]

    @property
    def post_prov_pause(self):
        """
        return the value of post_prov_pause

        :return: int
        """
        return self["post_prov_pause"]

    @property
    def client_keys(self):
        """
        return the client keys

        :return: dict
        """
        return self["client_keys"]


class RunnerJSONMessage(JSONableDict):
    signature = "RunnerJSONMessage"

    def __init__(self, models, vars=None, proxies=None, orchestrator_args=None, previous=None):
        """
        Create the overall message to send about a set of models

        :param models: instance of ModelSet
        :param vars: optional; list of RunVar instances
        :param proxies: optional; list of Proxy instances
        :param orchestrator_args: optional; instance of OrchestratorArgs
        :param previous: optional; if present, should be a dictionary of an ActuatorOrchestration
            instance created with actuator.utils.persist_to_dict
        """
        super(RunnerJSONMessage, self).__init__()
        if not isinstance(models, ModelSet):
            raise ActuatorException("The model_set argument isn't a ModelSet instance")

        if vars and any(not isinstance(v, RunVar) for v in vars):
            raise ActuatorException("There is an object in the vars arg that isn't a Var instance")

        if proxies and any(not isinstance(p, Proxy) for p in proxies):
            raise ActuatorException("There is an object in the proxies arg that isn't a Proxy instance")

        if not isinstance(orchestrator_args, (type(None), OrchestratorArgs)):
            raise ActuatorException("The param 'orchestrator_args' isn't a instance of OrchestratorArgs")

        if not isinstance(previous, (type(None), dict)):
            raise ActuatorException("The 'previous' parameter isn't a dict")

        self["models"] = models
        self["vars"] = vars if vars is not None else []
        self["proxies"] = proxies if proxies is not None else []
        self["orchestrator"] = orchestrator_args
        self["previous"] = previous

    @property
    def models(self):
        """
        return the ModelSet describing all models in this message

        :return: ModelSet instance
        """
        return self["models"]

    @property
    def vars(self):
        """
        return the list of RunVar instances supplied to this message

        :return: list of RunVar instances
        """
        return self["vars"]

    @property
    def proxies(self):
        """
        return the list of Proxy objects describing the required provisioner proxies

        :return: list of Proxy instances
        """
        return self["proxies"]

    @property
    def orchestrator(self):
        """
        return the OrchestratorArgs to be used in ActuatorOrchestration instance creation

        :return: instance of OrchestrationArgs
        """
        return self["orchestrator"]

    @property
    def previous(self):
        """
        return the dict of a previous instantiation of this model which will be used instead of
        a new instance.

        :return: dict of a previous orchestration run as returned from utils.persist_to_dict
        """
        return self["previous"]
