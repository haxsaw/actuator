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
Created on 3 Oct 2014

@author: tom
'''
import uuid
import sys


class ActuatorException(Exception): pass


class KeyAsAttr(str): pass


class ContextExpr(object):
    def __init__(self, *path):
        self._path = path
        
    def __getattr__(self, item):
        if item[0] != '_':
            return ContextExpr(item, *self._path)
        else:
            #NOTE: this line seems to actually be unreachable
            return super(ContextExpr, self).__getattribute__(item)
        
    def __call__(self, ctx):
        ref = ctx
        for p in reversed(self._path):
            ref = getattr(ref, p)
        return ref
        
ctxt = ContextExpr()
        
class CallContext(object):
    def __init__(self, infra_inst, component):
        self.infra = infra_inst
        self.comp = component


class AbstractModelingEntity(object):
    def __init__(self, logicalName, *args, **kwargs):
        super(AbstractModelingEntity, self).__init__(*args, **kwargs)
        self.logicalName = logicalName
        self._id = uuid.uuid4()
        self._infra_instance = None
        self.fixed = False
        
    def _validate_args(self, referenceable):
        """
        This method takes either an InfraSpec derived class, or an instance of such a class, and
        determines if all arguments that are instances of ContextExpr can be successfully "called"
        with the provided "referenceable" (an object that creates some kind of model reference
        when attributes are attempted to be accessed on it). Silent return indicates that all
        args are valid, otherwise an InfraException is raised that describes what object
        is a problem.
        
        Derived classes may wish to override this if they do any special arguments handling, or
        if there are other objects that they contain that should also get their args checked.
        Derived classes need to be sure they call the super() version of this method in their
        implementation.
        """
        args, kwargs = self.get_init_args()
        context = CallContext(referenceable, self)
        for i, arg in enumerate(args):
            if isinstance(arg, ContextExpr):
                try:
                    _ = arg(context)
                except Exception, e:
                    raise ActuatorException("Argument validation failed; argument %d of %s failed to eval with: %s" %
                                         (i, self.logicalName, e.message))
        for kwname, kwvalue in kwargs.items():
            if isinstance(kwvalue, ContextExpr):
                context = CallContext(referenceable, kwvalue)
                try:
                    _ = arg(context)
                except Exception, e:
                    raise ActuatorException("Argument validation failed; argument '%s' of %s failed to eval with: %s" %
                                         (kwname, self.logicalName, e.message))
            elif isinstance(kwvalue, AbstractModelingEntity):
                kwvalue._validate_args(referenceable)

        
    def fix_arguments(self):
        if not self.fixed:
            self._fix_arguments()
            self.fixed = True
    
    def _fix_arguments(self):
        """
        This method is meant to trigger any activities that need to be carried out in
        order to process arguments into a form that can be used for processing. Generally,
        this means calling _get_arg_value() on appropriate arguments to invoke any callables
        provided as arguments so that the values to use can be computed by the callable.
        """
        raise TypeError("Derived class %s must implement fix_arguments()" % self.__class__.__name__)
         
    def _set_infra_instance(self, inst):
        self._infra_instance = inst
        
    def _container(self):
        my_ref = AbstractModelReference.find_ref_for_obj(self)
        container = None
        while my_ref and my_ref._parent:
            value = my_ref._parent.value()
            if isinstance(value, (MultiComponent, SpecBase, ComponentGroup)):
                container = my_ref._parent
                break
            #this next line appears to be unreachable
            my_ref = my_ref._parent
        return container
    
    container = property(_container)
        
    def _get_arg_value(self, arg):
        if callable(arg):
            try:
                ctx = CallContext(self._infra_instance, AbstractModelReference.find_ref_for_obj(self))
                value = arg(ctx)
                if isinstance(value, ModelInstanceReference):
                    value = value.value()
            except Exception, e:
                t, v = sys.exc_info()[:2]
                raise ActuatorException("Callable arg failed with: %s, %s, %s" %
                                     (t, v, e.message)), None, sys.exc_info()[2]
        else:
            value = arg
        return value
        
    def get_init_args(self):
        """
        This method must return a 2-tuple; the first element is a tuple of
        positional arguments for a new instance of the same class, and the
        second is a dict that are the kwargs for a new instance
        """
        raise TypeError("Derived class must implement get_init_args()")

    def get_class(self):
        """
        Override if you want to get a different class besides your own
        """
        return self.__class__
        
    def clone(self, clone_cache):
        "this doesn't work with circular object refs yet"
        #clone_cache is a map that maps original instances to their clones
        clone = clone_cache.get(self)
        if clone is None:
            args, kwargs = self.get_init_args()
            new_args = [(arg.clone(clone_cache) if isinstance(arg, AbstractModelingEntity) else arg)
                        for arg in args]
            new_kwargs = {k:(v.clone(clone_cache) if isinstance(v, AbstractModelingEntity) else v)
                          for k, v in kwargs.items()}
            clone = self.get_class()(*new_args, **new_kwargs)
            clone_cache[self] = clone
        return clone
    
    
class ModelComponent(AbstractModelingEntity):
    pass
    
        
class _ComputeModelComponents(object):
    def components(self):
        all_components = set()
        for v in self._comp_source().values():
            if isinstance(v, ModelComponent):
                all_components.add(v)
            elif isinstance(v, _ComputeModelComponents):
                all_components |= v.components()
        return all_components
    
    def refs_for_components(self, my_ref=None):
        all_refs = set()
        for k, v in self._comp_source().items():
            if isinstance(v, ModelComponent):
                if isinstance(k, KeyAsAttr):
                    all_refs.add(my_ref[k])
                else:
                    all_refs.add(getattr(self if my_ref is None else my_ref, k))
            elif isinstance(self, MultiComponent):
                ref = my_ref[k]
                all_refs |= v.refs_for_components(my_ref=ref)
            elif isinstance(self, ComponentGroup):
                ref = getattr(my_ref, k)
                all_refs |= v.refs_for_components(my_ref=ref)
            elif isinstance(v, _ComputeModelComponents):
                ref = getattr(self, k)
                all_refs |= v.refs_for_components(my_ref=ref)
        return all_refs
    
    def _comp_source(self):
        "returns a dict of components in an instance"
        raise TypeError("Derived class must implement _comp_source")
    

class ComponentGroup(AbstractModelingEntity, _ComputeModelComponents):
    def __init__(self, logicalName, **kwargs):
        super(ComponentGroup, self).__init__(logicalName)
        clone_cache = {}
        for k, v in kwargs.items():
            if isinstance(v, AbstractModelingEntity):
                setattr(self, k, v.clone(clone_cache))
            else:
                raise TypeError("arg %s has a value that isn't a kind of InfraComponentBase" % k)
        self._kwargs = kwargs
        
    def _comp_source(self):
        return {k:getattr(self, k) for k in self._kwargs}
    
    def get_init_args(self):
        return ((self.logicalName,), self._kwargs)
    
    def _fix_arguments(self):
        for _, v in self.__dict__.items():
            if isinstance(v, AbstractModelingEntity):
                v.fix_arguments()
        
    def _validate_args(self, referenceable):
        super(ComponentGroup, self)._validate_args(referenceable)
#         for
    

class MultiComponent(AbstractModelingEntity, _ComputeModelComponents):
    def __init__(self, templateComponent):
        super(MultiComponent, self).__init__("")
        self.templateComponent = templateComponent
        self._instances = {}
        
    def _fix_arguments(self):
        for i in self._instances.values():
            i.fix_arguments()
            
#     def refs_for_components(self, my_ref=None):
#         result = {}
#         if isinstance(self.templateComponent, ComponentGroup):
#             ref = my_ref.__class__("container", obj=self, parent=my_ref)
#             result = self.templateComponent.refs_for_components(my_ref=ref)
#         return result
        
    def get_prototype(self):
        return self.templateComponent
        
    def get_init_args(self):
#         args = (self.templateComponent.clone({}),)
        args = (self.templateComponent,)
        return (args, {})
        
    def _validate_args(self, referenceable):
        super(MultiComponent, self)._validate_args(referenceable)
        proto = self.get_prototype()
        proto._validate_args(referenceable)
        
    def __len__(self):
        return len(self._instances)
    
    def __iter__(self):
        return iter(self._instances)
    
    def __nonzero__(self):
        return len(self._instances) != 0
    
    def __contains__(self, key):
        return self.has_key(key)
        
    def iterkeys(self):
        return self._instances.iterkeys()
    
    def itervalues(self):
        return (self.get(k) for k in self.iterkeys())
    
    def iteritems(self):
        return ((k, self.get(k)) for k in self.iterkeys())
    
    def keys(self):
        return self._instances.keys()
    
    def values(self):
        return [self.get(k) for k in self.keys()]
    
    def items(self):
        return [(k, self.get(k)) for k in self.keys()]
    
    def has_key(self, key):
        return self._instances.has_key(KeyAsAttr(key))
    
    def get(self, key, default=None):
        try:
            result = AbstractModelReference.find_ref_for_obj(self)[key]
        except KeyError, _:
            result = default
        return result
    
    def _comp_source(self):
        return dict(self._instances)
    
    def get_instance(self, key):
        inst = self._instances.get(key)
        if not inst:
            prototype = self.get_prototype()
            args, kwargs = prototype.get_init_args()
            #args[0] is the logicalName of the prototype
            #we form a new logical name by appending the
            #key to args[0] separated by an '_'
            logicalName = "%s_%s" % (args[0], str(key))
            inst = prototype.get_class()(logicalName, *args[1:], **kwargs)
            self._instances[key] = inst
        return inst
    
    def instances(self):
        return dict(self._instances)
    

class MultiComponentGroup(MultiComponent):
    def __new__(self, logicalName, **kwargs):
        group = ComponentGroup(logicalName, **kwargs)
        return MultiComponent(group)
    

class AbstractModelReference(object):
    _inst_cache = {}
    _inv_cache = {}
    _as_is = frozenset(["__getattribute__", "__class__", "value", "_name", "_obj",
                        "_parent", "get_path", "_get_item_ref_obj",
                        "get_containing_component", "get_containing_component_ref"])
    def __init__(self, name, obj=None, parent=None):
        self._name = name
        self._obj = obj
        self._parent = parent
        
    def __new__(cls, name, obj=None, parent=None):
        inst = AbstractModelReference._inst_cache.get( (cls, name, obj, parent) )
        if inst is None:
            inst = super(AbstractModelReference, cls).__new__(cls, name, obj, parent)
            AbstractModelReference._inst_cache[(cls, name, obj, parent)] = inst
        if obj is not None:
            if isinstance(name, KeyAsAttr):
                target = obj
            else:
                target = object.__getattribute__(obj, name)
                try:
                    _ = hash(target)
                except TypeError, _:
                    target = obj
            AbstractModelReference._inv_cache[target] = inst
            
        return inst
    
    @classmethod
    def find_ref_for_obj(cls, obj):
        return AbstractModelReference._inv_cache.get(obj)
    
    def get_containing_component(self):
        ga = super(AbstractModelReference, self).__getattribute__
        val = self.value()
        if not isinstance(val, ModelComponent):
            obj = ga("_obj")
            if isinstance(obj, ModelComponent):
                val = obj
            else:
                parent = ga("_parent")
                val = (parent.get_containing_component()
                       if parent is not None
                       else None)
        return val
    
    def get_containing_component_ref(self):
        comp = self.get_containing_component()
        return AbstractModelReference.find_ref_for_obj(comp)
    
    def get_path(self):
        parent = self._parent
        return (parent.get_path() if parent is not None else []) + [self._name]
    
    def __getattribute__(self, attrname):
        ga = super(AbstractModelReference, self).__getattribute__
        if attrname in AbstractModelReference._as_is:
            value = ga(attrname)
        else:
            name = ga("_name")
            if isinstance(name, KeyAsAttr):
                theobj = ga("_obj")
            else:
                theobj = object.__getattribute__(ga("_obj"), name)
            if hasattr(theobj, attrname):
                value = getattr(theobj, attrname)
                if not callable(value) and not attrname.startswith("_") and not isinstance(value, AbstractModelReference):
                    #then wrap it with a new reference object
                    value = ga("__class__")(attrname, theobj, self)
            else:
                raise AttributeError("%s instance has no attribute named %s" % (theobj.__class__.__name__, attrname))
        return value
    
    def _get_item_ref_obj(self, theobj, key):
        raise TypeError("Derived class must implement _get_item_ref_obj()")
    
    def __getitem__(self, key):
        key = KeyAsAttr(key)
        ga = super(AbstractModelReference, self).__getattribute__
        theobj = object.__getattribute__(ga("_obj"), ga("_name"))
        if isinstance(theobj, MultiComponent):
            value = self.__class__(key, self._get_item_ref_obj(theobj, key), self)
        elif hasattr(theobj, "__getitem__"):
            value = theobj[key]
        else:
            raise TypeError("%s object doesn't support keyed access" % self.__class__)
        return value
    
    def value(self):
        ga = super(AbstractModelReference, self).__getattribute__
        name = ga("_name")
        obj = ga("_obj")
        return (obj
                if isinstance(name, KeyAsAttr)
                else object.__getattribute__(obj, name))
    
    
class ModelReference(AbstractModelReference):
    def _get_item_ref_obj(self, theobj, key):
        return theobj.get_prototype()
    

class ModelInstanceReference(AbstractModelReference):
    def _get_item_ref_obj(self, theobj, key):
        return theobj.get_instance(key)
    
    def __len__(self):
        value = self.value()
        if not hasattr(value, "__len__"):
            raise TypeError("object of type %s has no len()" % str(value))
        return len(value)
    
    def __nonzero__(self):
        value = self.value()
        result = value is not None
        if result:
            if hasattr(value, "__nonzero__"):
                result = value.__nonzero__()
            else:
                result = True
        return result
    
    def __iter__(self):
        value = self.value()
        if not hasattr(value, "__iter__"):
            raise TypeError("object of type %s is not iterable" % str(value))
        return iter(value)
    
    def __contains__(self, key):
        value = self.value()
        if not hasattr(value, "__contains__"):
            raise TypeError("object of type %s does not support 'in'" % str(value))
        return key in value
        
    
class SpecBaseMeta(type):
    model_ref_class = None
    _COMPONENTS = "__components"
    
    def __getattribute__(cls, attrname):  #  @NoSelf
        ga = super(SpecBaseMeta, cls).__getattribute__
        value = (cls.model_ref_class(attrname, obj=cls, parent=None)
                 if attrname in ga(SpecBaseMeta._COMPONENTS) and cls.model_ref_class
                 else ga(attrname))
        return value


class SpecBase(_ComputeModelComponents):
    __metaclass__ = SpecBaseMeta
