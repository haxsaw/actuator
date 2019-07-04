"""
Specifying models
=================
ALL: must specify the infra, namespace, config, and execution model class names at least; may need module
names as well
1. Transmit the model module as JSON content
2. Name a repo from which the Python module is to be fetched
3. Transmit the details to pull model info from the model DB
4. Path to where the model resides
5. Setup:
    1. Model init args (optional)
    2. Instance methods to call along with their arguments

Vars setup
===========================
1. Namespace Var values

Proxies and credentials
=======================
1. Name of proxy type
2. Arguments for each proxy to create

Handler data destination
========================
One of:
1. Standard out (as a JSON stream)
2. URL of where to send JSON objects
3. Name of queue where JSON objects are pushed

Operational control
===================
1. Completion notification endpoint (stdout, URL)
2. Error notification endpoint

Supplemental information
========================
1. Paths to add to sys.path
2. Log configuration/destination

{"models":{
          "infra": {"kind": "json|db|repo|path",
                    "classname": # name of the model class,
                    "module_name": # name of the module in which the model resides
                    "details": {  # details of the kind of the model implementation
                                  # json:
                                  # Python module in a JSON message; key "content": value the module
                                  # db:
                                  # name of DB entry to query for list of classes and init args
                                  # repo:
                                  # repo path, package, tag, version
                                  # path:
                                  # file directory, module name, class name
                               },
                    # the support sub-object lists other modules that the model module uses
                    # and must be present during import.
                    "support": [{"kind": "json|db|repo|path",
                                 "module_name": # name of the support module
                                 "details": {  # details of the kind of the model implementation
                                               # json:
                                               # Python module in a JSON message, module name, model class name
                                               # db:
                                               # name of DB entry to query for list of classes and init args
                                               # repo:
                                               # repo path, package, tag, version
                                               # path:
                                               # file directory, module name, class name
                                },
                                ...],
                    "setup":   {"init": {
                                            "positional": [positional args],
                                            "keyword": {"arg1": "value1",
                                                        "arg2": "value2",
                                                        ...
                                                        }
                                        },
                                "methods": [["method1",
                                             {
                                                "positional": [positional args],
                                                "keyword": {"arg1": "value1",
                                                            "arg2": "value2",
                                                            ...
                                                           }
                                             },
                                            ],
                                            ...  # another method
                                           ],
                                "keys": [{"path": [list of strings naming a path to a Multi*],
                                          "keys": [list of keys to apply to the above component]
                                         },
                                         ...
                                        ]
                               }
                   },
          "namespace": # same as infra,
          "config":    # same as infra,
          "exec":      # same as infra,
         },
 "vars": [{"varpath": # path to namespace component that holds the var
           "name": # name of the var
           "value": # value for the var
           "isoverride": False  # True if to be treated as an override
           },
           ...
          ],
 "proxies": [{"kind": "gcp|aws|az|os|vmw",
              "args": {"positional": [positional args],
                       "keyword": {"arg1": "value1",
                                   "arg2": "value2",
                                   ...
                                   }
                      }
             },
             ...
            ],
 "handler": {"kind": "stdout|queuename|url",
             "details": # values for queuename or url
            },
 "monitor": {"completion": # completion URL
             "error": # error URL
             "logconfig": # some kind of log capture path
            },
 "orchestrator":  # details about how to run the orchestrator; all are optional, as is this key
            {
                "no_delay": True|False,  # default False
                "num_threads": integer,  # default 5
                "post_prov_pause": integer,  # default 60; time to wait before starting config
                "client_keys": dict  # arbitrary JSON-able key-value pairs
            }
}
"""
import os
import os.path
import sys
import importlib
import collections
import json
import io
import traceback
import threading
import signal
import logging
from actuator import (Var, NamespaceModel, MultiComponent, ActuatorException, ModelBase,
                      ActuatorOrchestration)
