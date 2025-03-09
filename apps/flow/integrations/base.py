import time
from typing import Optional, Type, Dict, Union, Any
import uuid
import logging
from copy import deepcopy

from django.db.models import Model

from apps.core.utils import generate_uid
from apps.flow.base import ServiceInterface
from apps.flow.models import ExternalService
from apps.flow import ServiceStatus
from apps.flow.services.history import BaseHistory
from .exceptions import (
    ServiceErrorException,
    RejectRequestException,
    ServiceUnavailable,
)

logger = logging.getLogger(__name__)


class Register:
    _registry: Dict[str, Dict[str, Union[Type, str]]] = {}

    @staticmethod
    def registered_classes():
        return Register._registry

    @classmethod
    def get_class(cls, name):
        assert name in cls._registry, (
            f"{name} has not in {cls._registry}"
        )
        return cls._registry[name]['class']

    @classmethod
    def get_descriptions(cls):
        return list((k, v["description"]) for k, v in cls._registry.items())

    @classmethod
    def get_for_class(cls, _class) -> str:
        """Возвращает путь к сервис классу ввиде str"""
        for service_name, registry in cls._registry.items():
            if registry['class'] is _class:
                return service_name


class BaseService(Register, ServiceInterface, BaseHistory):
    save_serializer: Optional[Type] = None
    save_response = True
    success_status = ServiceStatus.WAS_REQUEST

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        service_class: str = getattr(cls, "name", f"{cls.__module__}.{cls.__name__}")
        description = cls.__doc__ or getattr(cls, 'description', '')

        parent_class_found = BaseService.get_for_class(cls.__bases__[0])
        if parent_class_found:
            cls._registry.pop(parent_class_found)

        cls._registry.update({
            service_class: {
                "class": cls,
                "description": f"{cls.__name__}: {description}"
            }
        })

    def __init__(self, instance, service_model: Model, cached_data=None, get_cache=True, request_id=None, **kwargs):
        self.instance = instance
        self.service: Union['ExternalService', Model] = service_model
        self.cached_data = cached_data
        self.kwargs = kwargs
        self.status = ServiceStatus.NO_REQUEST  # noqa
        self.get_cache = kwargs.get('get_cache', True)
        self.pipeline_id = kwargs.get('pipeline_id', None)
        self.uid = kwargs.get('uid') or generate_uid()
        self.request_id = request_id or uuid.uuid4().hex

    def get_instance(self):
        return self.instance

    def conditions(self):
        return True

    def prepare(self):
        pass

    def post_run(self):
        pass

    def run(self):
        raise NotImplementedError

    def check_rule(self, data):
        pass

    @property
    def log_iin(self):  # noqa
        """В дочерних классах нужно определить, где модем получить значение ИИН
        Пример:
        return self.instance.borrower.iin
        """
        return ''

    def find_cached_data(self):
        from apps.flow.models import ServiceHistory
        reference = self.instance.get_reference()
        if reference and self.service.cache_lifetime:
            history = ServiceHistory.objects.find_cached_data(service=self.service, reference=reference).first()
            if history:
                logger.info("data from cache %s", history)
            self.cached_data = history.data if history else None

    def run_service(self) -> Any:
        response_data = None
        if self.conditions():
            self.prepare()
            self.find_cached_data()
            try:
                if bool(self.cached_data) and self.get_cache:
                    logger.info("cache_data exists service=%s instance=%s", self.service, self.instance)
                    response_data = self.cached_data
                    self.status = ServiceStatus.CACHED_REQUEST
                    logger.info("request from cached_data")

                else:
                    start_time = time.perf_counter()
                    logger.info("%s request run instance=%s", self.__class__.__name__, self.instance)
                    response_data = self.run()
                    self.status = self.success_status
                    logger.info("%s request from source", self.__class__.__name__, extra={'instance': self.instance})


                self.data = deepcopy(response_data)
                self.save(response_data)

            except ServiceUnavailable as exc:
                self.status = ServiceStatus.SERVICE_UNAVAILABLE
                raise ServiceUnavailable(exc)

            except Exception as exc:
                logger.error('run_service: %s', exc)
                logger.exception(exc)
                self.status = ServiceStatus.REQUEST_ERROR
                # raise ServiceErrorException(exc)

            else:
                if self.status != ServiceStatus.CACHED_REQUEST:
                    self.status = ServiceStatus.WAS_REQUEST

                try:
                    logger.info("request post_run")
                    self.post_run()

                except Exception as exc:
                    logger.error('Exception.post_run: %s', exc)

            finally:
                logger.info("request log_save")
                self.log_save()

            # Проверки правил
            self.check_rule(response_data)

        return response_data

    def to_internal_value(self, response) -> Any:  # noqa
        return response.json()

    def prepared_data(self, data: dict) -> dict:  # noqa
        return data

    def save(self, prepared_data):
        if self.save_serializer and isinstance(prepared_data, dict):
            instance = self.get_instance()

            if instance and prepared_data:
                prepared_data = self.prepared_data(prepared_data)
                serializer = self.save_serializer(instance=instance, data=prepared_data)
                serializer.is_valid(raise_exception=True)
                serializer.save()


class InternalCheckRuleService(BaseService):  # noqa
    save_response = False
    success_status = ServiceStatus.CHECKED

    def check_rule(self, data=None):
        pass

    def save(self, prepared_data=None):
        return super(InternalCheckRuleService, self).save(prepared_data)

    def run_service(self) -> Any:
        if self.conditions():
            self.prepare()
            try:
                self.run()
                self.status = self.success_status

            except Exception as exc:
                logger.exception(exc)

            else:
                self.log_save()

        self.check_rule()
        return
