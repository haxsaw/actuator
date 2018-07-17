import collections
import inspect
import six


from actuator import ModelBaseMeta, ModelReference, InfraModel, InfraModelMeta, ActuatorException, NamespaceModel, \
    NamespaceModelMeta, ConfigModel, ConfigModelMeta, AbstractModelingEntity, process_modifiers, _Nexus, ModelComponent, \
    ModelBase, VariableContainer, ModelInstanceReference, _common_vars


class ServiceMeta(ModelBaseMeta):
    model_ref_class = ModelReference

    def __new__(mcs, name, bases, attr_dict):
        if "infra" in attr_dict and not isinstance(attr_dict["infra"], (InfraModel, InfraModelMeta)):
            raise ActuatorException("The 'infra' attribute is not a kind of InfraModel class")
        if "namespace" in attr_dict and not isinstance(attr_dict["namespace"], (NamespaceModel, NamespaceModelMeta)):
            raise ActuatorException("The 'namespace' attribute is not a kind of NamespaceModel class")
        if "config" in attr_dict and not isinstance(attr_dict["config"], (ConfigModel, ConfigModelMeta)):
            raise ActuatorException("The 'config' attribute is not a kind of ConfigModel class")

        newbie = super(ServiceMeta, mcs).__new__(mcs, name, bases, attr_dict,
                                                 as_component=(AbstractModelingEntity,
                                                               ModelBaseMeta))
        process_modifiers(newbie)
        _Nexus._add_model_desc("svc", newbie)
        return newbie


_default_model_args = (("_UNNAMED_",), {})


