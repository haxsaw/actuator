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

import getpass
import datetime
from pprint import pprint as pp

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


def find_running(obid):
    l = list(actuator_db.running.find({"_id": bson.ObjectId(obid)}))
    return l[0] if l else None


def find_terminated(obid):
    l = list(actuator_db.terminated.find({"_id": bson.ObjectId(obid)}))
    return l[0] if l else None


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
                                            "username": {"$first": "$user"},
                                            "app": {"$first": "$app"},
                                            "init_start": {
                                                "$addToSet": "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.initiate_start_time"},
                                            "init_end": {
                                                "$addToSet": "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.initiate_end_time"},
                                            "server_count": {"$sum": {"$cond":
                                                                   [{"$and":
                                                                       [{"$or": [
                                                                           {"$eq": [
                                                                                "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                                                "Server"]},
                                                                           {"$eq": [
                                                                                "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                                                "TemplatedServer"]}
                                                                         ]
                                                                         },
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
                                               "username": {"$first": "$user"},
                                               "app": {"$first": "$app"},
                                               "init_start": {"$addToSet": "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.initiate_start_time"},
                                               "init_end": {"$addToSet": "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.initiate_end_time"},
                                               "server_count": {"$sum": {"$cond":
                                                   [{"$and": [
                                                        {"$or": [   # any kind of server class
                                                              {"$eq": [
                                                               "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                               "Server"]},
                                                              {"$eq": [
                                                                  "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__CLASS__",
                                                                  "TemplatedServer"
                                                              ]}
                                                        ]},
                                                        {"$eq": [   # must be reversed to termination
                                                            "$orchestrator.CATALOG.__VALUE__._ATTR_DICT_.__OBJECT__.performance_status",
                                                            "reversed"]},
                                                        ]
                                                     },
                                                    1,
                                                    0]}
                                                   }
                                               }
                                    }
                                   ]))

    return l


terminated = servers_in_terminated_apps

running = running_servers_by_app_instance