from actuator.task import TaskEventHandler
from actuator.provisioners.openstack import OpenStackProvisionerProxy
from actuator.provisioners.azure import AzureProvisionerProxy
from actuator.provisioners.aws import AWSProvisionerProxy
from actuator.provisioners.vsphere import VSphereProvisionerProxy
from actuator.runner_utils.utils import (OrchestrationEventPayload, EngineEventPayload,
                                         TaskEventPayload, ActuatorEvent, setup_json_logging)
# from actuator.provisioners.gcp import ?

_proxies = {"os": OpenStackProvisionerProxy,
            "az": AzureProvisionerProxy,
            'aws': AWSProvisionerProxy,
            'vmw': VSphereProvisionerProxy,
            'gcp': None}


class RunnerEventManager(TaskEventHandler):
    """
    Is a sink of events from the orchestrator and passes them along to other
    interested parties.
    """
    def __init__(self, destination):
        """
        create an Actuator event handler
        :param destination: some object with a write() method that takes a string
            to send on to a consumer
        """
        self.destination = destination

    def orchestration_starting(self, orchestrator):
        oe = OrchestrationEventPayload(orchestrator._id)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_START, oe)
        self.destination.write(event.to_json())

    def orchestration_finished(self, orchestrator, result):
        oe = OrchestrationEventPayload(orchestrator._id, success=result)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_FINISH, oe)
        self.destination.write(event.to_json())

    def provisioning_starting(self, orchestrator):
        oe = OrchestrationEventPayload(orchestrator._id)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_PROV_START, oe)
        self.destination.write(event.to_json())

    def provisioning_finished(self, orchestrator, result):
        oe = OrchestrationEventPayload(orchestrator._id, success=result)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_PROV_FINISH, oe)
        self.destination.write(event.to_json())

    def configuration_starting(self, orchestrator):
        oe = OrchestrationEventPayload(orchestrator._id)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_CONFIG_START, oe)
        self.destination.write(event.to_json())

    def configuration_finished(self, orchestrator, result):
        oe = OrchestrationEventPayload(orchestrator._id, success=result)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_CONFIG_FINISH, oe)
        self.destination.write(event.to_json())

    def execution_starting(self, orchestrator):
        oe = OrchestrationEventPayload(orchestrator._id)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_EXEC_START, oe)
        self.destination.write(event.to_json())

    def execution_finished(self, orchestrator, result):
        oe = OrchestrationEventPayload(orchestrator._id, success=result)
        event = ActuatorEvent(ActuatorEvent.orch_event, ActuatorEvent.O_EXEC_FINISH, oe)
        self.destination.write(event.to_json())

    def engine_starting(self, model, graph):
        ep = EngineEventPayload(model.name, model._id)
        for node in graph.nodes():
            ep.add_task_node(node)
        for from_node, to_node in graph.edges():
            ep.add_task_edge(from_node, to_node)
        event = ActuatorEvent(ActuatorEvent.eng_event, ActuatorEvent.E_START, ep)
        self.destination.write(event.to_json())

    def engine_finished(self, model):
        ep = EngineEventPayload(model.name, model._id)
        event = ActuatorEvent(ActuatorEvent.eng_event, ActuatorEvent.E_FINISH, ep)
        self.destination.write(event.to_json())

    def task_starting(self, model, tec):
        tp = TaskEventPayload(model._id, tec)
        event = ActuatorEvent(ActuatorEvent.task_event, ActuatorEvent.T_START, tp)
        self.destination.write(event.to_json())

    def task_finished(self, model, tec):
        tp = TaskEventPayload(model._id, tec)
        event = ActuatorEvent(ActuatorEvent.task_event, ActuatorEvent.T_FINISH, tp)
        self.destination.write(event.to_json())

    def task_failed(self, model, tec, errtext):
        tp = TaskEventPayload(model._id, tec, errtext=errtext)
        event = ActuatorEvent(ActuatorEvent.task_event, ActuatorEvent.T_FAIL_FINAL, tp)
        self.destination.write(event.to_json())

    def task_retry(self, model, tec, errtext):
        tp = TaskEventPayload(model._id, tec, errtext=errtext)
        event = ActuatorEvent(ActuatorEvent.task_event, ActuatorEvent.T_FAIL_RETRY, tp)
        self.destination.write(event.to_json())


