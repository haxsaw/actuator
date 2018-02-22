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
Support for creating Actuator infrastructure models
"""

from errator import narrate, narrate_cm
from actuator.utils import (ClassModifier, process_modifiers, _Persistable, KeyAsAttr,
                            _Performable)
from actuator.modeling import (ActuatorException, ModelBaseMeta, ModelBase,
                               ModelComponent, AbstractModelingEntity,
                               ModelInstanceReference,
                               _ComputeModelComponents, ModelReference,
                               ComponentGroup, MultiComponent,
                               MultiComponentGroup, AbstractModelReference,
                               _Nexus)
from actuator.task import TaskEventHandler


class InfraException(ActuatorException):
    pass


_infra_options = "__infra_options__"
_long_names = "long_names"
_recognized_options = {_long_names}


@ClassModifier
def with_infra_options(cls, *_, **kwargs):
    """
    Available options:
    @keyword long_names: boolean, defaults to False. This option provides info
        to resources as to what "display name" to use when asked by the
        provisioner. By default, a "short" name is used, specifically the name
        given to the resource. However, there are cases where more than one
        instance of a resource with the same name may get generated, making it
        hard to determine which is which in various reports from cloud systems.
        Use long_names=True will use a name that starts with the name of the
        infra model, continues with the 'path' to the resource, and terminates
        with the short name for the resource. If infra model instances are
        uniquely named, this will result in unique display names for every
        resource provisioned.
    """
    opts_dict = cls.__dict__.get(_infra_options)
    if opts_dict is None:
        opts_dict = {}
        setattr(cls, _infra_options, opts_dict)
    for k, v in kwargs.items():
        if k not in _recognized_options:
            raise InfraException("Unrecognized InfraModel option: %s" % k)
        opts_dict[k] = v


@ClassModifier
def with_resources(cls, *_, **kwargs):
    """
    This function attaches additional resources onto a class object.

    :param cls: a new class object
    :param kwargs: dict of names and associated components to provision; must
        all be derived from AbstractModelingEntity
    :return: None
    """
    components = getattr(cls, InfraModelMeta._COMPONENTS)
    if components is None:
        raise InfraException("FATAL ERROR: no components collection on the class object")
    for k, v in kwargs.items():
        if not isinstance(v, AbstractModelingEntity):
            raise InfraException("Argument %s is not derived from AbstractModelingEntity" % k)
        setattr(cls, k, v)
        components[k] = v
    return


class _LongnameProp(object):
    def __get__(self, inst, _):
        mi = inst.get_model_instance()
        ref = AbstractModelReference.find_ref_for_obj(inst)
        ln = ".".join(([mi.name] if mi else ["NONE"]) +
                      (ref.get_path() if ref else []) +
                      [inst.name])
        return ln
    

class _LNMixin(object):
    longname = _LongnameProp()


class ResourceGroup(_LNMixin, ComponentGroup):
    """
    A specialization of the L{ComponentGroup} class
    """
    pass


class MultiResource(_LNMixin, MultiComponent):
    """
    A specialization of the L{MultiComponent} class
    """
    pass


class MultiResourceGroup(_LNMixin, MultiComponentGroup):
    """
    A specialization of the L{MultiComponentGroup} class
    """
    def __new__(cls, name, **kwargs):
        namesep = kwargs.pop("namesep", "_")
        group = ResourceGroup(name, **kwargs)
        return MultiResource(group, namesep=namesep)


class Provisionable(_LNMixin, ModelComponent, _Performable):
    """
    This class serves as a marker class for any L{ModelComponent} derived
    class as something that can actually be provisioned.
    """
    # def __init__(self, *args, **kwargs):
    #     if "other_deps" in kwargs:
    #         self._other_deps = list(kwargs["other_deps"])
    #         del kwargs["other_deps"]
    #     else:
    #         self._other_deps = []
    #     self.other_deps = None
    #     super(Provisionable, self).__init__(*args, **kwargs)
    #
    # def _fix_arguments(self):
    #     super(Provisionable, self)._fix_arguments()
    #     self.other_deps = [d.fix_arguments() for d in self._other_deps
    #                        if isinstance(d, Provisionable)]

    def __init__(self, *args, **kwargs):
        cloud = None
        if "cloud" in kwargs:
            cloud = kwargs["cloud"]
            del kwargs["cloud"]
        self._cloud = cloud
        self.cloud = None
        super(Provisionable, self).__init__(*args, **kwargs)

    @narrate(lambda s: "...and so we asked for the base init args "
                       "from provisionable {}".format(s.name))
    def _get_attrs_dict(self):
        """
        We need to add in this method as _Performable adds an attribute we need
        to persist, and ModelComponent is a kind of _Persistable
        """
        d = super(Provisionable, self)._get_attrs_dict()
        d["performance_status"] = self.performance_status
        d["cloud"] = self.cloud
        return d

    def _fix_arguments(self):
        self.cloud = self._get_arg_value(self._cloud) if self._cloud is not None else None

    def get_init_args(self):
        args, kwargs = super(Provisionable, self).get_init_args()
        kwargs["cloud"] = self._cloud
        return args, kwargs

    def get_display_name(self):
        """
        Returns the name to use in reports and displays.
        
        This method returns either the resource name or resource longname,
        depending on whether or not the long_names option was set on the
        infra model the resource is attached to.
        """
        mi = self.get_model_instance()
        return self.longname if (mi and mi._long_names) else self.name
        

class InfraModelMeta(ModelBaseMeta):
    model_ref_class = ModelReference

    def __new__(mcs, name, bases, attr_dict):
        new_class = super(InfraModelMeta, mcs).__new__(mcs, name, bases, attr_dict)
        process_modifiers(new_class)
        new_class._class_refs_for_resources()
        _Nexus._add_model_desc("inf", new_class)
        return new_class
            

class InfraModel(ModelBase):
    """
    This is the base class to use for any infrastructure model. Derive a class
    from this class to make your own infra models.
    """
    __metaclass__ = InfraModelMeta
    ref_class = ModelInstanceReference
    
    def __init__(self, name, event_handler=None, **kwargs):
        """
        Creates a new instance of an infra model.
        
        You may override this method as long as you call super().__init__()
        in the derived class's __init__() method.
        
        @param name: a logical name for the infra instance
        """
        if event_handler is not None and not isinstance(event_handler, TaskEventHandler):
            raise InfraException("event_handler is not a kind of TaskEventHandler")
        super(InfraModel, self).__init__(name, **kwargs)
        # self.name = name
        self.event_handler = event_handler
        # set option defaults
        self._long_names = False
        # process options
        opts = self.__class__.__dict__.get(_infra_options)
        if opts:
            for k, v in opts.items():
                if k == _long_names:
                    self._long_names = v
        ga = super(InfraModel, self).__getattribute__
        # update self.__dict__ with clones of the model's components
        attrdict = self.__dict__
        for k, v in ga(InfraModelMeta._COMPONENTS).items():
            attrdict[k] = clone = v.clone()
            clone._set_model_instance(self)
        self.provisioning_computed = False

    def get_event_handler(self):
        return self.event_handler

    def set_event_handler(self, handler):
        self.event_handler = handler

    @narrate(lambda s: "...so we asked infra model %s for it attrs dict".format(s.name))
    def _get_attrs_dict(self):
        d = dict(self.__dict__)
        d.update(super(InfraModel, self)._get_attrs_dict())
        # don't save the event_handler
        d["event_handler"] = None
        return d
    
    def _find_persistables(self):
        with narrate_cm(lambda s: "---so we started looking for persistables "
                                  "in model {}".format(s.name), self):
            for p in self.__dict__.values():
                if isinstance(p, _Persistable):
                    for q in p.find_persistables():
                        yield q
        
    def validate_args(self):
        """
        Currently unused
        """
        for resource in self.__class__.__dict__[InfraModelMeta._COMPONENTS].values():
            resource._validate_args(self)
        
    def provisioning_been_computed(self):
        """
        Returns if provisioning has been run on this model instance.
        """
        return self.provisioning_computed
    
    @narrate(lambda s: "...which caused us to look for the components in {}".format(s.name))
    def components(self):
        """
        Returns a set with the unique resources to provision on this instance.
        """
        _resources = super(InfraModel, self).components()
        # We need some place where we have a reasonable expectations
        # that all logical refs have been eval'd against the model instance
        # and hence we can tell every Provisionable that's out there so we
        # can let them all know where the infra instance is.
        #
        # this is kind of crap to do here, but there really isn't a better place
        # unless we enforce some kind of stateful API that gives is a chance
        # to call _set_model_instance(). This is a pretty cheap and harmless
        # sideeffect, and one that isn't so bad that fixing it by introducing some
        # sort of stateful API elements
        for resource in _resources:
            resource._set_model_instance(self)
        return _resources
    
    resources = components

    @narrate(lambda s, mr, *kw: "...so we started computing provising for all "
                                "model refs in {}".format(s.name))
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
            return
        self.provisioning_computed = True
        if exclude_refs is None:
            exclude_refs = set()
        else:
            exclude_refs = set(exclude_refs)
        for mr in modelrefs:
            if mr not in exclude_refs and mr.get_containing_component_ref() not in exclude_refs:
                _ = self.get_inst_ref(mr)
            
    @classmethod
    @narrate("...which required us to find all the refs for each component in the infra model")
    def _class_refs_for_resources(cls, my_ref=None):
        all_refs = set()
        for k, v in cls.__dict__[InfraModelMeta._COMPONENTS].items():
            if isinstance(v, Provisionable):
                if isinstance(k, KeyAsAttr):  # this probably isn't possible
                    all_refs.add(my_ref[k])
                else:
                    all_refs.add(getattr(cls if my_ref is None else my_ref, k))
            elif isinstance(v, _ComputeModelComponents):
                ref = getattr(cls, k)
                all_refs |= v.refs_for_components(my_ref=ref)
        return all_refs                
    
    def _comp_source(self):
        return dict(self.__dict__)
    
    
class IPAddressable(object):
    """
    This is a protocol for any object that can acquire and be addressed with
    and IP adddress. Other classes derive from this to allow them to be used
    as references for other components.
    """
    def get_ip(self, context=None):
        """
        Return the IP address for self as a string. Derived classes are
        responsible for implementing this.
        
        @keyword context: Ignored; this param exists to allow this method to be
            used where callable params are allowed so that a L{CallContext} object
            can be passed in.
        """
        raise TypeError("Not implemented")

    def get_cidr4(self):
        """
        Return a string in CIDR format for the IPv4 address
        """
        raise TypeError("Not implemented")
    
    
class StaticServer(IPAddressable, Provisionable):
    """
    Represents an already existing server to be used in an infrastructure.
    
    A StaticServer provides a way knit non-dynamic (virtual or cloud) resources
    into an infra model. This resource won't be provisioned, as it already has,
    but it can be used wherever a reference to a server & L{IPAddressable} are
    required in other models.
    """
    def __init__(self, name, hostname_or_ip, **kwargs):
        """
        Create a new StaticServer instance.
        
        @param name: A logical name for the server
        @param hostname_or_ip: a resolveable name for the server, either an
            IP address or a host name (FQDN where required). Actuator assumes
            that the name will be resolveable if a hostname is provided.
        """
        super(StaticServer, self).__init__(name, **kwargs)
        self.hostname_or_ip = None
        self._hostname_or_ip = hostname_or_ip
        
    @narrate(lambda s: "...so we asked static server {} for its attr dict".format(s.name))
    def _get_attrs_dict(self):
        d = super(StaticServer, self)._get_attrs_dict()
        d["hostname_or_ip"] = self.hostname_or_ip
        return d
        
    @narrate(lambda s: "...so we asked static server {} to fix its args".format(s.name))
    def _fix_arguments(self):
        self.hostname_or_ip = self._get_arg_value(self._hostname_or_ip)

    @narrate(lambda s: "...so we asked static server {} finish reanimation".format(s.name))
    def finalize_reanimate(self):
        self._hostname_or_ip = self.hostname_or_ip

    @narrate(lambda s: "...so we asked static server {} for its init args".format(s.name))
    def get_init_args(self):
        __doc__ = Provisionable.get_init_args.__doc__
        return (self.name, self._hostname_or_ip), {}
    
    def get_ip(self, context=None):
        """
        Returns the hostname or IP that was provided in the constructor.
        
        @keyword context: Ignored; present so this method can be passed as a
            callable value for ann argument.
        """
        return self.hostname_or_ip
