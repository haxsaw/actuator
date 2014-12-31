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
import re
from actuator.utils import ClassModifier, process_modifiers, capture_mapping, get_mapper
from actuator.modeling import (AbstractModelReference, ModelComponent, ModelBase,
                               ModelReference, ModelInstanceReference, ModelBaseMeta,
                               ComponentGroup, MultiComponent, MultiComponentGroup,
                               ContextExpr)


class NamespaceException(Exception): pass


_namespace_mapper_domain = object()


class _ModelRefSetAcquireable(object):
    def _get_model_refs(self):
        return set()


class _ComputableValue(_ModelRefSetAcquireable):
    #Mako-compatible replacement
    _prefix = r'\!{'
    _suffix = r'}'
    _replacement_pattern = re.compile("%s[a-zA-Z_]+[a-zA-Z0-9_]*%s" % (_prefix, _suffix))
    _prefix_len = 2
    _suffix_len = 1
    def __init__(self, value):
        if isinstance(value, basestring):
            self.value = str(value)
        elif hasattr(value, "value"):
            self.value = value
        elif value is None:
            self.value = None
        else:
            raise NamespaceException("Unrecognized value type: %s" % str(type(value)))
        
    def _get_model_refs(self):
        s = set()
        if self.value_is_external():
            s.add(self.value)
        return s

    def value_is_external(self):
        return hasattr(self.value, "value")
        
    def expand(self, context, allow_unexpanded=False, raise_on_unexpanded=False):
        history = set([])
        return self._expand(context, history, allow_unexpanded=allow_unexpanded,
                            raise_on_unexpanded=raise_on_unexpanded)
        
    def _expand(self, context, history, allow_unexpanded=False,
                raise_on_unexpanded=False):
        if isinstance(self.value, AbstractModelReference):
            infra = context.find_infra_model()
            val = infra.get_inst_ref(self.value).value() if infra is not None else None
            return val
        elif isinstance(self.value, ContextExpr):
            value = context._get_arg_value(self.value)
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
                    raise NamespaceException("Unable to determine value for '{}'".format(name))
                elif not allow_unexpanded:
                    value = None
                break
            else:
                history.add(name)
                value = "".join([leader,
                                 var.get_raw_value()._expand(context, history, allow_unexpanded),
                                 trailer])
                history.remove(name)
            m = self._replacement_pattern.search(value)
        return value
    

class Var(_ModelRefSetAcquireable):
    def __init__(self, name, value):
        self.name = name
        self.value = _ComputableValue(value)
        
    def _get_model_refs(self):
        return self.value._get_model_refs()

    def get_value(self, context, allow_unexpanded=False):
        return self.value.expand(context, allow_unexpanded)
    
    def value_is_external(self):
        return self.value.value_is_external()
    
    def get_raw_value(self):
        return self.value
    
    
class VarFuture(object):
    def __init__(self, var, context):
        self.var = var
        self.context = context
        
    def value(self, allow_unexpanded=False):
        return self.var.get_value(self.context, allow_unexpanded=allow_unexpanded)
        

class VariableContainer(_ModelRefSetAcquireable):
    def __init__(self, parent=None, variables=None, overrides=None):
        super(VariableContainer, self).__init__()
        self.variables = {}
        self.overrides = {}
        self.parent_container = parent
        if variables is not None:
            self.add_variable(*variables)
        if overrides is not None:
            self.add_override(*overrides)
                    
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
        for v in args:
            if not isinstance(v, Var):
                raise NamespaceException("'%s' is not a Var" % str(v))
            self.variables[v.name] = v
        return self
            
    def add_override(self, *args):
        for v in args:
            if not isinstance(v, Var):
                raise TypeError("'%s' is not a Var" % str(v))
            self.overrides[v.name] = v
        return self
            
    def find_variable(self, name):
        value = self.overrides.get(name)
        provider = self
        if value is None:
            value = self.variables.get(name)
        if value is None:
            value, provider = self.parent_container.find_variable(name) if self.parent_container else (None, None)
        return value, provider
    
    def var_value(self, name):
        v, _ = self.find_variable(name)
        return v.get_value(self)
    
    def future(self, name):
        v, p = self.find_variable(name)
        return VarFuture(v, self) if (v and p) else None
    
    def find_infra_model(self):
        model = self.get_infra_model()
        if model is None and self.parent_container:
            model = self.parent_container.find_infra_model()
        return model
            
    def get_infra_model(self):
        return None
    
    def get_visible_vars(self):
        d = self.parent_container.get_visible_vars() if self.parent_container else {}
        d.update(self.variables)
        d.update(self.overrides)
        return d
    

_common_vars = "__common_vars__"
def with_variables(cls, *args, **kwargs):
    vars_list = cls.__dict__.get(_common_vars)
    if vars_list is None:
        vars_list = []
        setattr(cls, _common_vars, vars_list)
    vars_list.extend(list(args))
with_variables = ClassModifier(with_variables)


_common_comps = "__components"
def with_components(cls, *args, **kwargs):
    for k, v in kwargs.items():
        setattr(cls, k, v)
with_components = ClassModifier(with_components)


# class ComponentMeta(type):
#     cls_registry = {}
#     def __new__(cls, name, bases, attr_dict):
#         new_cls = super(ComponentMeta, cls).__new__(cls, name, bases, attr_dict)
#         cls.cls_registry[name] = new_cls
#         return new_cls
    