class ModuleDescriptor(object):
    def __init__(self, descriptor_dict, dmodule_dir="./dmodules"):
        """
        Does the work to set up a Python module file to be used in an orchestration
        :param descriptor_dict: a dictionary object that contains the data needed to acquire modules:
            "kind": "json|db|repo|path",
            "module_name": # name of the module to create (without the .py suffix)
            "details": {  # details of the kind of infra spec
                          # json:
                          # Python module in a JSON message, module name, model class name
                          # db:
                          # name of DB entry to query for list of classes and init args
                          # repo:
                          # repo path, package, tag, version
                          # path:
                          # file directory, module name, class name
                       }
        :param dmodule_dir: a path string that indicates a directory where module code can be placed
            and from where it can be imported.

        The __init__ method only sets up the instance and checks the descriptor_dict for correctness;
        the actual mechanics of importing the model are dealt with elsewhere.
        """
        missing_keys = [k for k in ("kind", "module_name", "details")
                        if k not in descriptor_dict]
        if missing_keys:
            raise ActuatorException("Can't create a module descriptor; the following key(s) are missing: {}"
                                    .format(str(missing_keys)))
        self.kind = descriptor_dict["kind"]
        # if self.kind not in ("json", "db", "repo", "path"):
        if self.kind not in ("json",):
            raise ActuatorException("Unrecognised value for 'kind': {} in module {}"
                                    .format(self.kind, descriptor_dict["module_name"]))
        self.module_name = descriptor_dict["module_name"]
        self.details = descriptor_dict["details"]
        self.dmodule_dir = dmodule_dir

    def setup_module_file(self):
        if os.path.exists(self.dmodule_dir):
            if not os.path.isdir(self.dmodule_dir):
                raise ActuatorException("The dynamic module directory {} already exists as a plain file"
                                        .format(self.dmodule_dir))
        else:
            os.makedirs(self.dmodule_dir)

        if self.dmodule_dir not in sys.path:
            sys.path.append(self.dmodule_dir)

        if not os.path.exists(os.path.join(self.dmodule_dir, self.module_name + ".py")):
            if self.kind == "json":
                self.setup_file_from_json()
            else:
                raise ActuatorException("Unrecognised value for 'kind': {} in module {}"
                                        .format(self.kind, self.module_name))

    def setup_file_from_json(self):
        if "content" not in self.details:
            raise ActuatorException("There is no 'content' key in the details for module {}"
                                    .format(self.module_name))
        module_path = os.path.join(self.dmodule_dir, self.module_name + ".py")
        open(module_path, "w").write(self.details["content"])


class ModelModuleDescriptor(ModuleDescriptor):
    def __init__(self, descriptor_dict, dmodule_dir="./dmodules"):
        """
        Specialises the ModuleDescriptor to process a python module containing an Acutator model
        :param descriptor_dict: as described in the base class ModuleDescriptor, but requires one
            extra key:
            "classname": # name of the model class,
        :param dmodule_dir: a path string that indicates a directory where module code can be placed
            and from where it can be imported.

        The __init__ method only sets up the instance and checks the descriptor_dict for correctness;
        the actual mechanics of importing the model are dealt with elsewhere.
        """
        super(ModelModuleDescriptor, self).__init__(descriptor_dict, dmodule_dir=dmodule_dir)
        if 'classname' not in descriptor_dict:
            raise ActuatorException("Can't create a module descriptor; there is no 'classname'")

        self.classname = descriptor_dict['classname']
        self.model_class = None
        self.model_module = None

    def fetch_model_class(self):
        if not self.model_class:
            self.setup_module_file()
            importlib.invalidate_caches()
            try:
                self.model_module = importlib.import_module(self.module_name)
            except Exception as e:
                sio = io.StringIO()
                traceback.print_exception(*sys.exc_info(), file=sio)
                raise ActuatorException("Python raised exception '{}' while importing module {}; "
                                        "the traceback was:\n{}".format(str(e), self.module_name,
                                                                        sio.getvalue()))
            else:
                self.model_class = getattr(self.model_module, self.classname, None)
                if self.model_class is None:
                    raise ActuatorException("Can't find model class {} in module {}".format(self.classname,
                                                                                            self.module_name))
        return self.model_class


