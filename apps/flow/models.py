import logging
from typing import List, Type, Optional, Dict, Any, TYPE_CHECKING, Union
import importlib

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import JSONField
from django.forms import model_to_dict
from django.utils.translation import gettext_lazy as _, gettext
from django_extensions.db.models import TimeStampedModel
from solo.models import SingletonModel

from apps.credits import CreditStatus
from . import ServiceStatus, ServicePurposes
from .managers import ServiceReasonQuerySet, HistoryQuerySet, StatusTriggerQuerySet

if TYPE_CHECKING:
    from apps.credits.models import CreditApplication, Lead

logger = logging.getLogger(__name__)


class ExternalService(models.Model):
    class Meta:
        verbose_name = _("Внешний сервис")
        verbose_name_plural = _("Внешние сервисы")
        ordering = ('name',)

    name = models.CharField('Название', max_length=100)
    service_class = models.CharField('Класс сервиса', max_length=255, null=True)
    address = models.CharField(
        _("Адрес"),
        max_length=255,
        null=True,
        blank=True,
    )
    username = models.CharField('Имя пользователя', max_length=255, null=True, blank=True)
    password = models.CharField('Пароль', max_length=255, null=True, blank=True)
    token = models.CharField('Api token', max_length=255, null=True, blank=True)

    timeout = models.PositiveIntegerField('Таймаут (сек.)', null=True, blank=True)
    cache_lifetime = models.PositiveIntegerField('Время жизни кэша (дней)', null=True)
    params = JSONField('Параметры', null=True)

    is_active = models.BooleanField('Активен', default=False)

    def __str__(self) -> str:
        status = "активен" if self.is_active else "неактивен"
        return f"{self.name} ({status})"

    def get_class(self, application, cached_data=None, **kwargs):
        module_name, class_name = self.service_class.rsplit(".", 1)
        service_class = getattr(importlib.import_module(module_name), class_name)
        return service_class(instance=application, service_model=self, cached_data=cached_data, **kwargs)

    def run_service(self, obj: models.Model, cached_data=None, kwargs: Optional[Dict[str, Any]] = None):
        _kwargs = kwargs or {}
        _kwargs.update(self.get_params(obj))
        service_class = self.get_class(obj, cached_data=cached_data, **_kwargs)
        return service_class.run_service()

    def get_params(self, obj: models.Model) -> dict:
        data = model_to_dict(obj)
        params = self.params or {}

        if isinstance(self.params, dict):
            for key, value in self.params.items():
                try:
                    params[key] = data[value]
                except KeyError:
                    continue

        if self.username or self.password:
            params['username'] = self.username
            params['password'] = self.password

        return params

    @classmethod
    def by_class(cls, service_class: Type) -> 'ExternalService':
        """Находим модель через ServiceClass"""
        service_class_name = f"{service_class.__module__}.{service_class.__name__}"
        external_service = cls.objects.filter(
            service_class=service_class_name,
            is_active=True,
        ).first()

        if not external_service:
            logger.error("class %s does not exists", service_class_name)
            raise Exception("class %s does not exists" % service_class_name)

        return external_service

    def run_in_background(self, obj):
        from .tasks import run_service_background
        run_service_background.delay(self.id, obj.id, obj._meta.label)


class Pipeline(models.Model):
    SUCCESS_STATUSES = (
        ServiceStatus.CHECKED,
        ServiceStatus.WAS_REQUEST,
    )

    class Meta:
        verbose_name = _("Конвейер")
        verbose_name_plural = _("Настройки: Список конвейеров")

    name = models.CharField("Наименование", max_length=255)
    is_active = models.BooleanField("Активен", default=False)
    background = models.BooleanField("Фоновый режим", default=False)

    def __str__(self):
        return self.name

    def chain_active_jobs(self) -> List[Type['Job']]:
        return self.jobs.filter(is_active=True).order_by('priority')

    def run_for(self, credit: 'CreditApplication'):
        if self.background:
            self.run_in_background(credit)
        else:
            self.run(credit)

    def run(self, credit: 'CreditApplication'):
        """выполнение"""
        # Flow(self).run(credit)

    def run_in_background(self, credit: 'CreditApplication'):
        """выполнение в фоне"""
        # FlowBackground(self).run(credit)

    def active_jobs(self) -> List[Type['Job']]:
        return self.jobs.filter(is_active=True).order_by('priority')

    def retry_jobs(self, instance: Union['Lead', 'CreditApplication']) -> List[Type['Job']]:
        return self.active_jobs().exclude(
            service_id__in=self.successfully_completed_jobs(instance)
        )

    def successfully_completed_jobs(self, instance: Union['Lead', 'CreditApplication']) -> List[Type['Job']]:
        content_type = ContentType.objects.get_for_model(instance)
        return self.services_history.filter(
            content_type=content_type,
            object_id=instance.id,
            status__in=self.SUCCESS_STATUSES
        ).values_list("service_id", flat=True)