class ModelInstanceFinderMixin(object):
    #relies on the protocol for both ModelComponent and VariableContainer
    def get_model_instance(self):
        result = None
        if self._model_instance:
            result = self._model_instance
        elif self.parent_container is not None:
            if isinstance(self.parent_container, NamespaceModel):
                result = self.parent_container
            else:
                result = self.parent_container.get_model_instance()
        return result
    
    
class Role(ModelInstanceFinderMixin, ModelComponent, VariableContainer):
    def __init__(self, name, host_ref=None, variables=None, model=None):
        super(Role, self).__init__(name, model_instance=model)
        self.host_ref = None
        self._host_ref = host_ref
        if variables is not None:
            self.add_variable(*variables)
            
    def clone(self, clone_into_class=None):
        clone = super(Role, self).clone(clone_into_class=clone_into_class)
        clone._set_model_instance(self._model_instance)
        return clone
    
    def _get_arg_value(self, arg):
        val = super(Role, self)._get_arg_value(arg)
        if isinstance(val, basestring):
            #check if we have a variable to resolve
            cv = _ComputableValue(val)
            val = cv.expand(self)
        return val
            
    def _fix_arguments(self):
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
        _, kwargs = super(Role, self).get_init_args()
        kwargs.update({"host_ref":self._host_ref,
                       "variables":self.variables.values(),})
        return ((self.name,), kwargs)
        
    def _get_model_refs(self):
        modelrefs = super(Role, self)._get_model_refs()
        if self.host_ref is not None:
            modelrefs.add(self.host_ref)
        return modelrefs
                
    
@capture_mapping(_namespace_mapper_domain, ComponentGroup)
class RoleGroup(ModelInstanceFinderMixin, ComponentGroup, VariableContainer):
    def _set_model_instance(self, mi):
        super(RoleGroup, self)._set_model_instance(mi)
        for c in [v for k, v in self.__dict__.items() if k in self._kwargs]:
            c._set_model_instance(mi)

    def clone(self, clone_into_class=None):
        clone = super(RoleGroup, self).clone(clone_into_class=clone_into_class)
        clone._set_model_instance(self._model_instance)
        clone._set_parent(self.parent_container)
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
    def _set_model_instance(self, mi):
        super(MultiRole, self)._set_model_instance(mi)
        for c in self.instances().values():
            c._set_model_instance(mi)
            
    def clone(self, clone_into_class=None):
        clone = super(MultiRole, self).clone(clone_into_class=clone_into_class)
        for k, v in self._instances.items():
            child = v.clone()
            child._set_parent(clone)
            clone._instances[k] = child
        clone._set_parent(self.parent_container)
        clone._set_model_instance(self._model_instance)
        clone.add_variable(*self.variables.values())
        clone.add_override(*self.overrides.values())
        return clone
    
    def get_instance(self, key):
        inst = super(MultiRole, self).get_instance(key)
        inst._set_parent(self)
        inst._set_model_instance(self._model_instance)
        return inst
    
    def _get_model_refs(self):
        modelrefs = super(MultiRole, self)._get_model_refs()
        for c in self.instances().values():
            modelrefs |= c._get_model_refs()
        return modelrefs
    

@capture_mapping(_namespace_mapper_domain, MultiComponentGroup)
class MultiRoleGroup(MultiRole, VariableContainer):
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
        return newbie
    

class NamespaceModel(VariableContainer, ModelBase):
    __metaclass__ = NamespaceModelMeta
    ref_class = ModelInstanceReference

    def __init__(self):
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
        self._components = {}
        for _, (key, clone) in clone_map.items():
            self._components[key] = clone
            setattr(self, key, clone)
        
        if _common_vars in self.__class__.__dict__:
            self.add_variable(*self.__class__.__dict__[_common_vars])
        self.infra = None
        
    def __new__(cls, *args, **kwargs):
        inst = super(NamespaceModel, cls).__new__(cls, *args, **kwargs)
        return inst
    
    def _comp_source(self):
        return self.get_components()
    
    def _get_model_refs(self):
        modelrefs = super(NamespaceModel, self)._get_model_refs()
        for c in self._components.values():
            modelrefs |= c._get_model_refs()
        return modelrefs
    
    def get_components(self):
        return dict(self._components)
    
    def get_infra_model(self):
        return self.infra
    
    def set_infra_model(self, infra_model):
        if self.infra is None:
            self.infra = infra_model
        elif self.infra is not infra_model:
            raise NamespaceException("A different infra model has already been supplied")
    
    def compute_provisioning_for_environ(self, infra_instance, exclude_refs=None):
        self.infra = infra_instance
        if exclude_refs is None:
            exclude_refs = set()
        exclude_refs = set([infra_instance.get_inst_ref(ref) for ref in exclude_refs])
        self.refs_for_components()
        for v in self._components.values():
            v.fix_arguments()
        self.infra.compute_provisioning_from_refs(self._get_model_refs(), exclude_refs)
        return set([p for p in self.infra.components()
                    if AbstractModelReference.find_ref_for_obj(p) not in exclude_refs])
        
    def add_components(self, **kwargs):
        for k, v in kwargs.items():
            if not isinstance(v, Role):
                raise NamespaceException("%s is not a kind of component" % str(v))
            clone = v.clone()
            self._components[k] = clone
            self.__dict__[k] = clone
        return self
