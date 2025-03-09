from abc import ABC, ABCMeta, abstractmethod
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation


class AbstractModelMeta(ABCMeta, type(models.Model)):
    pass


class ServiceHistoryMixin(models.Model, metaclass=AbstractModelMeta):
    history = GenericRelation('flow.ServiceHistory')

    class Meta:
        abstract = True

    def set_response(self, **kwargs):
        pass

    @abstractmethod
    def get_reference(self) -> str:
        raise NotImplementedError('Необходимо определить get_reference в %s.' % self.__class__.__name__)
