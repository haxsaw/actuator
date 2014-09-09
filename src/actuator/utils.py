'''
Created on 7 Sep 2014

@author: tom
'''
import sys

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


def capture_mapping(domain, map_to_cls):
    def capmap(from_cls):
        themap = _all_mappers.get(domain)
        if not themap:
            _all_mappers[domain] = themap = ClassMapper()
        themap[from_cls] = map_to_cls
        return from_cls
    return capmap


def get_mapper(domain):
    return _all_mappers.get(domain)


MODIFIERS = "__perseverance_modifiers__"


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
