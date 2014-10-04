'''
Created on 7 Sep 2014

@author: tom
'''

from actuator.utils import ClassModifier, process_modifiers
from actuator.modeling import (ActuatorException,SpecBaseMeta, SpecBase,
                               ModelComponent, AbstractModelingEntity,
                               ModelInstanceReference, KeyAsAttr,
                               _ComputeModelComponents, ModelReference)


class InfraException(ActuatorException): pass


_infra_options = "__infra_options__"
_recognized_options = set(["long_names"])
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


@ClassModifier
def with_infra_components(cls, *args, **kwargs):
    """
    This function attaches additional components onto a class object.

    :param cls: a new class object
    :param args: no positional args are recognized
    :param kwargs: dict of names and associated components to provision; must
        all be derived from InfraComponentBase
    :return: None
    """
    components = getattr(cls, InfraSpecMeta._COMPONENTS)
    if components is None:
        raise InfraException("FATAL ERROR: no component collection on the class object")
    for k, v in kwargs.items():
        if not isinstance(v, AbstractModelingEntity):
            raise InfraException("Argument %s is not derived from InfraComponentBase" % k)
        if not isinstance(k, basestring):
            raise InfraException("Key %s is not a string" % str(k))
        setattr(cls, k, v)
        components[k] = v
    return


class Provisionable(ModelComponent):
    """
    This class serves as a marker class for any InfraComponentBase derived class as something
    that can actually be provisioned.
    """
    pass
        

class InfraSpecMeta(SpecBaseMeta):
#     _COMPONENTS = "__components"
    model_ref_class = ModelReference

    def __new__(cls, name, bases, attr_dict):
        components = {}
        for n, v in attr_dict.items():
            if isinstance(v, AbstractModelingEntity):
                components[n] = v
        attr_dict[cls._COMPONENTS] = components
        new_class = super(InfraSpecMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(new_class)
        new_class._class_refs_for_components()
        #
        #@FIXME: The validation here has been suspended as there are some deeper
        #design problems that have to be sorted out to fix it
#         for component in components.values():
#             component._validate_args(new_class)
        return new_class
            
    

# class InfraSpec(_ComputeProvisionables):
class InfraSpec(SpecBase):
    __metaclass__ = InfraSpecMeta
    ref_class = ModelInstanceReference
    
    def __init__(self, name):
        super(InfraSpec, self).__init__()
        self.name = name
        clone_cache = {}   #maps 
        ga = super(InfraSpec, self).__getattribute__
        attrdict = self.__dict__
        for k, v in ga(InfraSpecMeta._COMPONENTS).items():
            attrdict[k] = v.clone(clone_cache)
        self.provisioning_computed = False
        
    def validate_args(self):
        for component in self.__class__.__dict__[InfraSpecMeta._COMPONENTS].values():
            component._validate_args(self)
        
    def provisioning_been_computed(self):
        return self.provisioning_computed
    
#     def provisionables(self):
    def components(self):
        comps = super(InfraSpec, self).components()
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
        for comp in comps:
            comp._set_infra_instance(self)
        return comps
    
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
            if mr not in exclude_refs and mr.get_containing_component_ref() not in exclude_refs:
                _ = self.get_inst_ref(mr)
            
    @classmethod
    def _class_refs_for_components(cls, my_ref=None):
        all_refs = set()
        for k, v in cls.__dict__[InfraSpecMeta._COMPONENTS].items():
            if isinstance(v, Provisionable):
                if isinstance(k, KeyAsAttr):
                    all_refs.add(my_ref[k])
                else:
                    all_refs.add(getattr(cls if my_ref is None else my_ref, k))
            elif isinstance(v, _ComputeModelComponents):
                ref = getattr(cls, k)
                all_refs |= v.refs_for_components(my_ref=ref)
        return all_refs                
    
    def _comp_source(self):
        return dict(self.__dict__)
    
    def __getattribute__(self, attrname):
        ga = super(InfraSpec, self).__getattribute__
        value = (self.ref_class(attrname, obj=self, parent=None)
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
    
    
class ServerRef(object):
    def get_admin_ip(self):
        raise TypeError("Not implemented")