class Job(models.Model):
    class Meta:
        verbose_name = _("Задача")
        verbose_name_plural = _("Задачи")

    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='jobs'
    )
    service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name='Сервис'
    )
    priority = models.PositiveSmallIntegerField('Порядок выполнения', default=0)
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    raise_exception = models.BooleanField("Вызвать исключение", default=False)
    # objects = JobQueryset()

    def __str__(self):
        return self.service.name


class ServiceHistory(TimeStampedModel):
    class Meta:
        verbose_name = _("История запросов")
        verbose_name_plural = _("Сервисы: История запросов")
        indexes = [
            models.Index(fields=['created_at']),
        ]
        ordering = ("-pk",)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Сервис")
    )
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        blank=True, null=True,
        verbose_name=_("Конвейер"),
        related_name='services_history'
    )
    reference_id = models.CharField(max_length=255, null=True, blank=True)
    data = JSONField(_("Данные"), null=True, blank=True)
    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=ServiceStatus.choices,
        default=ServiceStatus.NO_REQUEST
    )
    runtime = models.DecimalField(_("Выполнено за(сек)"), max_digits=6, decimal_places=3, default=0.0)
    created_at = models.DateTimeField(_("Дата запроса"), auto_now_add=True, null=True, db_index=True)
    request_id = models.CharField(_('Request-id'), max_length=32, blank=True, null=True)

    objects = HistoryQuerySet.as_manager()

    def __str__(self):
        return self.service.__str__()

    @property
    def response(self):
        if hasattr(self, "service_response"):
            return self.service_response
        return None

    def create_log(self, verbose: dict):
        if isinstance(verbose, dict):
            url = verbose.pop('url', None)
            method = verbose.pop('method', None)
            req = verbose.pop('request', None)
            res = verbose.pop('response', None)
            return ServiceResponse.objects.create(
                history=self,
                url=url,
                method=method,
                request=req,
                response=res
            )

    def set_response(self, **kwargs) -> 'ServiceResponse':
        return ServiceResponse.objects.create(
            history=self,
            **kwargs
        )


class ServiceResponse(TimeStampedModel):
    class Meta:
        verbose_name = _("Лог сервиса")
        verbose_name_plural = _("Логи сервисов")

    history = models.OneToOneField(
        ServiceHistory,
        on_delete=models.CASCADE,
        related_name="service_response",
        verbose_name="Лог"
    )
    url = models.CharField("Ссылка", max_length=255, null=True, blank=True)
    method = models.CharField("Метод", max_length=100, null=True, blank=True)
    request = models.TextField("Параметры запроса", null=True, blank=True)
    response = models.TextField("Ответ от сервиса", null=True, blank=True)

    def __str__(self):
        return f"Response log for {self.history}"


class ServiceReason(models.Model):
    class Meta:
        verbose_name = _("Негативный статус")
        verbose_name_plural = _("Настройки: Негативные статусы")
        ordering = ("service", "key")

    service = models.ForeignKey(
        ExternalService,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Сервис"
    )
    key = models.CharField("Ключ", max_length=255, unique=True)
    message = models.CharField("Отказное сообщение", max_length=255)
    is_active = models.BooleanField("Активен", default=True)

    objects = ServiceReasonQuerySet.as_manager()

    def __str__(self):
        return f"{self.key}: {self.message}"


class StatusTrigger(models.Model):
    class Meta:
        verbose_name = _("Триггер смены статуса")
        verbose_name_plural = _("Настройки: Триггеры")
        unique_together = ('status', 'priority')

    name = models.CharField(max_length=255, verbose_name='Название')
    product = models.ForeignKey(
        'credits.Product',  # noqa
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name='Программа'
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=CreditStatus.choices,
    )
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Конвейер"
    )
    priority = models.PositiveIntegerField(verbose_name='Приоритет', default=0)
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    objects = StatusTriggerQuerySet.as_manager()

    def __str__(self) -> str:
        return self.name

    @classmethod
    def run(cls, *, status: CreditStatus, credit: 'CreditApplication'):
        from .services import Flow
        logger.info("trigger status run")
        for process in cls.objects.find(status=status):
            if process.pipeline:
                try:
                    Flow(process.pipeline, credit).run()

                except Exception as exc:
                    logger.error("Flow.run except %s", exc)


class BiometricConfiguration(SingletonModel):
    service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name='Сервис'
    )

    class Meta:
        verbose_name = _("Biometric Configuration")
        verbose_name_plural = _("Biometric Configuration")

    def __str__(self):
        return gettext("Biometric Configuration")
