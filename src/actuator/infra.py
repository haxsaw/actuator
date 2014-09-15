'''
Created on 7 Sep 2014

@author: tom
'''
import uuid
import sys

from actuator.utils import ClassModifier, process_modifiers


class InfraException(Exception): pass


_infra_options = "__infra_options__"
_recognized_options = set(["default_provisioner"])
@ClassModifier
def with_infra_options(cls, *args, **kwargs):
    """
    Available options:
    default_provisioner=None
    """
    opts_dict = cls.__dict__.get(_infra_options)
    if opts_dict is None:
        opts_dict = {}
        setattr(cls, _infra_options, opts_dict)
    for k, v in kwargs.items():
        if k not in _recognized_options:
            raise InfraException("Unrecognized InfraSpec option: %s" % k)
        opts_dict[k] = v


class ContextExpr(object):
    def __init__(self, *path):
        self._path = path
        
    def __getattr__(self, item):
        if item[0]!='_':
            return ContextExpr(item,*self._path)
        else:
            return super(ContextExpr, self).__getattribute__(item)
        
    def _get_path(self):
        return self._path
        
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


class InfraComponentBase(object):
    def __init__(self, logicalName, *args, **kwargs):
        super(InfraComponentBase, self).__init__(*args, **kwargs)
        self.logicalName = logicalName
        self._id = uuid.uuid4()
        self._infra_instance = None
        self.fixed = False
        
    def _validate_args(self, referenceable):
        """
        This method takes either an InfraSpec derived class, or an instance of such a class, and
        determines if all arguments that are instances of ContextExpr can successfully "called"
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
                    raise InfraException("Argument validation failed; argument %d of %s failed to eval with: %s" %
                                         (i, self.logicalName, e.message))
        for kwname, kwvalue in kwargs.items():
            if isinstance(kwvalue, ContextExpr):
                context = CallContext(referenceable, kwvalue)
                try:
                    _ = arg(context)
                except Exception, e:
                    raise InfraException("Argument validation failed; argument '%s' of %s failed to eval with: %s" %
                                         (kwname, self.logicalName, e.message))
            elif isinstance(kwvalue, InfraComponentBase):
                kwvalue._validate_args(referenceable)

        
    def fix_arguments(self, provisioner=None):
        if not self.fixed:
            self._fix_arguments(provisioner=provisioner)
            self.fixed = True
    
    def _fix_arguments(self, provisioner=None):
        """
        This method is meant to trigger any activities that need to be carried out in
        order to process arguments into a form that can be used for provisioning. Generally,
        this means calling _get_arg_value() on appropriate arguments to invoke any callables
        provided as arguments so that the values to use can be computed by the callable.
        A provisioner is  passed into the the method to support any of the computations
        required by a callable.
        """
        raise TypeError("Derived class must implement fix_arguments()")
         
    def _set_infra_instance(self, inst):
        self._infra_instance = inst
        
    def _container(self):
        my_ref = AbstractModelReference.find_ref_for_obj(self)
        container = None
        while my_ref and my_ref._parent:
            value = my_ref._parent.value()
            if isinstance(value, (MultiBase, InfraSpec, ComponentGroupBase)):
                container = my_ref._parent
                break
            my_ref = my_ref._parent
        return container
    
    container = property(_container)
        
    def _get_arg_value(self, arg):
        if callable(arg):
            try:
                ctx = CallContext(self._infra_instance, AbstractModelReference.find_ref_for_obj(self))
                value = arg(ctx)
                if isinstance(value, InfraModelInstanceReference):
                    value = value.value()
            except Exception, e:
                t, v = sys.exc_info()[:2]
                raise InfraException("Callable arg failed with: %s, %s, %s" %
                                     (t, v, e.message))                    
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
            new_args = [(arg.clone(clone_cache) if isinstance(arg, InfraComponentBase) else arg)
                        for arg in args]
            new_kwargs = {k:(v.clone(clone_cache) if isinstance(v, InfraComponentBase) else v)
                          for k, v in kwargs.items()}
            clone = self.get_class()(*new_args, **new_kwargs)
            clone_cache[self] = clone
        return clone
    
        
class Provisionable(object): pass
        

class KeyAsAttr(str): pass


class InfraSpecMeta(type):
    _COMPONENTS = "__components"
    def __new__(cls, name, bases, attr_dict):
        components = {}
        for n, v in attr_dict.items():
            if isinstance(v, InfraComponentBase):
                components[n] = v
        attr_dict[cls._COMPONENTS] = components
        new_class = super(InfraSpecMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(new_class)
        new_class._class_refs_for_provisionables()
        for component in components.values():
            component._validate_args(new_class)
#             args, kwargs = component.get_init_args()
#             for i, arg in enumerate(args):
#                 if isinstance(arg, ContextExpr):
#                     context = CallContext(new_class, component)
#                     try:
#                         _ = arg(context)
#                     except Exception, e:
#                         raise InfraException("InfraSpecMeta failed; argument %d of %s failed to eval with: %s" %
#                                              (i, arg.logicalName, e.message))
#             for kwname, kwvalue in kwargs.items():
#                 if isinstance(kwvalue, ContextExpr):
#                     context = CallContext(new_class, kwvalue)
#                     try:
#                         _ = arg(context)
#                     except Exception, e:
#                         raise InfraException("InfraSpecMeta failed; argument '%s' of %s failed to eval with: %s" %
#                                              (kwname, kwvalue.logicalName, e.message))
        return new_class
    
    def __getattribute__(cls, attrname):  #  @NoSelf
        ga = super(InfraSpecMeta, cls).__getattribute__
        value = (InfraModelReference(attrname, obj=cls, parent=None)
                 if attrname in ga(InfraSpecMeta._COMPONENTS)
                 else ga(attrname))
        return value
        
    
class AbstractModelReference(object):
    _inst_cache = {}
    _inv_cache = {}
    _as_is = frozenset(["__getattribute__", "__class__", "value", "_name", "_obj",
                        "_parent", "get_path", "_get_item_ref_obj",
                        "get_containing_provisionable"])
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
    
    def get_containing_provisionable(self):
        ga = super(AbstractModelReference, self).__getattribute__
        val = self.value()
        if not isinstance(val, Provisionable):
            obj = ga("_obj")
            if isinstance(obj, Provisionable):
                val = obj
            else:
                parent = ga("_parent")
                val = (parent.get_containing_provisionable()
                       if parent is not None
                       else None)
        return val
    
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
        if not isinstance(theobj, MultiBase):
            raise TypeError("%s object doesn't support keyed access" % self.__class__)
        if hasattr(theobj, "__getitem__"):
            value = getattr(theobj, "__getitem__")
        else:
            value = self.__class__(key, self._get_item_ref_obj(theobj, key), self)
        return value
    
    def value(self):
        ga = super(AbstractModelReference, self).__getattribute__
        name = ga("_name")
        obj = ga("_obj")
        return (obj
                if isinstance(name, KeyAsAttr)
                else object.__getattribute__(obj, name))
    
    
class InfraModelReference(AbstractModelReference):
    def _get_item_ref_obj(self, theobj, key):
        return theobj.get_prototype()
    

class InfraModelInstanceReference(AbstractModelReference):
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
        
    
class _ComputeProvisionables(object):
    def provisionables(self):
        all_provisionables = set()
        for v in self._prov_source().values():
            if isinstance(v, Provisionable):
                all_provisionables.add(v)
            elif isinstance(v, _ComputeProvisionables):
                all_provisionables |= v.provisionables()
        return all_provisionables
    
    def refs_for_provisionables(self, my_ref=None):
        all_refs = set()
        for k, v in self._prov_source().items():
            if isinstance(v, Provisionable):
                if isinstance(k, KeyAsAttr):
                    all_refs.add(my_ref[k])
                else:
                    all_refs.add(getattr(self if my_ref is None else my_ref, k))
            elif isinstance(self, MultiBase):
                ref = my_ref[k]
                all_refs |= v.refs_for_provisionables(my_ref=ref)
            elif isinstance(self, ComponentGroupBase):
                if not isinstance(v, _ComputeProvisionables):
                    continue
                ref = getattr(my_ref, k)
                all_refs |= v.refs_for_provisionables(my_ref=ref)
            elif isinstance(v, _ComputeProvisionables):
                ref = getattr(self, k)
                all_refs |= v.refs_for_provisionables(my_ref=ref)
        return all_refs
    
    def _prov_source(self):
        "returns a dict of provisionables in an instance"
        raise TypeError("Derived class must implement _prov_source")
    

class MultiBase(InfraComponentBase, _ComputeProvisionables):
    def __init__(self, name):
        super(MultiBase, self).__init__(name)
        self._instances = {}
        
    def _validate_args(self, referenceable):
        super(MultiBase, self)._validate_args(referenceable)
        proto = self.get_prototype()
        proto._validate_args(referenceable)
        
    def __len__(self):
        return len(self._instances)
    
    def __iter__(self):
        return iter(self._instances)
    
    def __nonzero__(self):
        return len(self._instances) != 0
        
    def iterkeys(self):
        return self._instances.iterkeys()

    def _prov_source(self):
        return dict(self._instances)
    
    def get_prototype(self):
        raise TypeError("Derived class must implement, get_prototype()")
    
    def get_instance(self, key):
        inst = self._instances.get(key)
        if not inst:
            args, kwargs = self.get_prototype().get_init_args()
            #args[0] is the logicalName of the prototype
            #we form a new logical name by appending the
            #key to args[0] separated by an '_'
            logicalName = "%s_%s" % (args[0], str(key))
            inst = self.get_prototype().get_class()(logicalName, *args[1:], **kwargs)
            self._instances[key] = inst
        return inst
    
    def instances(self):
        return dict(self._instances)
    

class InfraSpec(_ComputeProvisionables):
    __metaclass__ = InfraSpecMeta
    
    def __init__(self, name):
        super(InfraSpec, self).__init__()
        self.name = name
        clone_cache = {}   #maps 
        ga = super(InfraSpec, self).__getattribute__
        attrdict = self.__dict__
        for k, v in ga(InfraSpecMeta._COMPONENTS).items():
            attrdict[k] = v.clone(clone_cache)
        self.provisioning_computed = False
        
    def provisioning_been_computed(self):
        return self.provisioning_computed
    
    def provisionables(self):
        provs = super(InfraSpec, self).provisionables()
        #We need some place where we have a reasonable expectations
        #that all logical refs have been eval'd against the model instance
        #and hence we can tell every Provisionable that's out there so we
        #can let them all know where the infra instance is.
        #
        #this is kind of crap to do here, but there really isn't a better place
        #unless we enforce some kind of stateful API that gives is a chance
        #to call _set_infra_instance(). This is a pretty cheap and harmless
        #sideeffect, and one that isn't so bad that fixing it by introducing some
        #sort of stateful API elements
        for prov in provs:
            prov._set_infra_instance(self)
        return provs
    
    def compute_provisioning_from_refs(self, modelrefs, exclude_refs=None):
        """
        Take a collection of model reference objects and compute the Provisionables needed
        to satisfy the refs. An optional collection of model refs can be supplied and any
        ref in both collections will be skipped when computing the Provisionables.
        
        @param modelrefs: an iterable of InfraModelReference instances for the model this
            SystemSpec instance is for
        @param exclude_refs: an iterable of InfraModelReference instances whioh should not
            be considered when computing Provisionables (this will be skipped)
        """
        if self.provisioning_computed:
            raise InfraException("The provisioning for this instance has already been computed")
        self.provisioning_computed = True
        if exclude_refs is None:
            exclude_refs = set()
        else:
            exclude_refs = set(exclude_refs)
        for mr in modelrefs:
            if mr not in exclude_refs:
                _ = self.get_inst_ref(mr)
            
    @classmethod
    def _class_refs_for_provisionables(cls, my_ref=None):
        all_refs = set()
        for k, v in cls.__dict__.items():
            if isinstance(v, Provisionable):
                if isinstance(k, KeyAsAttr):
                    all_refs.add(my_ref[k])
                else:
                    all_refs.add(getattr(cls if my_ref is None else my_ref, k))
            elif isinstance(v, MultiBase):
                ref = getattr(cls, k)
                all_refs |= v.refs_for_provisionables(my_ref=ref)
            elif isinstance(v, _ComputeProvisionables):
                ref = getattr(cls, k)
                all_refs |= v.refs_for_provisionables(my_ref=ref)
        return all_refs                
    
    def _prov_source(self):
        return dict(self.__dict__)
    
    def __getattribute__(self, attrname):
        ga = super(InfraSpec, self).__getattribute__
        value = (InfraModelInstanceReference(attrname, obj=self, parent=None)
                 if attrname in ga(InfraSpecMeta._COMPONENTS)
                 else ga(attrname))
        return value
    
    def get_inst_ref(self, model_ref):
        ref = self
        for p in model_ref.get_path():
            if isinstance(p, KeyAsAttr):
                ref = ref[p]
            else:
                ref = getattr(ref, p)
        return ref if ref != self else None
    
    
class MultiComponent(MultiBase):
    def __init__(self, templateComponent):
        super(MultiComponent, self).__init__(None)
        self.templateComponent = templateComponent
        
    def get_prototype(self):
        return self.templateComponent
        
    def get_init_args(self):
        args = (self.templateComponent.clone({}),)
        return (args, {})
        
        
class ComponentGroupBase(InfraComponentBase, _ComputeProvisionables): pass


class MultiComponentGroup(MultiBase):
    def __init__(self, logicalName, **kwargs):
        super(MultiComponentGroup, self).__init__(logicalName)
        self.kwargs = kwargs
        class ComponentGroup(ComponentGroupBase):
            ldict = locals()
            clone_cache = {}
            for k, v in kwargs.items():
                ldict[k] = v.clone(clone_cache)
            del ldict, k, v, clone_cache
            
#             def _validate_args(self, referenceable):
#                 super(ComponentGroup, self)._validate_args(referenceable)
#                 for _, v in self.__class__.__dict__.items():
#                     if isinstance(v, InfraComponentBase):
#                         v._validate_args(referenceable)
            
            def __init__(self, logicalName):
                super(ComponentGroup, self).__init__(logicalName)
                clone_cache = {}
                for k, v in self.__class__.__dict__.items():
                    if isinstance(v, InfraComponentBase):
                        setattr(self, k, v.clone(clone_cache))
            
            def get_init_args(self):
                return ((self.logicalName,), {})
            
            def _prov_source(self):
                return dict(self.__dict__)
            
            def __nonzero__(self):
                return True
            
            
        self.groupTemplate = ComponentGroup(self.logicalName)
        self.groupClass = ComponentGroup
        
    def get_prototype(self):
        return self.groupTemplate
    
    def get_init_args(self):
        return ((self.logicalName,), self.kwargs)
    
