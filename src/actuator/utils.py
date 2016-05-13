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
"""
Actuator utilities, for both public and private use
"""
import sys
import os
import os.path
import logging
import pdb
import datetime
import collections
import threading
import types

base_logger_name = "actuator"
logging.basicConfig(format="%(levelname)s::%(asctime)s::%(name)s:: %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
LOG_DEBUG = logging.DEBUG
LOG_INFO = logging.INFO
LOG_WARN = logging.WARN
LOG_ERROR = logging.ERROR
LOG_CRIT = logging.CRITICAL


class UtilsException(Exception):
    pass


class KeyAsAttr(str):
    pass


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

        
class _SigDictMeta(type):
    _sigmap = {}
    _SIG_ = "_SIGNATURE_"

    def __new__(cls, name, bases, attr_dict):
        newbie = super(_SigDictMeta, cls).__new__(cls, name, bases, attr_dict)
        cls._sigmap[newbie._KIND_] = newbie
        return newbie
    
    @classmethod
    def get_kind(cls, o):   # @NoSelf
        return o[cls._SIG_] if cls.is_sigdict(o) else None
    
    @classmethod
    def find_class(cls, o):  # @NoSelf
        return cls._sigmap.get(cls.get_kind(o))
    
    @classmethod
    def is_sigdict(cls, o):  # @NoSelf
        return isinstance(o, dict) and cls._SIG_ in o
    
    
class _SignatureDict(dict):
    _KIND_ = "SignatureDict"
    __metaclass__ = _SigDictMeta

    def __init__(self):
        super(_SignatureDict, self).__init__()
        self[_SigDictMeta._SIG_] = self._KIND_
        
    def from_dict(self, d):
        self.update(d)
        return self
    
    
class _PersistableRef(_SignatureDict):
    _KIND_ = "_PersistableRef"
    _REFID_ = "_REFID_"
    _OBJ_INFO_ = "_OBJINFO_"

    def __init__(self, o=None):
        super(_PersistableRef, self).__init__()
        if o is not None:
            self[self._REFID_] = id(o)
            self[self._OBJ_INFO_] = str(o)
        
    def _id(self):
        return self[self._REFID_]
    id = property(fget=_id)
    
    def _info(self):
        return self[self._OBJ_INFO_]
    info = property(fget=_info)
    
    
class _ClassRef(_SignatureDict):
    _KIND_ = "_ClassRef"
    _CLASS_NAME_ = "_classname_"
    _MODULE_NAME_ = "_moddulename_"

    def __init__(self, o=None):
        super(_ClassRef, self).__init__()
        if o is not None:
            self[self._CLASS_NAME_] = o.__name__
            self[self._MODULE_NAME_] = o.__module__
            
    def get_class(self):
        return _find_class(self[self._MODULE_NAME_],
                           self[self._CLASS_NAME_])
        
        
class _PersistedKeyAsAttr(_SignatureDict):
    _KIND_ = "_PersistedKeyAsAttr"
    _VALUE_ = "_value_"

    def __init__(self, kaa=None):
        super(_PersistedKeyAsAttr, self).__init__()
        if kaa is not None:
            self[self._VALUE_] = kaa
            
    def get_kaa(self):
        return KeyAsAttr(self[self._VALUE_])
    
    
class _CallableRef(_SignatureDict):
    _KIND_ = "_CallableRef"
    _CALLABLE_NAME_ = "_callable_name_"
    _CALLABLE_MODULE_ = "_callable_module_"


class ValueRecoverer(object):
    def __init__(self, value, setter):
        if not isinstance(setter, types.MethodType):
            raise UtilsException("The provided setter, %s, is not an instance method" % setter)
        self.value = value
        self.setter = setter


class _InvokableAttrRef(_SignatureDict):
    _KIND_ = "_InvokableAttrRef"
    _VALUE_ = "_value_"
    _SETTER_ = "_setter_"

    def __init__(self, recoverer):
        if not isinstance(recoverer, ValueRecoverer):
            raise UtilsException("The 'recoverer' argument must be an instance eof ValueRecoverer")
        self[self._VALUE_] = recoverer.value
        self[self._SETTER_] = recoverer.setter.im_func.__name__

    def recover(self, obj):
        object.__getattribute__(obj, self[self._SETTER_])(self[self._VALUE_])

    
class _PersistablesCyclesDeco(object):
    def __init__(self):
        self.local = threading.local()
        self.m = None
        
    def __call__(self, m):
        self.m = m

        def cycle_checker(persistable):
            if not hasattr(self.local, "visitation_set"):
                self.local.visitation_set = set()
            per_id = id(persistable)
            if per_id not in self.local.visitation_set:
                self.local.visitation_set.add(per_id)
                for p in self.m(persistable):
                    yield p
        cycle_checker.__name__ = self.m.__name__
        cycle_checker.__doc__ = self.m.__doc__
        return cycle_checker
        
    
class _Persistable(object):
    """
    Internal utility mixin that defines the persist/restore protocol
    """
    _persistable = "_ACTUATOR_PERSISTABLE_"
    _class_name = "__CLASS__"
    _module_name = "__MODULE__"
    _obj_ = "__OBJECT__"
    _version = "__VERSION__"
    _path = "__PATH__"
    _vernum = 1

    def get_attrs_dict(self):
        ad = self._get_attrs_dict()
        for k, v in ad.items():
            ad[k] = self.encode_attr(k, v)
        sig = self.obj_sig_dict()
        sig.update({self._version: self._vernum,
                    self._persistable: "yes",
                    self._obj_: ad})
        return sig
    
    def finalize_reanimate(self):
        """
        Called after all attrs have been set on all persistables to do final recovery
        """
        return
    
    def recover_attr_value(self, k, v, catalog):
        """
        Allows derived classes to customize reanimation.
        
        This method is given the name of an attribute and it's corresponding
        value from persistence, and should return the re-animated version of
        that value. The default implementation simply returns the value, but
        a derived class may override this method to provide assistance to
        _Persistable in the case where the attribute value is something a bit
        odd, for instance a list of _Persistables, which otherwise wouldn't be
        restored properly. The notion is for the derived class to look at the
        key 'k' and only do the required work for the specific key, and other-
        wise should just call super(DerivedClassName, self).recover_attr_value(k, v)
        and return that value for everything else.
        
        @param k: The name of the attribute to set on 'self'
        @param v: The value as retrieved from persistence. If nothing needs to
            be done with this value simply return it, otherwise return the 
            properly re-animated value instead (may entail a call to
            _reanimator()).
        @param catalog: an instance of L{_Catalog}, a flat dictionary of all
            _Persistables currently being processed. If a _PersistableRef is
            re-created, the actual _Persistable can be located using the
            catalog
        @return: The reanimated value for k such that setattr(self, k, v) will
            yield self in a proper reanimated state.
        """
        retval = v
        if isinstance(v, collections.Iterable):
            if _SigDictMeta.is_sigdict(v):
                klass = _SigDictMeta.find_class(v)
                if not klass:
                    raise UtilsException("Couldn't find a class for kind %s" %
                                         _SigDictMeta.get_kind(v))
                retval = klass().from_dict(v)
                if isinstance(retval, _PersistableRef):
                    try:
                        retval = catalog.find_entry(retval.id).get_reanimated()
                    except UtilsException, e:
                        raise UtilsException("Error recovering attribute %s; error: %s"
                                             % (k, e.message))
                elif isinstance(retval, _ClassRef):
                    retval = retval.get_class()
                elif isinstance(retval, _PersistedKeyAsAttr):
                    retval = retval.get_kaa()
                elif isinstance(retval, _InvokableAttrRef):
                    # these are passed out as is; the caller is responsible for
                    # doing the right thing with the object
                    pass
                else:
                    raise UtilsException("Unknown kind of SigDict: %s" % retval[_SignatureDict._KIND_])
            elif isinstance(v, dict):
                for vk, vv in v.items():
                    # SHOULD FIX REANIM
                    if _SigDictMeta.is_sigdict(vk):
                        klass = _SigDictMeta.find_class(vk)
                        if not klass:
                            raise UtilsException("Couldn't find a class for dict k of kind %s" %
                                                 _SigDictMeta.get_kind(vk))
                        if klass is not _PersistedKeyAsAttr:
                            raise UtilsException("During reanimation, got a SigDict class that can't be hashed and "
                                                 "so can't be used as a dict key: %s" % klass._KIND_)
                        o = klass().from_dict(vk)
                        vk = o.get_kaa()
                    if _SigDictMeta.is_sigdict(vv):
                        klass = _SigDictMeta.find_class(vv)
                        if not klass:
                            raise UtilsException("Couldn't find a class for kind %s"
                                                 % _SigDictMeta.get_kind(vv))
                        v[vk] = klass().from_dict(vv)
                        if _SigDictMeta.is_sigdict(v[vk]):
                            # this is most likely a _PersistableRef
                            ref = _SigDictMeta.find_class(v[vk])().from_dict(v[vk])
                            v[vk] = catalog.find_entry(ref.id).get_reanimated()
            elif isinstance(v, (list, tuple)):
                retval = [(_SigDictMeta.find_class(o)().from_dict(o)
                           if _SigDictMeta.is_sigdict(o)
                           else o) for o in v]
                retval = [(catalog.find_entry(o.id).get_reanimated()
                           if isinstance(o, _PersistableRef)
                           else o) for o in retval]
        return retval
    
    def encode_attr(self, k, v):
        """
        Encodes an attr into something that can be turned into json.
        
        Derived classes may override this method to provide custom encodings
        for complex objects (such as dicts with objects as keys), but should
        always return super() if they don't process an attribute themselves.
        
        Objects properly encoded include:
        ints, longs, floats, strings, references to _Persistables, dicts with
        keys that are ints, longs floats and strings and values that are these
        types or _Persistables, and lists and tuples of the simple types or
        _Persistables.
        
        @param k: string; name of the attribute in the containing object
        @param v: object: the value of the attribute named 'k'
        @return: a JSON-safe encoding of the attribute
        """
        retval = v
        if isinstance(v, _Persistable):
            retval = _PersistableRef(v)
        elif isinstance(v, collections.Iterable) and not isinstance(v, basestring):
            if isinstance(v, dict):
                retval = {(_PersistedKeyAsAttr(vk) if isinstance(vk, _PersistedKeyAsAttr) else vk):
                          (_PersistableRef(vv) if isinstance(vv, _Persistable) else vv)
                          for vk, vv in v.items()}
                # retval = {vk: (_PersistableRef(vv)
                #                if isinstance(vv, _Persistable)
                #                else vv) for vk, vv in v.items()}
            elif isinstance(v, (list, tuple)):
                retval = [(_PersistableRef(i) if isinstance(i, _Persistable) else i)
                          for i in v]
        elif isinstance(v, type):
            retval = _ClassRef(v)
        elif isinstance(v, KeyAsAttr):
            retval = _PersistedKeyAsAttr(v)
        elif isinstance(v, ValueRecoverer):
            retval = _InvokableAttrRef(v)
        return retval
        
    def obj_sig_dict(self):
        return {self._class_name: self.__class__.__name__,
                self._module_name: self.__class__.__module__}
        
    def persisted_persistable(self, o):
        return isinstance(o, dict) and self._persistable in o
        
    def _get_attrs_dict(self):
        """
        Return a dict of single-valued attributes, NO COLLECTIONS!
        
        The derived class must implement this to return the single valued attrs.
        
        Keys are attr names, values are the corresponding attr values.
        If a value of 'attr' is some kind of _Persistable, return the value of
        self.attr.get_attrs_dict() as the value of attr.
        
        NOTE: Since callables can't be persisted, only the values returned by
        the callable can be in the returned dict. That means only processed
        arguments are allowed to be returned. You only want these frozen values
        anyway.
        """
        return {}
    
    @_PersistablesCyclesDeco()
    def find_persistables(self):
        yield self
        for p in self._find_persistables():
            yield p
            
    def _find_persistables(self):
        """
        Returns a series of contained _Persistables; a generator is expected
        
        This method is a generator that yields contained _Persistables. By
        "contained" we mean _Persistables that this _Persistable manages directly,
        as opposed to _Persistables that this _Persistable doesn't  manage but
        simply holds a reference to (_Persistable due to context expressions are
        a good example). A derived class should implement a generator that yields
        each _Persistable one at a time. This should be accomplished by calling
        find_persistables() on each contained _Persistable and yielding the
        values provided. For example, suppose self.wibble is a contained _Persistable
        for this object. This method could then be implemented like so:
        
        for p in self.wibble.find_persistables():
            yield p
            
        Notice that you never have to yield 'self'. The default implementation
        simply ends the iteration.
        """
        # the following is just an oddity of Python; it needs to see a 'yield'
        # in the method to make it a generator, but we don't actually ever
        # need it to execute. So we protect it with the impossible test
        if 1 == 0:
            yield
    
    def set_attrs_from_dict(self, d, catalog):
        for k, v in d.items():
            try:
                v = self.recover_attr_value(k, v, catalog)
            except UtilsException, e:
                raise UtilsException("Got an exception trying to recover attribute %s: %s"
                                     % (k, e.message))
            if isinstance(v, _InvokableAttrRef):
                v.recover(self)
            else:
                setattr(self, k, v)
        return


class _AbstractPerformable(object):
    UNSTARTED = "unstarted"
    PERFORMED = "performed"
    REVERSED = "reversed"

    def get_performance_status(self):
        raise TypeError("Derived class must implement")

    def set_performance_status(self, status):
        raise TypeError("Derived class must implement")


class _Performable(_AbstractPerformable):
    def __init__(self, *args, **kwargs):
        super(_Performable, self).__init__(*args, **kwargs)
        self.performance_status = self.UNSTARTED

    def get_performance_status(self):
        return self.performance_status

    def set_performance_status(self, status):
        self.performance_status = status


# adapted from pickle.Unpickler
def _find_class(module, name):
    __import__(module)
    mod = sys.modules[module]
    klass = getattr(mod, name)
    return klass


class _Dummy(object):
    pass


class _CatalogEntry(_SignatureDict):
    ORIG_ID = "_ORIG_ID_"
    ORIG_TYPE = "_ORIG_TYPE_"
    ATTRS_DICT = "_ATTR_DICT_"
    REANIM_OBJ = "_REANIM_OBJ_"
    _KIND_ = "_CatalogEntry"

    def __init__(self, o=None):
        super(_CatalogEntry, self).__init__()
        self[self.ORIG_ID] = self.compute_id(o)
        self[self.ORIG_TYPE] = o.obj_sig_dict() if o is not None else None
        self[self.ATTRS_DICT] = o.get_attrs_dict() if o is not None else None
        self[self.REANIM_OBJ] = None
        
    @classmethod
    def compute_id(cls, o):
        return id(o)
        
    def _id(self):
        return self[self.ORIG_ID]
    id = property(fget=_id)
        
    def from_dict(self, d):
        super(_CatalogEntry, self).from_dict(d)
        tinfo = self[self.ORIG_TYPE]
        if tinfo is None:
            o = None
        else:
            o = _Dummy()
            module, name = (tinfo[_Persistable._module_name],
                            tinfo[_Persistable._class_name])
            klass = _find_class(module, name)
            o.__class__ = klass
        self[self.REANIM_OBJ] = o
        return self
    
    def get_reanimated(self):
        return self[self.REANIM_OBJ]
    
    def apply_attributes(self, catalog):
        o = self[self.REANIM_OBJ]
        if o is not None:
            o.set_attrs_from_dict(self[self.ATTRS_DICT][_Persistable._obj_], catalog)
        return self
        
    
class _Catalog(_SignatureDict):
    _KIND_ = "_Catalog"
    
    def add_entry(self, persistable):
        if _CatalogEntry.compute_id(persistable) not in self:
            ce = _CatalogEntry(o=persistable)
            self[ce.id] = ce
        
    def find_entry(self, eid):
        try:
            return self[eid]
        except KeyError, _:
            raise UtilsException("Can't find catalog entry for reference %s; have you "
                                 "ensured that every ref to a _Persistable has been "
                                 "reported via _find_persistables()?" % str(eid))
    
    @classmethod
    def print_it(cls, adict):
        for k, v in adict.items():
            print k
            if _SigDictMeta.is_sigdict(v):
                print "\tType info:", v[_CatalogEntry.ORIG_TYPE]
                print "\tAttrs:", v[_CatalogEntry.ATTRS_DICT]
    
    def to_dict(self):
        return self
    
    def from_dict(self, a_dict):
        for k, v in a_dict.items():
            if _SigDictMeta.is_sigdict(v):
                self[int(k)] = _CatalogEntry().from_dict(v)
        for ce in self.values():
            if isinstance(ce, _CatalogEntry):
                ce.apply_attributes(self)
        for ce in self.values():
            if isinstance(ce, _CatalogEntry):
                o = ce.get_reanimated()
                if o is not None:
                    o.finalize_reanimate()
        return self
    
    
def reanimate_from_dict(d):
    catalog = _Catalog()
    catalog.from_dict(d["CATALOG"])
    root = catalog.find_entry(_PersistableRef().from_dict(d["ROOT_OBJ"]).id)
    return root.get_reanimated()
    
    
def persist_to_dict(o, name=None):
    if not isinstance(o, _Persistable):
        raise TypeError("the parameter must be a kind of _Persistable")
    catalog = _Catalog()
    for p in o.find_persistables():
        catalog.add_entry(p)
    d = dict()
    d["PERSIST_TIMESTAMP"] = str(datetime.datetime.now())
    d["NAME"] = name
    d["SYS_PATH"] = sys.path[:]
    d["VERSION"] = 1
    d["CATALOG"] = catalog.to_dict()
    d["ROOT_OBJ"] = _PersistableRef(o)
    return d
