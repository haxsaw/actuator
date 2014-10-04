'''
Created on 7 Sep 2014

@author: tom
'''
import re
from actuator.utils import ClassModifier, process_modifiers
from actuator.modeling import AbstractModelReference


class NamespaceException(Exception): pass


class _ModelRefSetAcquireable(object):
    def _get_model_refs(self):
        return set()


class _ComputableValue(_ModelRefSetAcquireable):
    _replacement_pattern = re.compile("\![a-zA-Z_]+[a-zA-Z0-9_]*\!")
    def __init__(self, value):
        if type(value) == str:
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
        
    def expand(self, context, allow_unexpanded=False):
        history = set([])
        return self._expand(context, history, allow_unexpanded)
        
    def _expand(self, context, history, allow_unexpanded=False):
        if hasattr(self.value, "value"):
            infra = context.find_infra()
            val = infra.get_inst_ref(self.value).value() if infra is not None else None
            return val
        elif self.value is None:
            return self.value
        value = self.value
        m = self._replacement_pattern.search(value)
        while m:
            leader = value[:m.start()]
            trailer = value[m.end():]
            name = value[m.start()+1:m.end()-1]
            if name in history:
                raise NamespaceException("detected variable replacement loop with %s" % name)
            var, _ = context.find_variable(name)
            if var is None:
                if not allow_unexpanded:
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
    def __init__(self, parent=None):
        self.variables = {}
        self.overrides = {}
        self.parent_container = parent
        
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
                raise Exception("'%s' is not a Var" % str(v))
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
    
    def future(self, name):
        v, p = self.find_variable(name)
        return VarFuture(v, self) if (v and p) else None
    
    def find_infra(self):
        infra = self.get_infra()
        if infra is None and self.parent_container:
            infra = self.parent_container.find_infra()
        return infra
            
    def get_infra(self):
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


_common_comps = "__common_comps__"
def with_components(cls, *args, **kwargs):
    for k, v in kwargs.items():
        setattr(cls, k, v)
with_components = ClassModifier(with_components)


class ComponentMeta(type):
    cls_registry = {}
    def __new__(cls, name, bases, attr_dict):
        new_cls = super(ComponentMeta, cls).__new__(cls, name, bases, attr_dict)
        cls.cls_registry[name] = new_cls
        return new_cls
    

class Component(VariableContainer):
    __metadata__ = ComponentMeta
    def __init__(self, name, host_ref=None, variables=None, parent=None):
        super(Component, self).__init__(parent=parent)
        self.name = name
        self.host_ref = host_ref
        if variables is not None:
            self.add_variable(*variables)
        
    def clone(self):
        return Component(self.name, host_ref=self.host_ref, variables=self.variables.values())
    
    def _get_model_refs(self):
        modelrefs = super(Component, self)._get_model_refs()
        if self.host_ref:
            modelrefs.add(self.host_ref)
        return modelrefs
        
        
class NamespaceSpecMeta(type):
    def __new__(cls, name, bases, attr_dict):
        if _common_vars not in attr_dict:
            attr_dict[_common_vars] = []
        newbie = super(NamespaceSpecMeta, cls).__new__(cls, name, bases, attr_dict)
        process_modifiers(newbie)
        return newbie
    

class NamespaceSpec(VariableContainer):
    __metaclass__ = NamespaceSpecMeta
    def __init__(self):
        super(NamespaceSpec, self).__init__()
        
        components = set()
        clone_map = {}
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, Component):
                components.add((k, v))
        next_ply = set([(k,c) for k, c in components if c.parent_container is None])
        for k, c in next_ply:
            clone = c.clone()
            clone_map[c] = (k, clone)
            clone._set_parent(self)
        components -= next_ply
        while components:
            next_ply = set([(k,c) for k, c in components if c.parent_container in clone_map])
            if not next_ply:
                raise NamespaceException("No components can be found that have parents which were previously cloned")
            for k, c in next_ply:
                clone = c.clone()
                clone_map[c] = (k, clone)
                clone._set_parent(clone_map[c.parent_container][1])
            components -= next_ply
        self.components = {}
        for _, (key, clone) in clone_map.items():
            self.components[key] = clone
            setattr(self, key, clone)
        
        self.add_variable(*self.__class__.__dict__[_common_vars])
        self.infra_instance = None
        
    def __new__(cls, *args, **kwargs):
        inst = super(NamespaceSpec, cls).__new__(cls, *args, **kwargs)
        return inst
    
    def _get_model_refs(self):
        modelrefs = super(NamespaceSpec, self)._get_model_refs()
        for c in self.components.values():
            modelrefs |= c._get_model_refs()
        return modelrefs
    
    def get_components(self):
        return dict(self.components)
    
    def get_infra(self):
        return self.infra_instance
    
    def compute_provisioning_for_environ(self, infra_instance, exclude_refs=None):
        if exclude_refs is None:
            exclude_refs = set()
        exclude_refs = set([infra_instance.get_inst_ref(ref) for ref in exclude_refs])
        self.infra_instance = infra_instance
        self.infra_instance.compute_provisioning_from_refs(self._get_model_refs(), exclude_refs)
        return set([p for p in self.infra_instance.components()
                    if AbstractModelReference.find_ref_for_obj(p) not in exclude_refs])
#         return self.infra_instance.provisionables()
        
    def add_components(self, **kwargs):
        for k, v in kwargs.items():
            if not isinstance(v, Component):
                raise NamespaceException("%s is not a kind of component" % str(v))
            clone = v.clone()
            self.components[k] = clone
            self.__dict__[k] = clone
        return self