class ModelProcessor(object):
    """
    Processes the entire set of JSON contents that describe a model, its modules, and how to
    create instances of it.
    """
    def __init__(self, model_json_dict, dmodule_dir="./dmodules"):
        if "setup" not in model_json_dict:
            raise ActuatorException("There's no 'setup' key in the JSON telling us how to create a model instance")
        if "init" not in model_json_dict["setup"]:
            raise ActuatorException("There's no 'init' key in the 'setup' section of the JSON")
        missing = [key for key in ('positional', 'keyword')
                   if key not in model_json_dict['setup']['init']]
        if missing:
            raise ActuatorException("Missing the key(s) '{}' in the module's setup/init section".format(str(missing)))

        # it all looks kosher; capture what we need
        self.setup = model_json_dict['setup']
        self.model_descriptor = ModelModuleDescriptor(model_json_dict, dmodule_dir=dmodule_dir)
        for sm in model_json_dict.get("support", []):
            md = ModuleDescriptor(sm, dmodule_dir=dmodule_dir)
            md.setup_module_file()

    def get_model_instance(self):
        """
        returns an instance of the model with all keys and methods applied
        :return:
        """
        try:
            self.model_descriptor.setup_module_file()
            model_class = self.model_descriptor.fetch_model_class()
            model_instance = model_class(*self.setup["init"]["positional"],
                                         **self.setup["init"]["keyword"])
        except ActuatorException:
            raise
        except Exception as e:
            sio = io.StringIO()
            traceback.print_exception(*sys.exc_info(), file=sio)
            raise ActuatorException("Model instance creation failed: the exception '{}' was raised while "
                                    "instantiating model {}; the traceback was:\n{}".format(str(e),
                                                                    self.model_descriptor.classname,
                                                                    sio.getvalue()))

        # invoke any methods supplied
        if "methods" in self.setup:
            # call all the methods named
            for method_name, args in self.setup["methods"]:
                pargs = args.get('positional', ())
                kw = args.get('keyword', {})
                m = getattr(model_instance, method_name, None)
                if m is None:
                    raise ActuatorException("Model instance setup failed: {} has no method {}"
                                            .format(self.model_descriptor.classname, method_name))
                try:
                    m(*pargs, **kw)
                except Exception as e:
                    sio = io.StringIO()
                    traceback.print_exception(*sys.exc_info(), file=sio)
                    raise ActuatorException("Model instance setup failed: calling method {} on model {} "
                                            "instance raised exception {}; the traceback was:\n{}"
                                            .format(method_name,
                                                    self.model_descriptor.classname,
                                                    str(e),
                                                    sio.getvalue()))

        # apply any keys to Multi* components
        assert isinstance(model_instance, ModelBase)
        if "keys" in self.setup:
            for keydict in self.setup["keys"]:
                missing = [k for k in ('path', 'keys')
                           if k not in keydict]
                if missing:
                    raise ActuatorException("Model instance setup failed: Model instance {} is missing the "
                                            "following in a 'keys' setup entry: {}"
                                            .format(self.model_descriptor.classname, str(missing)))
                path = keydict["path"]
                if not isinstance(path, collections.Iterable):
                    raise ActuatorException("Model instance setup failed: The value of 'path' {} for model "
                                            "instance {} isn't iterable"
                                            .format(str(path), self.model_descriptor.classname))
                keys = keydict["keys"]
                if not isinstance(path, collections.Iterable):
                    raise ActuatorException("Model instance setup failed: The value of keys {} for model "
                                            "instance {} isn't iterable"
                                            .format(str(keys), self.model_descriptor.classname))
                current = model_instance
                for c in path:
                    try:
                        try:
                            current = getattr(current, c)
                        except AttributeError:
                            if isinstance(current.value(), MultiComponent):
                                current = current[c]
                            else:
                                raise
                    except Exception as e:
                        raise ActuatorException("Model instance setup failed: Can't find attribute '{}' "
                                                "in path '{}' in model {}".format(c, path,
                                                                                  self.model_descriptor.classname))
                for key in keys:
                    try:
                        _ = current[key]
                    except Exception as e:
                        raise ActuatorException("Model instance setup failed: Applying key '{}' to component "
                                                "at path '{}' in model {} resulted in the exception '{}'"
                                                .format(key, path, self.model_descriptor.classname,
                                                        str(e)))

        return model_instance


