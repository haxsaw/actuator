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
Base Actuator modeling support
'''
import uuid
import sys
import re
import itertools
import weakref

from actuator.utils import ClassMapper, _Persistable

class ActuatorException(Exception): pass


class KeyAsAttr(str):
    #internal
    pass


class _ValueAccessMixin(object):
    def value(self, **kwargs):
        """
        Basic protocol for acquiring the value for an object. Keyword args
        relevant to the object may be supplied, but unknown ones may be
        rejected by users of this mixin. So it only kinda-sorta defines
        a polymorphic interface. 
        """
        raise TypeError("derived class must implement")
    
    
class KeyItem(_ValueAccessMixin):
    #internal
    def __init__(self, key):
        self.key = key if callable(key) else KeyAsAttr(key)
        
    def value(self, ctx=None):
        """
        Returns the value of self.key. If key is a callable, then its return
        value is returned instead of the key itself.
        
        @param ctx: A L{CallContext} object. Although the signature treats it as
            optional, it should be considered required (although the method 
            *will* work right without it as long as self.key isn't callable.
            Generally, this is called internally when needed and the context
            is always provided.
        """
        if callable(self.key):
            value = self.key(ctx)
        else:
            value = self.key
        return value 


class ContextExpr(object):
    """
    Creates deferred references to object attrs
    
    You should never make one of these yourself; simply access attributes on
    the global 'ctxt' object and new instances are created for you. This object
    captures the path to a particular attribute in an object, and can eval
    that path later against a materialized object when it is available. Use
    ctxt to generate references into your various models. This supports both
    attribute access and key access on any Multi* objects
    """
    def __init__(self, *path):
        self._path = path
        
    def __getattr__(self, item):
        return ContextExpr(item, *self._path)
        
    def __getitem__(self, key):
        return ContextExpr(KeyItem(key), *self._path)
        
    def __call__(self, ctx):
        ref = ctx
        for p in reversed(self._path):
            if isinstance(p, KeyItem):
                ref = ref[p.value(ctx)]
            else:
                ref = getattr(ref, p)
                if callable(ref):
                    ref = ref(ctx)
        return ref
        
        
ctxt = ContextExpr()


class CallContext(object):
    """
    Captures the context in which a callable argument is evaluated, and is passed
    into the callable when it is invoked.
    
    You don't make instances of these; Actuator handles it for you. An instance
    is passed into any callable that has been supplied as an argument in creating
    any AbstractModelingEntity object (components, roles, etc). The attributes of
    the class have the following meaning:
    
    @ivar comp: the component that the callable is an argument for. This may be
        None if this is an argument attached to the model itself
    @ivar model: the instance of the model that the component is a part of
    @ivar name: the name used to access the component from its parent. If comp
        if the value of an attribute on another object, then 'name' will be the
        attribute's name. If comp was accessed using a key, for example:
        'thing[1]', the name will be the key used, here '1'. If comp is None
        then this will likewise be None.
    @ivar nexus: an object that provides access to other models in the model
        set: nexus.inf is the infra model, nexus.ns the namespace model, and
        nexus.cfg is the config model. This allows logical navigation to other
        models in context expressions.
    """
    def __init__(self, model_inst, component):
        self.model = model_inst
        self.nexus = model_inst.nexus if model_inst is not None else None
        self.comp = component
        self.name = component._name if component else None
        
        
# class AbstractModelingEntity(object):
class AbstractModelingEntity(_Persistable):
    """
    Base class for all modeling entities
    """
    #this attribute flags to the clone() method if attrs are to be  cloned;
    #derived classed can set this to false if they don't want to clone
    #model attrs
    clone_attrs = True
    _inst_map = weakref.WeakValueDictionary()
    
    def __init__(self, name, *args, **kwargs):
        """
        Create a new modeling entity
        
        Set up the basic data for all modeling entities. The attribut
        @param name: Internal name for the entity. This is not guaranteed to
            unique or unmolested; container components may modify this name to
            suit its purposes, although they are to guarantee that the user supplied
            name will be present in any mangled version.
        @keyword model_instance: used internally; provides the model this
            entity is a part of. Users don't have to specify this value, and
            generally can't anyway
        """
        model = kwargs.get("model_instance")
        if "model_instance" in kwargs:
            kwargs.pop("model_instance")
        super(AbstractModelingEntity, self).__init__(*args, **kwargs)
        self.name = name
        "@ivar: publically available name attr for this entity"
        self._id = uuid.uuid4()
        """@ivar: public; internally generated unique id for this instance,
            a uuid.uuid4"""
        self._inst_map[self._id] = self  #set up a weak ref to the inst cache
        self._model_instance = model
        self.fixed = False
        """@ivar: public, read only. Indicates if the value of this entity
            has had its final computation (all refs resolved, callable args
            all called). Once fixed, callables won't be called again"""
            
    def _get_attrs_dict(self):
        d = super(AbstractModelingEntity, self)._get_attrs_dict()
        #@FixMe: this is going to be missing self._model_instance for the time being 
        d.update( {"name":self.name,
                   "_id":str(self._id),
                   "fixed":self.fixed,
                   "_model_instance":self._model_instance} )
        return d
            
    def get_ref(self):
        return AbstractModelReference.find_ref_for_obj(self)
        
    def _validate_args(self, referenceable):
        """
        CURRENTLY UNUSED: certain problems with finding references keep this private method out of use
        
        This method takes either an ModelBase derived class, or an instance of such a class, and
        determines if all arguments that are instances of ContextExpr can be successfully "called"
        with the provided "referenceable" (an object that creates some kind of model reference
        when attributes are attempted to be accessed on it). Silent return indicates that all
        args are valid, otherwise an ActuatorException is raised that describes what object
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
                                         (i, self.name, e.message))
        for kwname, kwvalue in kwargs.items():
            if isinstance(kwvalue, ContextExpr):
                context = CallContext(referenceable, kwvalue)
                try:
                    _ = arg(context)
                except Exception, e:
                    raise ActuatorException("Argument validation failed; argument '%s' of %s failed to eval with: %s" %
                                         (kwname, self.name, e.message))
            elif isinstance(kwvalue, AbstractModelingEntity):
                kwvalue._validate_args(referenceable)

        
    def fix_arguments(self):
        """
        Called internally when it time to fix arguments on the entity
        
        This method sets up the protocol for all derived entities to fix all
        arguments; this means turning model refs to model instance refs, and
        calling any callables to get the actual argument value. The user doesn't
        have to call this in normal operation, but may want to try it when
        testing out any callable arguments.
        """
        if not self.fixed:
            self.fixed = True
            self._fix_arguments()
        return self
            
    def _refix_arguments(self):
        """
        Allows arguments to be fixed again.
        
        This method addresses a pathological set of circumstances that hopefully
        will be eliminated in a future release. No reason for a user to call
        this.
        """
        self.fixed = False
        self.fix_arguments()
    
    def _fix_arguments(self):
        """
        Derived classes override this to fix any arguments to themselves.
        
        This method is meant to trigger any activities that need to be carried out in
        order to process arguments into a form that can be used for processing. Generally,
        this means calling _get_arg_value() on appropriate arguments to invoke any callables
        provided as arguments so that the values to use can be computed by the callable.
        """
        raise TypeError("Derived class %s must implement fix_arguments()" % self.__class__.__name__)
    
    def get_model_instance(self):
        """
        Returns the model instance this entity is a part of (if any)
        """
        return self._model_instance
         
    def _set_model_instance(self, inst):
        #private
        self._model_instance = inst
        
    def _container(self):
        """
        This returns the entity that contains self
        
        This method returns a model reference to the object that contains
        this object. For instance, if this object is an attribute on a model
        class, this method will return a reference to the model class. OTOH, if
        this object is an instance inside of some L{ComponentGroup} object, then
        this method will return the L{ComponentGroup}. Can be applied to the
        return value to get the container's container, etc.
         
        """
        my_ref = AbstractModelReference.find_ref_for_obj(self)
        container = None
        while my_ref and my_ref._parent:
            value = my_ref._parent.value()
            if isinstance(value, (MultiComponent, ModelBase, ComponentGroup)):
                container = my_ref._parent
                break
            #this next line appears to be unreachable
            my_ref = my_ref._parent
        return container
    
    container = property(_container, doc=_container.__doc__)
        
    def _get_arg_value(self, arg):
        #internal
        if callable(arg):
            try:
                if isinstance(arg, (SelectElement, RefSelectUnion)):
                    model = self.get_model_instance().nexus.find_instance(arg.builder.model)
                else:
                    model = self.get_model_instance()
                ctx = CallContext(model, AbstractModelReference.find_ref_for_obj(self))
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
        Returns the arguments that were used to create this object
        
        This method must return a 2-tuple; the first element is a tuple of
        positional arguments for this instance, and the second is a dict that
        contains the kwargs for this instance. Typically used when a copy of
        this object is to be made
        """
        return ((self.name,), {"model":self._model_instance})

    def get_class(self):
        """
        Returns the class of the object (or another class if desired)
        
        Override if you want to get a different class besides your own
        """
        return self.__class__
        
    def clone(self, clone_into_class=None):
        """
        Make a copy of this object
        
        Creates a pre-fixed copy of this object; the fixed values aren't copied,
        just the values passed to __init__(). Hence, this method is useful in
        making a copy of the current state of this object, but instead is for
        creating a copy that is created the same way as 'self' was.
        
        @param clone_into_class: Optional, defaults to None. Allows the caller
            to determine what class should be instantiated for the clone. Normally
            the class returned by L{AbstractModelingEntity.get_class} is
            used.
        @return: an un-fixed copy of self.
        """
        args, kwargs = self.get_init_args()
        new_args = [(arg.clone() if self.clone_attrs and isinstance(arg, AbstractModelingEntity) else arg)
                    for arg in args]
        new_kwargs = {k:(v.clone() if self.clone_attrs and isinstance(v, AbstractModelingEntity) else v)
                      for k, v in kwargs.items()}
        clone_class = self.get_class() if clone_into_class is None else clone_into_class
        clone = clone_class(*new_args, **new_kwargs)
        clone._set_model_instance(self.get_model_instance())
        return clone
    
    
class ModelComponent(AbstractModelingEntity):
    """
    Base class that is for any entity that will be a component of a model
    """
    pass
    
        
class _ComputeModelComponents(object):
    """
    Mixin class; do not instantiate directly
    """
    def components(self):
        """
        Returns a set of component entities (instances of ModelComponent) in self
        
        This method returns a set of all components within self; this
        includes any nested components that may be inside self if it is a
        container of some sort. NOTE: these are not references to components
        but the actual components themselves.
        """
        all_components = set()
        for v in self._comp_source().values():
            if isinstance(v, ModelComponent):
                all_components.add(v)
            elif isinstance(v, _ComputeModelComponents):
                all_components |= v.components()
        return all_components
    
    def refs_for_components(self, my_ref=None):
        """
        Returns a set of model references for all ModelComponents within self.
        
        The method computes model references for all the components it contains
        or just has references to. It does this my performing attribute lookup
        on the name of all components 'self' thinks it has, relative to the
        the reference to 'self' itself. This will ensure that all references
        to relevant model components will be generated properly.
        
        @keyword my_ref: The reference to self; defaults to None, as this 
            usually starts with the model instance, and there's no reference
            to that object.
        """
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
        #private; returns a dict of components; derived class must override
        raise TypeError("Derived class must implement _comp_source")
    

class ComponentGroup(AbstractModelingEntity, _ComputeModelComponents):
    """
    A container that groups together other components
    
    This class allows for the creation of a new object with attributes
    determined by the kwargs supplied to it. This allows a group of components
    to be defined into a single reuseable unit.   
    """
    def __init__(self, name, **kwargs):
        """
        Create a new ComponentGroup
        
        @param name: string; the logical name to give the component
        @keyword {any keyword argument}: There are no fixed keyword arguments for
        this class; all keyword arg keys will be turned into attributes on
        the instance of this object. The value of each keyword arg must be
        a derived class of L{AbstractModelingEntity}.
        @raise TypeError: Raised if a keyword argument isn't an instance of
            L{AbstractModelingEntity}
        """
        super(ComponentGroup, self).__init__(name)
        for k, v in kwargs.items():
            if isinstance(v, AbstractModelingEntity):
                clone = v.clone()
                clone._set_model_instance(self.get_model_instance())
                setattr(self, k, clone)
            else:
                raise TypeError("arg %s has a value that isn't a kind of AbstractModelingEntity: %s" % (k, str(v)))
        self._kwargs = kwargs
        
    def _find_persistables(self):
        for p in super(ComponentGroup, self)._find_persistables():
            yield p
        for k in self._kwargs:
            for p in getattr(self, k).find_persistables():
                yield p
                
    def _get_attrs_dict(self):
        d = super(ComponentGroup, self)._get_attrs_dict()
        d["_kwargs"] = {}
        for k in self._kwargs:
            d[k] = getattr(self, k)
        return d
        
    def _set_model_instance(self, inst):
        super(ComponentGroup, self)._set_model_instance(inst)
        for v in self._comp_source().values():
            v._set_model_instance(inst)
        
    def _comp_source(self):
        return {k:getattr(self, k) for k in self._kwargs}
    
    def get_init_args(self):
        __doc__ = AbstractModelingEntity.get_init_args.__doc__
        return ((self.name,), self._comp_source())
    
    def _fix_arguments(self):
        for k, v in self.__dict__.items():
            if k in self._kwargs:
                v.fix_arguments()
        
    def _validate_args(self, referenceable):
        super(ComponentGroup, self)._validate_args(referenceable)
    

class MultiComponent(AbstractModelingEntity, _ComputeModelComponents):
    """
    A container that can create duplicates of a provided template component
    
    This component behaves like a dict, except that whenever a new key is used
    to look up an item, instead of a KeyError, a new copy of a template
    component is created for  that key. The key also becomes part of the name
    of the new component. 
    """
    def __init__(self, template_component):
        """
        Create a new MultiComponent instance
        
        @param template_component: Any kind of AbstractModelingEntity, including
            another MultiComponent or other container. The template will be
            cloned immediately so that it is isolated from any other uses
            elsewhere.
        @raise TypeError: raised if the template_component isn't some kind of
            AbstractModelingEntity
        """
        if not isinstance(template_component, AbstractModelingEntity):
            raise TypeError("The template component %s isn't an "
                            "instance of AbstractModelingEntity" % str(template_component))
        super(MultiComponent, self).__init__("")
        self.template_component = template_component.clone()
        self._instances = {}
        
    def _find_persistables(self):
        for p in super(MultiComponent, self)._find_persistables():
            yield p
        for i in self._instances.values():
            for p in i.find_persistables():
                yield p
                
    def _get_attrs_dict(self):
        d = super(MultiComponent, self)._get_attrs_dict()
        d.update( {"_instances":self._instances,
                   "template_component":None} )
        return d
        
    def _set_model_instance(self, inst):
        super(MultiComponent, self)._set_model_instance(inst)
        self.template_component._set_model_instance(inst)
        
    def _fix_arguments(self):
        for i in self._instances.values():
            i.fix_arguments()
            
#     def refs_for_components(self, my_ref=None):
#         result = {}
#         if isinstance(self.template_component, ComponentGroup):
#             ref = my_ref.__class__("container", obj=self, parent=my_ref)
#             result = self.template_component.refs_for_components(my_ref=ref)
#         return result
        
    def get_prototype(self):
        """
        Returns the object to make a copy of for a new key
        """
        return self.template_component
        
    def get_init_args(self):
        __doc__ = AbstractModelingEntity.get_init_args.__doc__
        args = (self.template_component,)
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
        """
        Returns an iterator for the keys for all instances
        """
        return self._instances.iterkeys()
    
    def itervalues(self):
        """
        Returns an iterator for all the instances.
        """
        return (self.get(k) for k in self.iterkeys())
    
    def iteritems(self):
        """
        Returns an iterator of all the (key, instance) pairs
        """
        return ((k, self.get(k)) for k in self.iterkeys())
    
    def keys(self):
        """
        Returns an iterable of all keys used to generate instances of the template
        """
        return self._instances.keys()
    
    def values(self):
        """
        Returns an iterable of references to all template instances generated for supplied keys
        """
        return [self.get(k) for k in self.keys()]
    
    def items(self):
        """
        Returns an iterable so (key, ref) tuples for all keyed template instances
        """
        return [(k, self.get(k)) for k in self.keys()]
    
    def has_key(self, key):
        """
        Returns True if an instance has been created for the supplied key, False otherwise
        
        @param key: an immutable key value
        """
        return self._instances.has_key(KeyAsAttr(key))
    
    def get(self, key, default=None):
        """
        Returns a reference to the instance for key, otherwise returns default
        
        @param key: immutable key value; coerced to a string
        @keyword default: defaults to None; value to return if key is not in the container
        """
        ref = AbstractModelReference.find_ref_for_obj(self)
        result = ref[key] if key in self else default
        return result
    
    def _comp_source(self):
        return dict(self._instances)
    
    def get_instance(self, key):
        """
        Returns an instance mapped to 'key'. If 'key' has been seen before, then
        return the instance previously created for the key. Ohterwise, create
        a new instance and map it to the supplied key.
        
        @param key: immutable key value; coerced to string
        """
        if key == "None":
            _ = 1
        inst = self._instances.get(key)
        if not inst:
            prototype = self.get_prototype()
            args, kwargs = prototype.get_init_args()
            #args[0] is the name of the prototype
            #we form a new logical name by appending the
            #key to args[0] separated by an '_'
            logicalName = "%s_%s" % (args[0], str(key))
            inst = prototype.get_class()(logicalName, *args[1:], **kwargs)
            self._instances[key] = inst
            inst._set_model_instance(self.get_model_instance())
        return inst
    
    def instances(self):
        """
        Returns a dict, key:component, for all instances created thus far.
        
        Does not return references, but the actual instances themselves
        """
        return dict(self._instances)
    

class MultiComponentGroup(MultiComponent):
    """
    A mixture of ComponentGroup and MultiComponent.
    
    Allows a group of components to be provisioned as a unit, and creates new
    instances of the grouping whenever a new key is supplied to name another
    instance of the group (in the way that ComponentGroup works). This is really
    just a shortcut for making a ComponentGroup and then passing that component
    to MultiComponent.
    """
    def __new__(self, name, **kwargs):
        """
        Create a new instance of a MultiComponentGroup object.
        
        Semantically, this is just a ComponentGroup in a MultiComponent. The
        kwargs will be come the attributes of instances created by indexing
        the returned object (obj[key]).
        
        @param name: the logical name to give the grouping
        @keyword **kwargs: This will become the attributes of each
        instance of the group that is created with a new key.
        """
        group = ComponentGroup(name, **kwargs)
        return MultiComponent(group)


class _Dummy(object): pass


class AbstractModelReference(_ValueAccessMixin, _Persistable):
    """
    Base for all model reference classes.
    
    Model references are logical constructs that point to a specific object
    or attribute of a model class or model class instance. For a given class or
    class instance, only a single reference is ever generated to refer to a
    particular object or attribute contained by the class or instance.
    
    References provide a way to capture where in a model you wish to acquire
    some data when it becomes available, but the actual acquisition can be
    deferred until the data is needed. This allows a decoupling of the knowledge
    of where a data item is coming from; you simply work with a reference that
    you ask the 'value()' of when it is time to use the value.
    
    You never need to create these; they are generated automatically by Actuator
    when you access attributes on models or model instances.    
    """
    _inst_cache = {}
    _inv_cache = {}
    _as_is = (frozenset(["__getattribute__", "__class__", "value", "_name", "_obj",
                        "_parent", "get_path", "_get_item_ref_obj",
                        "get_containing_component",
                        "get_containing_component_ref"])
              .union( frozenset(dir(_Persistable)).difference(frozenset(dir(_Dummy))) ))
    def __init__(self, name, obj=None, parent=None):
        """
        Initialize a new reference object.
        
        @param name: string; the name of the attribute to fetch from the parent
        @keyword obj: optional; an object on which the attribute 'name' is defined
            Hence, an instance of a reference is the data needed to successfully
            execute "getattr(obj, name)"
            Not specified in certain internal cases
        @keyword parent: The parent reference object to this object. In other
            words, the reference to 'obj'. This allows the reference to compute
            the full path to the item it refers to
        """
        self._name = name
        self._obj = obj
        self._parent = parent
        
    def __new__(cls, name, obj=None, parent=None):
        """
        Take the data supplied and either return a new reference object, or
        else return a previously created instance (if an instance for these
        parameters has been generated previously)
        
        @param name: name of the attribute on the object that the ref is for
        @keyword obj: object on which 'name' is defined.
        @keyword parent: parent reference to this reference; in other words, the
            reference to 'obj'
        """
        key = AbstractModelReference._cache_key(name, obj, parent)
        
        inst = AbstractModelReference._inst_cache.get(key)
        if inst is None:
            inst = super(AbstractModelReference, cls).__new__(cls, name, obj, parent)
            AbstractModelReference._inst_cache[key] = inst
            
        if obj is not None:
            if isinstance(name, KeyAsAttr):
                target = obj
            else:
                target = object.__getattribute__(obj, name)
                try:
                    _ = hash(target)
                except TypeError, _:
                    target = obj
            if target is not None:
                #We can *never* store a single ref to None; too many things
                #share this value
                AbstractModelReference._inv_cache[target] = inst
            
        return inst
    
    @classmethod
    def _cache_key(cls, name, obj, parent):
        return (cls, name, obj, parent)
    
    def _get_attrs_dict(self):
        d = super(AbstractModelReference, self)._get_attrs_dict()
        d.update( {"_name":self._name,
                   "_obj":self._obj,
                   "_parent":self._parent} )
        return d
    
    def _find_persistables(self):
        for p in super(AbstractModelReference, self)._find_persistables():
            yield p
        if self._parent is not None:
            for p in self._parent.find_persistables():
                yield p
    
    def finalize_reanimate(self):
        super(AbstractModelReference, self).finalize_reanimate()
        AbstractModelReference._inst_cache[AbstractModelReference._cache_key(self._name,
                                                                             self._obj,
                                                                             self._parent)] = self
    
    @classmethod
    def find_ref_for_obj(cls, obj):
        """
        Inverse lookup; for an object, look for the reference to it. The reference
        has to have been generated previously.
        
        NOTE: this may not always give you the result you wish. It's possible
        that the same object has had more than one reference navigate to it,
        in which case you could get an unexpected reference to the object
        you provide. It isn't clear that this is a big deal, since at the end
        of the day the underlying object is the same, but paths to the object
        may be confused.
        """
        return AbstractModelReference._inv_cache.get(obj)
    
    def get_containing_component(self):
        """
        For a refernce's value, return the L{ModelComponent} that contains the
        reference.
        
        This allows discovery of the L{ModelComponent} that contains a reference
        to a more basic data item, such as a string. For instance, if you have
        a reference to a component's string attribute, you may need to find out
        the component that owns that attribute in order to properly compute
        dependencies. This method returns that reference. For example, suppose
        you have:
        
            class Thing(ModelComponent):
                def __init__(self, name):
                    self.field = 1
                    
            t = Thing()
            ref = t.field
        
        To later find the L{ModelComponent} that ref is from, you can say:
        
        mc = ref.get_containing_component()
        
        If the reference is to a L{ModelComponent} itself, this method returns
        the L{ModelComponent} itself.
        """
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
        """
        Like L{get_containing_component}, but returns the reference for the
        discovered L{ModelComponent}
        """
        comp = self.get_containing_component()
        return AbstractModelReference.find_ref_for_obj(comp)
    
    def get_path(self):
        """
        Returns a list of strings that are all attribute accesses needed to
        reach this reference. If an index is in the path, that is returned as
        part of the returned path list where the index is a special string type,
        KeyAsAttr.
        """
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
        ga = super(AbstractModelReference, self).__getattribute__
        theobj = object.__getattribute__(ga("_obj"), ga("_name"))
        key = KeyAsAttr(key)
#         key = KeyAsAttr(self.value()._get_arg_value(key))
        if isinstance(theobj, MultiComponent):
            value = self.__class__(key, self._get_item_ref_obj(theobj, key), self)
        elif hasattr(theobj, "__getitem__"):
            value = theobj[key]
        else:
            raise TypeError("%s object doesn't support keyed access" % self.__class__)
        return value
    
    def value(self, **kwargs):
        """
        Returns the value that underlies the reference. This may or may not
        return something then None, depending on the reference and where the
        underlying object is in its lifecycle. References on models may never
        yield a value, while references on model instances will yield a value
        if the underlying value has been set.
        
        There are no "blocking" semantics here; the method returns the value
        that currently exists, and if the value changes later, retrieving the
        value() of this reference again will yield the new value.
        
        @param kwargs: ignored
        """
        ga = super(AbstractModelReference, self).__getattribute__
        name = ga("_name")
        obj = ga("_obj")
        return (obj
                if isinstance(name, KeyAsAttr)
                else object.__getattribute__(obj, name))
    
    
class ModelReference(AbstractModelReference):
    """
    Instances of this class are generated whenever accesses are made to the
    attributes of a model class. See the doc for L{AbstractModelReference} for
    the rest of the interface for this class.
    
    NOTE: these references are generated when accessing attributes on a model
    class; you never create them yourself. They are not generated for methods;
    methods are passed through as ususal.
    """
    def _get_item_ref_obj(self, theobj, key):
        return theobj.get_prototype()
    

class ModelInstanceReference(AbstractModelReference):
    """
    Instances of this class are created when accessing attributes on a model
    class instance. See the doc for L{AbstractModelReference} for the rest of
    the interface for this class.
    """
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
    
    
class RefSelTest(object):
    #internal
    def __init__(self, test_op, test_arg=None):
        self.test_op = test_op
        self.test_arg = test_arg
        
        
class SelectElement(object):
    #internal
    builder = None
    def __init__(self, name, ref, parent=None):
        self.name = name
        self.parent = parent
        self.ref = ref
        self.tests = []
        
    def all(self):
        self.tests.append(RefSelTest(self.builder.ALL))
        return self
    
    def key(self, key):
        self.tests.append(RefSelTest(self.builder.KEY, key))
        return self
    
    def keyin(self, keyiter):
        self.tests.append(RefSelTest(self.builder.KEYIN, set(keyiter)))
        return self
        
    def match(self, regexp_pattern):
        self.tests.append(RefSelTest(self.builder.PATRN,
                                         re.compile(regexp_pattern)))
        return self
    
    def no_match(self, regexp_pattern):
        self.tests.append(RefSelTest(self.builder.NOT_PATRN,
                                         re.compile(regexp_pattern)))
        return self
    
    def pred(self, predicate):
        if not callable(predicate):
            raise ActuatorException("The provided predicate isn't callable")
        self.tests.append(RefSelTest(self.builder.PRED, predicate))
        return self
        
    def __getattr__(self, attrname):
        try:
            next_ref = getattr(self.ref, attrname)
        except AttributeError, _:
            if isinstance(self.ref.value(), MultiComponent):
                next_ref = getattr(self.ref.template_component, attrname)
            else:
                raise
        return self.__class__(attrname, next_ref, parent=self)
    
    def __call__(self, ctxt):
        return self.builder._execute(self, ctxt)
    
    def _expand(self):
        if self.parent is not None:
            return self.parent._expand() + [self]
        else:
            return [self]


class RefSelectBuilder(object):
    #internal
    ALL = "all"
    KEY = "key"
    KEYIN = "keyin"
    PATRN = "pattern"
    NOT_PATRN = "not pattern"
    PRED = "predicate"
    filter_ops = [ALL, KEY, KEYIN, PATRN, NOT_PATRN, PRED]
    def __init__(self, model):
        super(RefSelectBuilder, self).__init__()
        
        class LocalSelectElement(SelectElement):
            builder = self
        
        self.element_class = LocalSelectElement
        self.model = model
        self.test_map = {self.ALL:self._all_test,
                         self.KEY:self._key_test,
                         self.KEYIN:self._keyin_test,
                         self.PATRN:self._pattern_test,
                         self.NOT_PATRN:self._not_pattern_test,
                         self.PRED:self._pred_test}
        
    def _all_test(self, key, test):
        return True
    
    def _key_test(self, key, test):
        return key == test.test_arg
    
    def _keyin_test(self, key, test):
        return key in [KeyAsAttr(k) for k in test.test_arg]
    
    def _pattern_test(self, key, test):
        return test.test_arg.search(key)
    
    def _not_pattern_test(self, key, test):
        return not test.test_arg.search(key)
    
    def _pred_test(self, key, test):
        return test.test_arg(key)
    
    def _do_test(self, key, element):
        key = KeyAsAttr(key)
        tests = element.tests[:]
        result = True
        while result and tests:
            test = tests[0]
            tests = tests[1:]
            result = self.test_map[test.test_op](key, test)
        return result

    def __getattr__(self, attrname):
        ref = getattr(self.model, attrname)
        return self.element_class(attrname, ref)
    
    def union(self, *exprs):
        for expr in exprs:
            if not isinstance(expr, self.element_class):
                raise ActuatorException("The following arg is not a select expression: %s" % str(expr))
        return RefSelectUnion(self, *exprs)
     
    def _execute(self, element, ctxt):
        work_list = element._expand()
        selected = [ctxt.model]
        while work_list:
            item = work_list[0]
            named = [getattr(i, item.name) for i in selected]
            next_selected = [([v for k, v in n.items() if self._do_test(k, item)]
                              if isinstance(n.value(), MultiComponent)
                              else [n])
                             for n in named]
            selected = itertools.chain(*next_selected)
            work_list = work_list[1:]
        return set(selected)
    
    
class RefSelectUnion(object):
    def __init__(self, builder, *exprs):
        self.builder = builder
        self.exprs = exprs
        
    def __call__(self, ctxt):
        return set(itertools.chain(*[e(ctxt) for e in self.exprs]))
    
    
class _ModelLookup(object):
    def __init__(self, klass):
        self.klass = klass
    
    def __get__(self, inst, owner):
        return inst.find_instance(self.klass)
    
    
class _Nexus(object):
    """
    Internal to Actuator
    
    A nexus is where, for a given instance of a system, models and their
    instances can be recorded and then looked up by other components. In
    particular, model instances can be looked up by either the class of the
    instance, or by a base class of the instance. This way, one model instance can
    find another instance by way of the instance class or base class. This can
    be used when processing reference selection expressions or context
    expressions.
    """
    def __init__(self):
        self.mapper = ClassMapper()
        
    @classmethod
    def _add_model_desc(cls, attrname, klass):
        if not hasattr(cls, attrname):
            setattr(cls, attrname, _ModelLookup(klass))
        
    def capture_model_to_instance(self, model_class, instance):
        """
        Associate a model class to an instance of that class. Actually causes a series
        of associations to be created, following the inheritance chain for the
        class and mapping each base class to the instance, as we can't be sure
        which class will be used to try to locate the instance, the specific one
        or a more general one. Mapping terminates when ModelBase is encountered
        in the mro.
        """
        self.mapper[model_class] = instance
        for base in model_class.__mro__:
            if base in [ModelBase, _NexusMember]:
                break
            if issubclass(base, (ModelBase, _NexusMember)):
                self.mapper[base] = instance
        
    def find_instance(self, model_class):
        return self.mapper.get(model_class)
    
    def merge_from(self, other_nexus):
        self.mapper.update(other_nexus.mapper)


class ModelBaseMeta(type):
    model_ref_class = None
    _COMPONENTS = "__components"
    def __new__(cls, name, bases, attr_dict):
        components = {}
        for n, v in attr_dict.items():
            if isinstance(v, AbstractModelingEntity):
                components[n] = v
        attr_dict[cls._COMPONENTS] = components
        newbie = super(ModelBaseMeta, cls).__new__(cls, name, bases, attr_dict)
        setattr(newbie, 'q', RefSelectBuilder(newbie))
        return newbie
    
    def __getattribute__(cls, attrname):  #  @NoSelf
        ga = super(ModelBaseMeta, cls).__getattribute__
        value = (cls.model_ref_class(attrname, obj=cls, parent=None)
                 if attrname in ga(ModelBaseMeta._COMPONENTS) and cls.model_ref_class
                 else ga(attrname))
        return value
    
    
class _NexusMember(_Persistable):
    def __init__(self, nexus=None):
        super(_NexusMember, self).__init__()
        self.set_nexus(nexus)
        
    def _get_attrs_dict(self):
        d = super(_NexusMember, self)._get_attrs_dict()
        d['nexus'] = None
        return d
                
    def set_nexus(self, nexus):
        self.nexus = nexus if nexus else _Nexus()
        self.nexus.capture_model_to_instance(self.__class__, self)
        
    def update_nexus(self, new_nexus):
        if self.nexus and new_nexus:
            new_nexus.merge_from(self.nexus)
        self.set_nexus(new_nexus)


class ModelBase(_NexusMember, _ComputeModelComponents):
    """
    This is the common base class for all models
    """
    __metaclass__ = ModelBaseMeta
    
    def get_inst_ref(self, model_ref):
        """
        Take a model ref object and get an associated model instance ref for
        this model instance.
        
        Evaluates a model_ref against this instance and returns an instance ref
        that refers to the same logical spot in the model instance. The ref must
        be for this model, otherwise an error will result.
        
        @param model_ref: 
        """
        ref = self
        for p in model_ref.get_path():
            if isinstance(p, KeyAsAttr):
                ref = ref[p]
            else:
                ref = getattr(ref, p)
        return ref if ref != self else None

    def __getattribute__(self, attrname):
        ga = super(ModelBase, self).__getattribute__
        value = (self.ref_class(attrname, obj=self, parent=None)
                 if attrname in ga(ModelBaseMeta._COMPONENTS)
                 else ga(attrname))
        return value
    