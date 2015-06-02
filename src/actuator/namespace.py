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
Support for creating Actuator namespace models
'''
import re
from actuator.utils import (ClassModifier, process_modifiers, capture_mapping,
                            get_mapper,  _Persistable)
from actuator.modeling import (AbstractModelReference, ModelComponent, ModelBase,
                               ModelReference, ModelInstanceReference, ModelBaseMeta,
                               ComponentGroup, MultiComponent, MultiComponentGroup,
                               CallContext, _Nexus, _ValueAccessMixin,
                               ContextExpr)
from actuator.infra import InfraModel


class NamespaceException(Exception): pass


_namespace_mapper_domain = object()


class _ModelRefSetAcquireable(object):
    #internal
    def _get_model_refs(self):
        return set()


class _ComputableValue(_ModelRefSetAcquireable, _Persistable):
    #Internal
    #
    #Mako-compatible replacement
    _prefix = r'\!{'
    _suffix = r'}'
    _replacement_pattern = re.compile("%s[a-zA-Z_]+[a-zA-Z0-9_]*%s" % (_prefix, _suffix))
    _prefix_len = 2
    _suffix_len = 1
    def __init__(self, value):
        """
        Create a new _ComputableValue instance
        
        @param value: Can be a plain string, a string with one or more replace-
            ment patterns in it, a AbstractModelReference, or a callable
        """
        if isinstance(value, basestring):
            self.value = str(value)
        elif isinstance(value, AbstractModelReference) or value is None or callable(value):
            self.value = value
        else:
            raise NamespaceException("Unrecognized value type: %s" % str(type(value)))
        
    def _is_value_persistable(self):
        return (isinstance(self.value, basestring) or
                isinstance(self.value, (AbstractModelReference, ContextExpr)) or
                self.value is None)
        
    def _find_persistables(self):
        for p in super(_ComputableValue, self)._find_persistables():
            yield p
        if isinstance(self.value, (ContextExpr, AbstractModelReference)):
            for p in self.value.find_persistables():
                yield p
                
    def _get_attrs_dict(self):
        d = super(_ComputableValue, self)._get_attrs_dict()
        d["value"] = self.value
        return d
        
    def _get_model_refs(self):
        s = set()
        if self.value_is_external():
            s.add(self.value)
        return s

    def value_is_external(self):
        """
        Predicate to indicate that the value for this item is to be acquired
        from a ModelComponent from elsewhere
        """
        return isinstance(self.value, AbstractModelReference)
        
    def expand(self, context, allow_unexpanded=False, raise_on_unexpanded=False):
        """
        Begins the computation of the value of the object supplied in the
        constructor. Returns the computed value, or may raise an exception if
        the value can't be computed
        
        @param context: A kind of L{VariableContainer} to anchor searches for
            other variables when replacement strings are discovered.
        @keyword allow_unexpanded: Optional, defaults to False. Indicates whether
            to return strings with un-expanded replacement patterns in them.
            With the default, the return value is None, which indicates that a
            value either hasn't been set or can't be fully determined. If True,
            then the string value will be processed as far as possible and will
            be returned in that state, possibly still with replacement patterns
            in the value.
        @keyword raise_on_unexpanded: Optional, defaults to False: Indicates what
            the method should do if a replacement pattern replaced (expanded)
            when it is encountered in the string whose value is being computed.
            The default, False, will just stop processing and return a value as
            dictated by the setting of allow_unexpanded. If True, then an exception
            is raised with a message about what can't be found in the string.
        """
        history = set([])
        return self._expand(context, history, allow_unexpanded=allow_unexpanded,
                            raise_on_unexpanded=raise_on_unexpanded)
        
    def _expand(self, context, history, allow_unexpanded=False,
                raise_on_unexpanded=False):
        if isinstance(self.value, AbstractModelReference):
            infra = context.find_infra_model()
            val = infra.get_inst_ref(self.value).value() if infra is not None else None
            return val
        elif callable(self.value):
            value = context._get_arg_value(self.value)
            if value is None:
                return None
        elif self.value is None:
            return None
        else:
            value = self.value
        m = self._replacement_pattern.search(value)
        while m:
            leader = value[:m.start()]
            trailer = value[m.end():]
            name = value[m.start()+self._prefix_len:m.end()-self._suffix_len]
            if name in history:
                raise NamespaceException("detected variable replacement loop with %s" % name)
            var, _ = context.find_variable(name)
            if var is None:
                if raise_on_unexpanded:
                    raise NamespaceException("Unable to determine value for '{}' in {}"
                                             .format(name, self.value))
                elif not allow_unexpanded:
                    value = None
                break
            else:
                history.add(name)
                value = "".join([leader,
                                 str(var.get_raw_value()._expand(context, history, allow_unexpanded)),
                                 trailer])
                history.remove(name)
            m = self._replacement_pattern.search(value)
        return value
    

class Var(_ModelRefSetAcquireable, _Persistable):
    """
    A container for a name-value pair in which the value is a L{_ComputableValue},
    and hence whose value can be a plain string, a string with replacement
    patterns, a callable that returns a string, or an AbstractModelReference. 
    """
    def __init__(self, name, value, in_env=True):
        """
        Define a new Var name-value pair.
        
        @param name: string; the 'name' in the pair. Cannot contain replacement
            patterns; if it does, they won't be processed
        @param value: Can be:
            1. A plain string
            2. A string with a replacement pattern ( !{name} )
            3. A callable that returns one of the above strings. The callable
                must take a single argument, a L{CallContext} instance that
                describes context where the callable is being invoked
            4. A AbstractModelReference that returns a string (that won't be
                processed further)
        @param in_env: Optional; default True. Indicates whether the Var should
            be included in any tasks for namespace L{Role} or not. By default,
            all Vars visible to a Role become part of any tasks for that Role.
            If you don't want the Var to be part of the environment (perhaps
            the Var has a sensitive value), then set in_env=False. Such Vars are
            only used in processing files and strings associated with tasks, and
            will not be sent along as part of the task's environment.
        """
        self.name = name
        self.value = _ComputableValue(value)
        self.in_env = in_env
        
    def _get_model_refs(self):
        return self.value._get_model_refs()
    
    def _is_value_persistable(self):
        return self.value._is_value_persistable()
    
    def _find_persistables(self):
        for p in super(Var, self)._find_persistables():
            yield p
        for p in self.value.find_persistables():
            yield p
    
    def _get_attrs_dict(self):
        d = super(Var, self)._get_attrs_dict()
        d.update( {"name":self.name,
                   "value":self.value,
                   "in_env":self.in_env} )
        return d

    def get_value(self, context, allow_unexpanded=False):
        """
        Get the value of Var evaluated from the perspective of a L{VariableContainer}
        
        Computes the value of the Var, invoking any callables and/or performing
        any expansions due to replacement patterns in the value string.
        
        @param context: A kind of L{VariableContainer} from which to anchor
            searches for other Vars when replacement patterns are found;
            replacements are always from the perspective of the context and the
            variable values it "sees".
        @keyword allow_unexpanded: Optional, default False. Determines what gets
            returned if an replacement pattern is discovered in a value and no
            replacement can be found. The default, False, means to return None,
            which indicates that a value can't be determined. If allow_unexpanded
            is True, then return as much as can be expanded and leave any
            unexpandable replacements patterns in the result. Usually a pair of
            calls modifying this value are used: first with the default to
            detect situations where the value can be computed, and then with
            allow_unexpanded==True to reveal how much expansion could be
            performed.
        """
        return self.value.expand(context, allow_unexpanded)
    
    def value_is_external(self):
        """
        Predicate that returns True if the value for the Var comes from an
        external source.
        """
        return self.value.value_is_external()
    
    def get_raw_value(self):
        """
        Return the un-interpreted value for the Var; this may be a string,
        reference, or callable.
        """
        return self.value
    
    
class VarFuture(_ValueAccessMixin):
    """
    A wrapper that allows a Var to be treated like reference into a model. Supports
    a value() method that allows deferring the computation of the variable until
    the value is needed. These are created by the future() method of
    L{VariableContainer}
    """
    def __init__(self, var, context):
        """
        Create a new VarFuture
        
        @param var: A Var object
        @param context: A kind of VariableContainer from which the Var's value
            can be computed.
        """
        self.var = var
        self.context = context
        
    def value(self, allow_unexpanded=False):
        """
        Compute the value of the Var from the perspective of the context.
        
        @keyword allow_unexpanded: Optional, default False. Indicates what to
            return if the Var can't be fully expanded (all replacement patterns
            can not be resolved). The default, False, means that if all patterns
            can't be replaced then return None as the result, which is only
            possible for unset values or for patterns that can't be replaced.
            If allow_unexpanded is True, return the result with as much as could
            be replaced.
        """
        return self.var.get_value(self.context, allow_unexpanded=allow_unexpanded)
    

class VarReference(_ValueAccessMixin):
    def __init__(self, var_cont, var_name):
        self.var_cont = var_cont
        self.var_name = var_name
            
    def __call__(self, allow_unexpanded=False):
        #@FIXME: we probably should have a check here if the container
        #has a var called var_name and raise a more useful exeception at
        #this point
        return self.var_cont.var_value(self.var_name,
                                       allow_unexpanded=allow_unexpanded)
    
    def value(self, allow_unexpanded=False):
        return self(allow_unexpanded=allow_unexpanded)
    
    
class VarValueAccessor(object):
    def __init__(self, var_cont):
        self.var_cont = var_cont
        
    def __getattr__(self, varname):
        return VarReference(self.var_cont, varname)
        

class VariableContainer(_ModelRefSetAcquireable, _Persistable):
    """
    A base mixin class for other classes that allows the class to be a
    container for Var objects.
    
    VariableContainers are arranged in a hierarchy, so that variables that
    can't be found in one container may be searched for in a parent. Searches
    for variables always start at the most "local" container.
    """
    def __init__(self, parent=None, variables=None, overrides=None):
        """
        Create a new VariableContainer
        
        @keyword parent: Optional; a kind of VariableContainer. This will be treated
            as the new container's parent, and any searches for variables in
            this container that can't be satisfied will continue with the parent
            if there is one. The default is no parent.
        @keyword variables: Optional; a sequence of Var objects that are used to
            initially populate the container with variables.
        @keyword overrides: Optional; a sequence of Var objects. Overrides
            provide a non-destructive way to supplying an alternate value for
            a variable. Normally, supplying a new Var with the same name as
            an existing Var overwrites the old Var, but overrides are managed
            independently and simply mask any variable Vars with the same name.
            Overrides can be cleared out later, allowing the original variable
            to be visible once again.
        """
        super(VariableContainer, self).__init__()
        self.v = VarValueAccessor(self)
        self.variables = {}
        self.overrides = {}
        self.parent_container = parent
        if variables is not None:
            self.add_variable(*variables)
        if overrides is not None:
            self.add_override(*overrides)
            
    def _get_attrs_dict(self):
        d = super(VariableContainer, self)._get_attrs_dict()
        persistable_vars = {v.name:(v if v._is_value_persistable()
                                    else v.get_value(self, allow_unexpanded=True))
                            for v in self.variables.values()}
        persistable_overrides = {v.name:(v if v._is_value_persistable()
                                         else v.get_value(self, allow_unexpanded=True))
                                 for v in self.overrides.values()}
        d.update( {"variables":persistable_vars,
                   "overrides":persistable_overrides,
                   "parent_container":self.parent_container,
                   "v":None} )
        return d
    
    def recover_attr_value(self, k, v, catalog):
        if k == "v":
            retval = VarValueAccessor(self)
        else:
            retval = super(VariableContainer, self).recover_attr_value(k, v, catalog)
        return retval
    
    def _find_persistables(self):
        for p in super(VariableContainer, self)._find_persistables():
            yield p
        for v in self.variables.values():
            if v._is_value_persistable():
                for p in v.find_persistables():
                    yield p
        for v in self.overrides.values():
            if v._is_value_persistable():
                for p in v.find_persistables():
                    yield p
        if self.parent_container:
            for p in self.parent_container.find_persistables():
                yield p
                
    def finalize_reanimate(self):
        for d in [self.variables, self.overrides]:
            for k, v in d.items():
                if isinstance(v, basestring):
                    d[k] = Var(k, v)
                    
    def _set_parent(self, parent):
        self.parent_container = parent
    
    def _get_model_refs(self):
        all_vars = dict(self.variables)
        all_vars.update(self.overrides)
        modelrefs = set()
        for v in all_vars.values():
            modelrefs |= v._get_model_refs()
        return modelrefs
    
    def add_variable(self, *args):
        """
        Adds one or more Vars to the container. Returns self so other calls
        can be chained from this one.
        
        @param *args: One or more Var objects. This method can take an 
            arbitrary number of Var objects in the invocation and put them
            into its variable storage. If something not Var is passed in an
            exception is raised.
        """
        for v in args:
            if not isinstance(v, Var):
                raise NamespaceException("'%s' is not a Var" % str(v))
            self.variables[v.name] = v
        return self
            
    def add_override(self, *args):
        """
        Adds one or more Vars to the overrides collection in the container.
        Overrides are searched first for a particular Var, so their value
        takes precedence. Returns self so other calls can be chained from this
        one.
        
        @param *args: One or more Var objects. This method can take an arbitrary
        number of Var objects when invoked and put them into the overrides
        collection. If something not a Var is passed ii an exception is
        raised.
        """
        for v in args:
            if not isinstance(v, Var):
                raise TypeError("'%s' is not a Var" % str(v))
            self.overrides[v.name] = v
        return self
            
    def find_variable(self, name):
        """
        Locates the named Var and the VariableContainer where it is defined.
        
        This method is concerned with finding a named Var and the container
        that manages it, as opposed to actually determining the Var's value.
        Self's overrides are first searched from the Var, and then self's
        variables, and if it can't be found in either of those places, self's
        parent is searched (if it has one).
        
        When the Var is found, the method returns a 2-tuple: the Var, and the
        VariableContainer that manages the Var (or None, None if no Var with
        the supplied name can be found).
        
        @param name: String; name of the Var to locate.
        """
        value = self.overrides.get(name)
        provider = self
        if value is None:
            value = self.variables.get(name)
        if value is None:
            value, provider = self.parent_container.find_variable(name) if self.parent_container else (None, None)
        return value, provider
    
    def var_value(self, name, allow_unexpanded=False):
        """
        Locate the named Var and return it's value relative to the current
        VariableContainer.
        
        Using the search rules from L{find_variable}, locate the Var with the
        supplied name, and then return the computed value for the Var from
        the perspective of the current VariableContainer
        
        @param name: string; the name of the Var to locate
        @keyword allow_unexpanded: Optional; default False. Determines what
            happens if a Var's value can't have all replacement patterns
            expanded. The default, False, causes None to be returned if all
            patterns can't be expanded. If True, then as much expansion as
            possible is performed and the result in returned, possibly still
            with replacement patterns in the returned value.
        """
        v, _ = self.find_variable(name)
        return v.get_value(self.get_context(), allow_unexpanded=allow_unexpanded)
    
    def get_context(self):
        return self
    
    def future(self, name):
        """
        Get a a L{VarFuture} object for the named Var.
        
        Searches for a Var named 'name' as per the search rules for L{find_variable},
        and if found return a L{VarFuture} object for the Var and the current
        VariableContainer, else None.
        
        @param name: String; name of the Var to find.
        """
        v, p = self.find_variable(name)
        return VarFuture(v, self) if (v and p) else None
    
    def find_infra_model(self):
        """
        Locate the infra model for this VariableContainer.
        
        Infra models are needed to perform certain Var processing; this
        method searches through the container hierarchy for the model to
        use. Returns the found infra model or None
        """
        model = self.get_infra_model()
        if model is None and self.parent_container:
            model = self.parent_container.find_infra_model()
        return model
            
    def get_infra_model(self):
        """
        Get the infra model on this container.
        
        Default implementation has no model so it returns None.
        """
        return None

    def get_visible_vars(self):
        """
        Return all the Vars visible to this container
        
        Computes the set of Vars visible to this container, taking into account
        parent containers and overrides, and the returns a dict containing
        the Vars that would be used from the perspective of this container.
        """
        d = self.parent_container.get_visible_vars() if self.parent_container else {}
        d.update(self.variables)
        d.update(self.overrides)
        return d
    

_common_vars = "__common_vars__"
def with_variables(cls, *args, **kwargs):
    """
    Used at the class level of a Namespace class model to set global Vars
    on the model. May be called repeatedly to set additional Vars.
    
    @param *args: One or more Var objects.
    """
    vars_list = cls.__dict__.get(_common_vars)
    if vars_list is None:
        vars_list = []
        setattr(cls, _common_vars, vars_list)
    vars_list.extend(list(args))
with_variables = ClassModifier(with_variables)


_common_roles = "__roles"
def with_roles(cls, *args, **kwargs):
    """
    Used at the class level of a Namespace class model to add Roles to the
    model. Role, RoleGroup, MultiRole, and MultiRoleGroup may be added to
    the model with this call. Can be called multiple times to add addtional
    Roles.
    """
    for k, v in kwargs.items():
        setattr(cls, k, v)
with_roles = ClassModifier(with_roles)


class ModelInstanceFinderMixin(object):
    #relies on the protocol for both ModelComponent and VariableContainer
    def get_model_instance(self):
        """
        Locate the Namespace model instance that self is a part of.
        """
        result = None
        mi = super(ModelInstanceFinderMixin, self).get_model_instance()
        if mi:
            result = mi
        elif self.parent_container is not None:
            if isinstance(self.parent_container, NamespaceModel):
                result = self.parent_container
            else:
                result = self.parent_container.get_model_instance()
        return result
    
    
class Role(ModelInstanceFinderMixin, ModelComponent, VariableContainer):
    """
    Defines a role for some component of a system, optionally establishing 
    Vars and its place in the namespace hierarchy.
    
    A Role is logical construct names a particular functional component of a
    system, for instance the "db role" or the "web app" role. Roles are tied
    to specific parts of the infra model that names where they should run and
    indicates what tasks should be carried out on their behalf and where.
    
    Roles are kinds of L{VariableContainer}s, and hence can hold L{Var}s
    as both variables and overrides. They are also L{ModelComponent}s,
    and hence respect the interface defined by that class.
    """
    def __init__(self, name, host_ref=None, variables=None, model=None):
        """
        Create a new Role, optionally defining an infra reference to a host
        and a start-up set of Vars.
        
        @param name: String; logical name of the Role
        @keyword host_ref: Optional; provides a way to identify an IPAddressable
            for this Role; this will indicate where Config tasks and software
            will execute for this role. This may be a string with a host name or
            IP address, a model reference to an IPAddressable, a context
            expression for an IPAddressable, or a callable that returns one
            of the above.
        @keyword variables: Optional; a sequence of Var objects that will be 
            defined on this Role
        @keyword model: Used internally only
        """
        super(Role, self).__init__(name, model_instance=model)
        self.host_ref = None
        self._host_ref = host_ref
        if variables is not None:
            self.add_variable(*variables)
            
    def clone(self, clone_into_class=None):
        """
        Create a copy of the initial state of this Role
        
        Creates a copy of the Role as if the original arguments to __init__()
        were used (in fact, they are).
        
        @keyword clone_into_class: internal
        """
        clone = super(Role, self).clone(clone_into_class=clone_into_class)
        clone._set_model_instance(self.get_model_instance())
        return clone
    
    def _get_attrs_dict(self):
        d = super(Role, self)._get_attrs_dict()
        d["host_ref"] = self.host_ref
        return d
    
    def _find_persistables(self):
        for p in super(Role, self)._find_persistables():
            yield p
        if isinstance(self.host_ref, _Persistable):
            for p in self.host_ref.find_persistables():
                yield p
    
    def _get_arg_value(self, arg):
        #internal
        val = super(Role, self)._get_arg_value(arg)
        if isinstance(val, basestring):
            #check if we have a variable to resolve
            cv = _ComputableValue(val)
            val = cv.expand(self)
        elif isinstance(val, ModelReference) and self.find_infra_model():
            val = self.find_infra_model().get_inst_ref(val).value()
        return val
            
    def _fix_arguments(self):
        #internal
        host_ref = self._get_arg_value(self._host_ref)
        if not isinstance(host_ref, AbstractModelReference):
            #@FIXME: The problem here is that it won't always be possible
            #to find a ref object of some kind. If the value supplied was
            #a hard-coded string or variable override, then there will
            #never be a ref object available for it. In that case we
            #need to return the object that was already there. This is
            #probably going to happen more often that we'd like
            tmp_ref = AbstractModelReference.find_ref_for_obj(self._get_arg_value(host_ref))
            if tmp_ref is not None:
                host_ref = tmp_ref
        self.host_ref = host_ref
            
    def get_init_args(self):
        __doc__ = ModelComponent.__doc__
        _, kwargs = super(Role, self).get_init_args()
        kwargs.update({"host_ref":self._host_ref,
                       "variables":self.variables.values(),})
        return ((self.name,), kwargs)
        
    def _get_model_refs(self):
        #internal
        modelrefs = super(Role, self)._get_model_refs()
        if self.host_ref is not None:
            modelrefs.add(self.host_ref)
        return modelrefs
                

@capture_mapping(_namespace_mapper_domain, ComponentGroup)
class RoleGroup(ModelInstanceFinderMixin, ComponentGroup, VariableContainer):
    """
    Defines a group of Roles that are used together; a kind of L{ComponentGroup}.
    
    This class allows a set of Roles to be grouped together so that the group
    can be used easily in single model. The use cases for this tend to be
    situations where a set of Roles all are associated to a single IPAddressable
    in an infra model, as otherwise it gets a bit clumsy to name different
    IPAddressables to associate with each Role in the group. 
    """
    def _set_model_instance(self, mi):
        super(RoleGroup, self)._set_model_instance(mi)
        for c in [v for k, v in self.__dict__.items() if k in self._kwargs]:
            c._set_model_instance(mi)
            c._set_parent(self)

    def clone(self, clone_into_class=None):
        """
        Create a copy of the initial state of this RoleGroup
        
        Creates a copy of the RoleGroup as if the original arguments to __init__()
        were used (in fact, they are).
        
        @keyword clone_into_class: internal
        """
        clone = super(RoleGroup, self).clone(clone_into_class=clone_into_class)
        clone._set_model_instance(self.get_model_instance())
        for c in (v for k, v in clone.__dict__.items() if k in self._kwargs):
            c._set_parent(clone)
        clone.add_variable(*self.variables.values())
        clone.add_override(*self.overrides.values())
        
        return clone
    
    def _get_model_refs(self):
        modelrefs = super(RoleGroup, self)._get_model_refs()
        for c in self.components():
            modelrefs |= c._get_model_refs()
        return modelrefs
    

@capture_mapping(_namespace_mapper_domain, MultiComponent)
class MultiRole(ModelInstanceFinderMixin, MultiComponent, VariableContainer):
    """
    Provides a way to name multiple instances of the same template Role that
    map to different resources in the infra model.
    
    The MultiRole class provides a means to have sets of near-identical Roles
    created to go along with multiple instances of a infra server resource.
    The canonical example would be a compute grid; each logical compute Role
    in the namespace should be associated with an independent server resource
    in the infra model.
    
    Once part of a model, the MultiRole can be treated like a dict, except that
    new keys cause new instances of the template Role to be created, which in
    turn can drive the creation of new infra model resources.
    
    MultiRoles are a kind of L{MultiComponent}, and hence follow the instatiation
    rules for those objects with the exception that the template object is
    a Role or other Role container (such as another MultiRole).
    
    See the base classes L{MultiComponent} annd L{VariableContainer} for details
    on instantiation and usage. 
    """
    def _set_model_instance(self, mi):
        super(MultiRole, self)._set_model_instance(mi)
        for c in self.instances().values():
            c._set_model_instance(mi)
            
    def clone(self, clone_into_class=None):
        """
        Create a copy of the initial state of the MultiRole. This is generally
        only used by Actuator itself to ensure Role independence.
        
        @keyword clone_into_class: used internally.
        """
        clone = super(MultiRole, self).clone(clone_into_class=clone_into_class)
        for k, v in self._instances.items():
            child = v.clone()
            child._set_parent(clone)
            clone._instances[k] = child
        clone._set_model_instance(self.get_model_instance())
        clone.add_variable(*self.variables.values())
        clone.add_override(*self.overrides.values())
        return clone
    
    def get_instance(self, key):
        """
        Returns an instance of the template identified by the 'key'.
        
        If the 'key' has been seen before, return the instance that was created
        for the key. If this is a new key, create a new instance for the key
        and return that.
        
        @param key: Immutable key to identify the instance to return. This will
            be coerced to a string internally.
        """
        inst = super(MultiRole, self).get_instance(key)
        inst._set_parent(self)
        inst._set_model_instance(self.get_model_instance())
        return inst
    
    def _get_model_refs(self):
        modelrefs = super(MultiRole, self)._get_model_refs()
        for c in self.instances().values():
            modelrefs |= c._get_model_refs()
        return modelrefs
    

@capture_mapping(_namespace_mapper_domain, MultiComponentGroup)
class MultiRoleGroup(MultiRole, VariableContainer):
    """
    Allow the creation of multiple RoleGroup based on a key.
    
    This is a convenience class that simply wraps a L{RoleGroup} in a
    L{MultiRole} so that a group of roles can be created with each new key
    used to index into the group. Like MultiRole, this class behaves like a
    dict, where keys are immutable and coerced to strings.
    
    See the base classes L{MultiRole} and L{VariableContainer} for more info
    on instantiation and usage. 
    """
    def __new__(self, name, **kwargs):
        group = RoleGroup(name, **kwargs)
        return MultiRole(group)
    
        
class NamespaceModelMeta(ModelBaseMeta):
    model_ref_class = ModelReference
    def __new__(cls, name, bases, attr_dict):
        cmapper = get_mapper(_namespace_mapper_domain)
        for k, v in attr_dict.items():
            if isinstance(v, (ComponentGroup, MultiComponent, MultiComponentGroup)):
                mapped_class = cmapper[v.__class__]
                attr_dict[k] = v.clone(clone_into_class=mapped_class)
        newbie = super(NamespaceModelMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(newbie)
        _Nexus._add_model_desc("ns", newbie)
        return newbie
    

class NamespaceModel(VariableContainer, ModelBase):
    """
    Base class for Namespace model classes.
    
    To create a new namespace model, derive a class from this class and add
    roles, Vars, etc.
    
    See the base classes L{VariableContainer} and L{ModelBase} for info on
    other methods.
    
    @ivar ivar: infra. DEPRECATED-- use self.nexus.inf instead
    """
    __metaclass__ = NamespaceModelMeta
    ref_class = ModelInstanceReference

    def __init__(self):
        """
        Create a new instance of the namespace model that can be further
        customized with different Var values.
        
        Makes a new instance of namespace model for a system. This method may
        be overridden as long as you call super().__init__() in the derived
        class's __init__() method.
        """
        super(NamespaceModel, self).__init__()
        components = set()
        clone_map = {}
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, (Role, ComponentGroup, MultiComponent, MultiComponentGroup)):
                components.add((k, v))
        for k, c in components:
            clone = c.clone()
            clone._set_model_instance(self)
            clone._set_parent(self)
            clone_map[c] = (k, clone)
        self._roles = {}
        for _, (key, clone) in clone_map.items():
            self._roles[key] = clone
            setattr(self, key, clone)
        
        if _common_vars in self.__class__.__dict__:
            self.add_variable(*self.__class__.__dict__[_common_vars])
        self.infra = None
        
    def __new__(cls, *args, **kwargs):
        inst = super(NamespaceModel, cls).__new__(cls, *args, **kwargs)
        return inst
    
    def _find_persistables(self):
        for p in super(NamespaceModel, self)._find_persistables():
            yield p
        for v in self._roles.values():
            if isinstance(v, _Persistable):
                for p in v.find_persistables():
                    yield p
    
    def _get_attrs_dict(self):
        d = super(NamespaceModel, self)._get_attrs_dict()
        ga = super(NamespaceModel, self).__getattribute__
        d.update( {"infra":ga("infra"),
                   "_roles":ga("_roles")} )
        d.update(self._roles)
        return d
    
    def _comp_source(self):
        return self.get_roles()
    
    def _get_model_refs(self):
        modelrefs = super(NamespaceModel, self)._get_model_refs()
        for c in self._roles.values():
            modelrefs |= c._get_model_refs()
        return modelrefs
    
    def get_roles(self):
        """
        Returns a dict of all the roles defined on the model. This includes
        the Role containers such as RoleGroup and MultiRole.
        """
        return dict(self._roles)
    
    def get_infra_model(self):
        """
        Returns the infra model for this namespace, if one has been specified.
        """
        return self.infra
    
    def set_infra_model(self, infra_model):
        """
        Internal; set the infra model instance to be used by this namespace instance.
        
        @param infra_model: An instance of some kind of L{InfraModel} derived
            class. Raises an exception is the infra has already been supplied,
            or if the model isn't a kind of InfraModel.
        """
        if self.infra is None:
            if isinstance(infra_model, InfraModel):
                self.infra = infra_model
            else:
                raise NamespaceException("The infra_model argument isn't an "
                                         "instance of InfraModel; {}"
                                         .format(str(infra_model)))
        elif self.infra is not infra_model:
            raise NamespaceException("A different infra model has already been supplied")
        infra_model.nexus.merge_from(self.nexus)
        self.nexus = infra_model.nexus
    
    def compute_provisioning_for_environ(self, infra_instance, exclude_refs=None):
        """
        Computes the provisioning needed for an instance of a namespace model.
        
        This method takes an infra model instance and for the current state of
        the namespace computes the required resources that need to be provisioned
        to satisfy the requirements of the namespace. It then returns a set
        containing the infra resources to be provisioned. Users usually have no
        need for this method; it is there for internal use, but made available
        for inspecting how a namespace model instance impacts an infra
        instance.
        
        This method sets the infra instance to use with this model
        
        @param infra_instance: An instance of an InfraModel derived class.
        @keyword exclude_refs: An iterable of references to exclude from the
            resulting set of provisionable resources. These can be either
            model or instance references.
        """
        self.set_infra_model(infra_instance)
        if exclude_refs is None:
            exclude_refs = set()
        exclude_refs = set([infra_instance.get_inst_ref(ref) for ref in exclude_refs])
        self.refs_for_components()
        for v in self._roles.values():
            v.fix_arguments()
        self.infra.compute_provisioning_from_refs(self._get_model_refs(), exclude_refs)
        return set([p for p in self.infra.components()
                    if AbstractModelReference.find_ref_for_obj(p) not in exclude_refs])
        
    def add_roles(self, **kwargs):
        """
        Add a group of plain Roles to the model instance.
        
        This method provides a way to add Roles to an already instantiated 
        namespace model object. The Roles are supplied as keyword arguments, and
        each keyword is turned into an attribute on the namespace instance object.
        Added roles only have an impact if they are added before the computation
        of provisioning.
        
        @keyword **kwargs: A series of keyword args, the values of which must
            be instances of L{Role}. These are added to the set of Roles for the
            model instance, and each keyword is also turned into an attribute
            (with the corresponding Role as value) on the model instance.
        """
        for k, v in kwargs.items():
            if not isinstance(v, Role):
                raise NamespaceException("%s is not a kind of role or role container" % str(v))
            clone = v.clone()
            self._roles[k] = clone
            self.__dict__[k] = clone
        return self
