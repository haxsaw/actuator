import getpass

import pymongo
import bson


from actuator.utils import persist_to_dict, reanimate_from_dict

client = pymongo.MongoClient()
actuator_db = client.actuator


def get_wrapper(d):
    wrapper_dict = {"user": getpass.getuser(),
                    "app": "hadoop",
                    "version": 1,
                    "orchestrator": d}
    return wrapper_dict


def capture_running(orchestrator, name=None):
    running = actuator_db.running
    d = persist_to_dict(orchestrator, name)
    wrapper = get_wrapper(d)
    o = running.insert_one(wrapper)
    return o.inserted_id


def capture_terminated(orchestrator, running_id):
    running = actuator_db.running
    running.delete_one({"_id": bson.ObjectId(running_id)})
    d = persist_to_dict(orchestrator)
    wrapper = get_wrapper(d)
    terminated = actuator_db.terminated
    o = terminated.insert_one(wrapper)
    return o.inserted_id


def running_servers_by_app_instance(app_name):
    running = actuator_db.running
    l = list(running.aggregate([{"$match": {"app": {"$eq": app_name}}},
                                {"$unwind": "$orchestrator.CATALOG"},
                                {"$group": {"_id": "$_id",
                                            "count": {"$sum": {"$cond":
                                                                   [{"$and": [{"$eq": [
                                                                       "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                                       "Server"]},
                                                                              {"$eq": [
                                                                                  "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.performance_status",
                                                                                  "performed"]},
                                                                              ]},
                                                                    1,
                                                                    0]}
                                                      }}}]))
    return l


def servers_in_terminated_apps(app_name):
    terminated = actuator_db.terminated
    l = list(terminated.aggregate([{"$match": {"app": {"$eq": app_name}}},
                                   {"$unwind": "$orchestrator.CATALOG"},
                                   {"$group": {"_id": "$_id",
                                               "count": {"$sum": {"$cond":
                                                   [{"$and": [{"$eq": [
                                                       "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                       "Server"]},
                                                       {"$eq": [
                                                           "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.performance_status",
                                                           "reversed"]},
                                                    ]},
                                                    1,
                                                    0]}
                                                   }}}]))

    return l