def process_vars(ns, vars_list):
    """
    Set the various vars in the namespace to the indicated values
    :param ns: a Namespace instance; this is changed in-place (no return value)
    :param vars_list: a list of JSON dicts, each of the form:
        varpath: path to component on which to set the var
        name: name of the var to set
        value: value for the Var
        isoverride: True if the value is to be set as a var override; default False
    """
    assert isinstance(ns, NamespaceModel)
    assert isinstance(vars_list, list)
    for vd in vars_list:
        # first, check the keys
        for key in ("varpath", "name", "value"):
            if key not in vd:
                raise ActuatorException("There's no '{}' key in {}".format(key, str(vd)))
        current = ns
        for c in vd["varpath"]:
            try:
                current = getattr(current, c)
            except AttributeError:
                if isinstance(current.value(), MultiComponent):
                    current = current[c]
                else:
                    raise
        if "isoverride" in vd and vd["isoverride"]:
            current.add_override(Var(vd["name"], vd["value"]))
        else:
            current.add_variable(Var(vd["name"], vd["value"]))
    return


def process_proxies(proxy_data_list):
    """
    Create a list of *Proxy objects that are used to provide credentials when contacting cloud services
    :param proxy_data_list: list of dicts with the following structure:
        "kind": one of 'gcp' (Google Cloud), 'aws' (Amazon), 'az' (Azure), 'os' (Openstack), 'vmw' (VMWare)
        "args": a dict with two entries:
            'positional': list of strings of positional arg values
            'keyword': dict of keyword/value pairs
    :return: a list of *Proxy objects for use with the orchestrator
    """
    proxy_list = []
    for pd in proxy_data_list:
        # first, check the keys
        for key in ("kind", "args"):
            if key not in pd:
                raise ActuatorException("There's no '{}' key in {}".format(key, str(pd)))
            if key == "args":
                if "positional" not in pd["args"] or 'keyword' not in pd["args"]:
                    raise ActuatorException("Missing 'positional' or 'keyword' in the args dict in '{}'".format(str(pd)))
        args = pd['args']["positional"]
        kw = pd['args']["keyword"]
        proxy_class = _proxies.get(pd['kind'].lower())
        if proxy_class is None:
            raise ActuatorException("Unknown proxy 'kind': {}".format(pd['kind'].lower()))
        proxy_list.append(proxy_class(*args, **kw))
    return proxy_list