class Service(six.with_metaclass(ServiceMeta, ModelComponent, ModelBase, VariableContainer)):
    ref_class = ModelInstanceReference
    infra = InfraModel
    namespace = NamespaceModel
    config = ConfigModel

    def __init__(self, name, infra=None, infra_args=_default_model_args,
                 namespace=None, namespace_args=_default_model_args,
                 config=None, config_args=_default_model_args, services=None, **kwargs):
        """
        Creates a new instance of a service model
        :param name: string; name of the service model
        :param infra: optional; if specified, an instance of some kind of InfraModel. Takes precedence
            over infra_args.
        :param infra_args: optional; if specified, a sequence of a sequence and a dict, to be
            used to create a new instance of the infra model like ModelClass(*infra_args[0], **infra_args[1]).
            Ignored in the 'infra' parameter has been supplied. If used, self.infra must be a subclass
            of InfraModel.
        :param namespace: optional; if specified, and instance of some kind of NamespaceModel. Takes
            precedence over namespace_args
        :param namespace_args: optional; if specified, a sequence of a sequence and a dict, to be used
            to create a new instance of the namespace model like ModelClass(*namespace_args[0], **namespace_args[1]).
            Ignored if the namespace parameter is specified. If used, self.namespace must be a subclass
            of NamespaceModel.
        :param config: optional; if specified, an instance of a ConfigModel. Takes precedence over config_args.
        :param config_args: optional; if specified, a sequence of a sequence and a dict, to be used
            to create a new instance of the config model like ModelClass(*config_args[0], **config_args[1]).
            Ignored if the config parameter is specified. If used, self.config must be a subvlass
            of ConfigModel.
        :param services: optional; a dict whose keys are names of services and whose values can
            be one of two things: they can be a Service instance, or they can be a sequence of
            [(), {}] parameters that can be used to instantiate a service. In this latter
            case, the Service that is "self" must have an attribute of the same name that is
            a Service model class to which these parameters will be applied to create a service
            instance. The new instance will be added as a new attribute of self with the name
            of the key in the services dict.
        """
        super(Service, self).__init__(name, **kwargs)

        self.service_names = set()
        self.services = {} if services is None else dict(services)

        self._infra = infra
        self._infra_args = infra_args
        if infra is None:
            if inspect.isclass(self.infra.value()) and issubclass(self.infra.value(), InfraModel):
                try:
                    infra = self.infra.value()(*infra_args[0], **infra_args[1])
                except Exception as e:
                    raise ActuatorException("Unable to create an instance of infra {} with pargs {} and kwargs {}: {}".
                                            format(self.infra.value().__name__,
                                                   infra_args[0], infra_args[1], str(e)))
            elif isinstance(self.infra.value(), InfraModel):
                infra = self.infra.clone()
            else:
                raise ActuatorException("No way to create any infra model, not even a stub")
        self.infra = infra

        self._namespace = namespace
        self._namespace_args = namespace_args
        if namespace is None:
            if inspect.isclass(self.namespace.value()) and issubclass(self.namespace.value(), NamespaceModel):
                try:
                    namespace = self.namespace.value()(*namespace_args[0], **namespace_args[1])
                except Exception as e:
                    raise ActuatorException("Unable to create an instance of namespace {} with pargs {} and "
                                            "kwargs {}: {}".format(self.namespace.value().__name__,
                                                                   namespace_args[0], namespace_args[1],
                                                                   str(e)))
            elif isinstance(self.namespace.value(), NamespaceModel):
                namespace = self.namespace.clone()
            else:
                raise ActuatorException("No way to create any namespace model, not even a stub")
        self.namespace = namespace

        self._config = config
        self._config_args = config_args
        _ = self.config
        if config is None:
            if inspect.isclass(self.config.value()) and issubclass(self.config.value(), ConfigModel):
                try:
                    config = self.config.value()(*config_args[0], **config_args[1])
                except Exception as e:
                    raise ActuatorException("Unable to create an instance of config {} with pargs {} and "
                                            "kwargs {}: {}".format(self.config.value().__name__,
                                                                   config_args[0], config_args[1],
                                                                   str(e)))
            elif isinstance(self.config.value(), ConfigModel):
                config = self.config.clone()
            else:
                raise ActuatorException("No way to create any config model, not even a stub")
        self.config = config

        self.infra.nexus.merge_from(self.nexus)
        self.namespace.set_infra_model(self.infra.value())
        self.config.set_namespace(self.namespace.value())
        self.nexus = self.config.nexus.value()

        # now, users can do three different things with services: they can spec a
        # service class as an attribute and provide the init params to this method,
        # they can spec the class as an attribute but provide a service instance to
        # this method, or they can just supply the instance and have no attribute.
        # where we want to get to is a situation where we can do the right things
        # in both cloning and persisting/reanimating circumstances, so we need to
        # process these cases carefully. What we'd like to eventually have is the
        # services dict only have non-service values in it
        #
        # first, we'll look for class attributes that are either service classes or instances
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, (Service, ServiceMeta)):
                if isinstance(v, ServiceMeta):
                    # then we have an inner service to instantiate; look for the args or an inst
                    if k not in self.services:
                        raise ActuatorException("No init args for service '{}'".format(k))
                    args = self.services[k]
                    if isinstance(args, Service):
                        newsvc = args
                        del self.services[k]  # this is a service which we
                    elif isinstance(args, collections.Sequence):
                        newsvc = v(*args[0], **args[1])
                    else:
                        raise ActuatorException("services entry for service '{}' isn't an instance "
                                                "of a kind of a Service or sequence of args".format(k))
                else:  # must be a Service instance; clone it
                    newsvc = v.clone()
                setattr(self, k, newsvc)
                self.service_names.add(k)
                newsvc.nexus.set_parent(self.nexus)
        # next, see if there are any services remaining the services param that we haven't
        # taken care of yet
        for k, v in self.services.items():
            if k in self.service_names:
                continue  # already covered
            if isinstance(v, Service):
                # something someone just decided to toss in here
                setattr(self, k, v)
                self.service_names.add(k)
            else:
                # ruh-roh; this shouldn't happen. if this is a sequence, it means these are
                # args for a service class, but we should have found those in the previous
                # for loop, so we have args but no class to apply them to. if they aren't
                # a sequence, then we don't know what to do with them anyway
                raise ActuatorException("services arg with key {} and value {} doesn't "
                                        "have a corresponding service model class on this "
                                        "service instance".format(k, str(v)))

        for k, v in self.__dict__.items():
            if isinstance(v, VariableContainer):
                v._set_parent(self)

        if _common_vars in self.__class__.__dict__:
            self.add_variable(*self.__class__.__dict__[_common_vars])

    def _comp_source(self):
        d = {}
        for a in ("infra", "namespace", "config"):
            m = getattr(self, a).value()
            d[a] = m
        for sn in self.services:
            svc = getattr(self, sn).value()
            d[sn] = svc
        return d

    def get_init_args(self):
        return ((self.name,),
                {"infra": (self._infra.value()
                           if isinstance(self._infra, ModelInstanceReference)
                           else self._infra),
                 "infra_args": self._infra_args,
                 "namespace": (self._namespace.value()
                               if isinstance(self._namespace, ModelInstanceReference)
                               else self._namespace),
                 "namespace_args": self._namespace_args,
                 "config": (self._config.value()
                            if isinstance(self._config, ModelInstanceReference)
                            else self._config),
                 "services": self.services})

    def finalize_reanimate(self):
        self.service_names = set(self.service_names)

    def _fix_arguments(self):
        super(Service, self)._fix_arguments()
        comps = self.namespace.compute_provisioning_for_environ(self.infra.value())
        for comp in comps:
            comp.fix_arguments()
        for k in self.service_names:
            v = getattr(self, k).value()
            v.fix_arguments()
            v.namespace.compute_provisioning_for_environ(v.infra.value())
        self.config.fix_arguments()

    def _get_attrs_dict(self):
        d = super(Service, self)._get_attrs_dict()
        d.update({"name": self.name,
                  "infra": self.infra.value(),
                  "_infra_args": self._infra_args,
                  "namespace": self.namespace.value(),
                  "_namespace_args": self._namespace_args,
                  "config": self.config.value(),
                  "service_names": list(self.service_names),
                  "services": self.services,
                  "nexus": self.nexus})
        # now add the actual services themselves
        for k in self.service_names:
            d[k] = getattr(self, k).value()
        return d

    def _find_persistables(self):
        for p in super(Service, self)._find_persistables():
            yield p

        for p in [self.infra, self._infra, self.namespace, self._namespace,
                  self.config, self._config, self.nexus]:
            if p is not None and not isinstance(p, collections.Iterable):
                for q in p.find_persistables():
                    yield q

        for k in self.service_names:
            p = getattr(self, k).value()
            yield p
            for q in p.find_persistables():
                yield q