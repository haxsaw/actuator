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
Actuator utilities, for both public and private use
'''
import sys
import os, os.path
import logging
import pdb


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
    """
    Internal; used to map a class, and its derived classes, to some other object.
    Really just a kind of dict that has some more interesting properties.
    """
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
    """
    Internal; a decorator that maps one class to another relative to a specific
    usage domain. Typically used to map a class to another, such that the second
    has some understanding of how to process the first. Often used to map
    data objects (and their derived classes) to handler classes.
    """
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
    """
    This is the mechanism to create functions that modify the content of
    of a class (with_dependencies, with_variables, etc). This class is a
    decorator for another function that processes the so-called "class modifiers"
    later on, usually in the metaclass __new__ for the class.
    """
    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
        
    def __call__(self, *args, **kwargs):
        class_locals = sys._getframe(1).f_locals
        modifiers = class_locals.setdefault(MODIFIERS, [])
        modifiers.append((self, args, kwargs))
        
    def process(self, obj, *args, **kwargs):
        self.func(obj, *args, **kwargs)
        
def process_modifiers(obj):
    """
    Processes the modifiers against the class they were meant to modify.
    """
    modifiers = getattr(obj, MODIFIERS, [])
    for modifier, args, kwargs in modifiers:
        modifier.process(obj, *args, **kwargs)
        
        
def find_file(filename, start_path=None):
    """
    Helpful utility that finds a file relative to some starting point.
    
    @param filename: The name of the file to find.
    @keyword start_path: A path prefix to use as the place to start looking
        for the file; if unspecified, will use the current value of
        os.getcwd() to determine the starting poing.
    @return: the full path to the file, or None if it can't be found.
    """
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
    return test_file_path


def adb(arg, brk=True):
    """
    Provides a way to break in the debugger when an argument is processed.
    
    This function gives the model author a way to break into pdb or another
    debugger when Actuator processes a particular argument so that you can
    examine the processing of the argument to figure out what's going on when
    things aren't going as expected.
    
    The argument supplied can be any argument, either the type(s) needed for the
    argument or a callable that will supply those types, and they will get
    passed on and processed normally, only delayed slightly by the debugger
    break.
    
    This function can't be used on the 'name' parameter of a model component,
    only on the other args.
    
    NOTE: since PyDev in Eclipse don't like programs to invoke pdb.set_trace()
    themselves, this attempts to determine when in such an environment. It does
    this by checking if stdin is a tty; if so, then pdb.set_trace() is called.
    If not, then a line is provided where the user can set a breakpoint in
    PyDev.
    
    @param arg: Any argument to a modeling component (besides the 'name'
        argument).
    @keyword brk: Optional, default is True. Flag to indicate whether to actually
        break or not; this allows actual debug breaking to be turned on and off
        by changing the value of brk. If True, then actually break.
    """
    def inner_adb(context):
        if brk:
            if sys.stdin.isatty():
                pdb.set_trace()
            else:
                #
                # PyDev USERS: set your breakpoint on the line below:
                _ = 0
        result = context.comp._get_arg_value(arg)
        return result
    return inner_adb