def process_models(model_dict, module_dir="./dmodules"):
    """
    Processes a model description portion of a JSON message
    :param model_dict: JSON dict with the following format:
        {
          "infra": {"kind": "json|db|repo|path",
                    "classname": # name of the model class,
                    "module_name": # name of the module in which the model resides (without the .py)
                    "details": {  # details of the kind of the model implementation
                                  # json:
                                  # Python module in a JSON message; key "content": value the module
                                  # db:
                                  # name of DB entry to query for list of classes and init args
                                  # repo:
                                  # repo path, package, tag, version
                                  # path:
                                  # file directory, module name, class name
                               },
                    # the support sub-object lists other modules that the model module uses
                    # and must be present during import.
                    "support": [{"kind": "json|db|repo|path",
                                 "classname": # name of the model class,
                                 "module_name": # name of the support module
                                 "details": {  # details of the kind of the model implementation
                                               # json:
                                               # Python module in a JSON message; key "content": value the module
                                               # db:
                                               # name of DB entry to query for list of classes and init args
                                               # repo:
                                               # repo path, package, tag, version
                                               # path:
                                               # file directory, module name, class name
                                },
                                ...],
                    "setup":   {"init": {
                                            "positional": [positional args],
                                            "keyword": {"arg1": "value1",
                                                        "arg2": "value2",
                                                        ...
                                                        }
                                        },
                                "methods": [["method1",
                                             {
                                                "positional": [positional args],
                                                "keyword": {"arg1": "value1",
                                                            "arg2": "value2",
                                                            ...
                                                           }
                                             },
                                            ],
                                            ...  # another method
                                           ],
                                "keys": [{"path": [list of strings naming a path to a Multi*],
                                          "keys": [list of keys to apply to the above component]
                                         },
                                         ...
                                        ]
                               }
                   },
          "namespace": # same as infra,
          "config":    # same as infra,
          "exec":      # same as infra,
         }
    :return: a dict whose keys are names of models, and whose values are instances of ModelProcessor
    """
    models = {"infra": None,
              "namespace": None,
              "config": None,
              "exec": None}
    for k in models:
        md = model_dict.get(k)
        if md:
            models[k] = ModelProcessor(md, dmodule_dir=module_dir)
    return models


class DefaultEventReporter(object):

    def write(self, msg):
        sys.stderr.write("%s\n%s\n" % (msg, "--END--"))


class JsonMessageProcessor(object):
    """
    Processes the overall JSON message for a variety of subsequent purposes.
    """
    def __init__(self, json_str):
        """
        set everything up from the supplied JSON message
        :param json: string; a JSON message describing what to orchestrate. Required keys are:
                models
                proxies
            Optional keys are:
                handler (defaults to stdout)
                vars
                monitor
        """
        logger = logging.getLogger()
        req_dict = json.loads(json_str.decode() if hasattr(json_str, 'decode') else json_str)
        missing = [k for k in ('models', 'proxies')
                   if k not in req_dict]
        if missing:
            raise ActuatorException("The request is missing the required keys {}".format(str(missing)))

        self.monitoring = None   # @FIXME needs some kind of handling
        self.model_processors = process_models(req_dict["models"])
        self.proxies = process_proxies(req_dict["proxies"])
        self.models = {k: (mp.get_model_instance() if mp else None) for k, mp in self.model_processors.items()}

        # optional processing; first vars
        if req_dict.get("vars") and self.models["namespace"] is None:
            raise ActuatorException("Namespace vars have been supplied but there is no namespace model "
                                    "to apply them to")
        vars = req_dict.get("vars")
        if vars is not None and self.models["namespace"] is not None:
            process_vars(self.models["namespace"], vars)

        # TODO: monitoring and handler

        # now orchestrator args
        self.orch_args = req_dict.get("orchestrator", {})
        if self.orch_args:
            allowed_keys = {"post_prov_pause", "num_threads", "no_delay", "client_keys"}
            for k in list(self.orch_args.keys()):
                if k not in allowed_keys:
                    logger.warning("Unrecognized orchestrator key '{}'; ignoring".format(k))
                    del self.orch_args[k]

    def infra_model(self):
        return self.models["infra"]

    def namespace_model(self):
        return self.models["namespace"]

    def config_model(self):
        return self.models["config"]

    def exec_model(self):
        return self.models["exec"]

    def get_proxies(self):
        return self.proxies


