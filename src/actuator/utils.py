# 
# Copyright (c) 2014 Tom Carroll
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
'''
Created on 7 Sep 2014
'''
import sys
import os, os.path
import logging


base_logger_name = "actuator"
logging.basicConfig(format="%(levelname)s::%(asctime)s::%(name)s:: %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
LOG_DEBUG = logging.DEBUG
LOG_INFO = logging.INFO
LOG_WARN = logging.WARN
LOG_ERROR = logging.ERROR
LOG_CRIT = logging.CRITICAL


class ClassMapper(dict):
    def __getitem__(self, item):
        """
        This method differs from normal __getitem__ in that since item is expected to be
        a class, if a mapping can't be found directly for item, then a mapping for one
        of the bases on the __mro__ is subsequently searched for. Only if all of these
        searches are exhausted with no results do we raise a KeyError.
        """
        val = None
        try:
            val = dict.__getitem__(self, item)
        except KeyError, _:
            for cls in item.__mro__:
                try:
                    val = dict.__getitem__(self, cls)
                    break
                except KeyError, _:
                    pass
        if not val:
            raise KeyError("Can not find a value for %s" % item)
        return val
    

_all_mappers = {}


def capture_mapping(domain, from_class):
    def capmap(to_class):
        themap = _all_mappers.get(domain)
        if not themap:
            _all_mappers[domain] = themap = ClassMapper()
        themap[from_class] = to_class
        return to_class
    return capmap


def get_mapper(domain):
    return _all_mappers.get(domain)


MODIFIERS = "__actuator_modifiers__"


class ClassModifier(object):
    def __init__(self, func):
        self.func = func
        
    def __call__(self, *args, **kwargs):
        class_locals = sys._getframe(1).f_locals
        modifiers = class_locals.setdefault(MODIFIERS, [])
        modifiers.append((self, args, kwargs))
        
    def process(self, obj, *args, **kwargs):
        self.func(obj, *args, **kwargs)
        
def process_modifiers(obj):
    modifiers = getattr(obj, MODIFIERS, [])
    for modifier, args, kwargs in modifiers:
        modifier.process(obj, *args, **kwargs)
        
        
def find_file(filename, start_path=None):
    test_file_path = None
    if start_path is None:
        start_path = os.getcwd()
    if os.path.isabs(filename):
        if os.path.exists(filename):
            test_file_path = filename
    else:
        for root, _, files in os.walk(start_path):
            if filename in files:
                test_file_path = os.path.join(root, filename)
                break
    assert test_file_path, "Can't the file {}; aborting find".format(filename)
    return test_file_path