def process_handler(handler_dict):
    """
    processes the part of the message for
    :param handler_dict: a dict describing how to deal with handler messages; of the form:
        {
         "kind": "stdout|queuename|url",
         "details": # values for queuename or url
        }
    :return:
    """
    pass


def get_processor_from_file(jfile):
    jstr = jfile.read()
    jstr = jstr.decode() if hasattr(jstr, "decode") else jstr
    processor = JsonMessageProcessor(jstr)
    return processor


class OrchRunner(object):
    def __init__(self, orch):
        self.orch = orch
        self.is_running = False
        self.completion_status = None

    def run(self):
        self.is_running = True
        try:
            self.completion_status = self.orch.initiate_system()
        except Exception as _:
            logger = logging.getLogger()
            logger.exception("The orchestrator raised and exception while standing up a system")
        self.is_running = False

    def quit_running(self):
        self.orch.quit_processing()


def do_it(json_file, input, output):
    """
    @param json_file: file object containing a runner json message
    @param input: file object where commands are read from
    @param output: file object where responses are written to
    @return: Returns the value of orchestrator.is_running
    """
    logger = logging.getLogger()
    try:
        f = open(json_file, 'r')
        processor = get_processor_from_file(f)
        f.close()
    except Exception as _:
        logger.exception("Received an error trying to process the JSON file {}".format(json_file))
        logger.critical("Unable to continue; exiting")
        sys.exit(1)

    assert isinstance(processor, JsonMessageProcessor)

    t = orch = infra = ns = config = exe = proxies = orch_runner = evhandler = None
    ready_prompt = "READY:\n"
    # we don't put the usual guards around the interactive code as humans won't be
    # the party driving this, only another program
    output.write(ready_prompt)
    output.flush()

    command = input.readline().strip()
    while command.lower() != 'q':
        if command == 'q':  # quit immediately; killing the orchestration if needed
            output.write("quitting\n")
            output.flush()
            continue
        elif command == 'r':  # run or re-run an orchestration
            if orch_runner is None:
                infra = processor.infra_model()
                config = processor.config_model()
                ns = processor.namespace_model()
                exe = processor.exec_model()
                proxies = processor.get_proxies()
                evhandler = RunnerEventManager(DefaultEventReporter())
                orch = ActuatorOrchestration(infra_model_inst=infra, provisioner_proxies=proxies,
                                             namespace_model_inst=ns, config_model_inst=config,
                                             execute_model_inst=exe, event_handler=evhandler,
                                             **processor.orch_args)
                orch_runner = OrchRunner(orch)
            if not orch_runner.is_running:
                try:
                    t = threading.Thread(target=orch_runner.run, args=())
                    t.start()
                except Exception as _:
                    logger.exception("Received an error during system initiation")
            output.write("running\n")
            output.flush()
        output.write("READY:\n")
        output.flush()
        command = input.readline().strip()

    thread_alive = False
    if orch_runner:
        orch_runner.quit_running()
        if t:
            t.join()
            if t.is_alive():
                thread_alive = True
    return (orch_runner.completion_status if orch_runner is not None else None,
            ((orch_runner.is_running and thread_alive) if orch_runner is not None else False))


if __name__ == "__main__":
    """
    The path to the json file is supplied as the argument to the script.
    """
    logger = logging.getLogger()
    del logger.handlers[:]
    setup_json_logging()
    if len(sys.argv) < 2:
        logger.critical("No JSON file specified; unable to continue")
        sys.exit(1)
    success, is_running = do_it(sys.argv[1], sys.stdin, sys.stdout)
    if is_running:
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        sys.exit(0)
