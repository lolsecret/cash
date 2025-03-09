from uuid import uuid4

import pyotp
from phonenumber_field.modelfields import PhoneNumberField
from phonenumbers import PhoneNumber

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel

from apps.core.models import CharIDModel
from .manager import OTPQueryset


class SMSType(models.Model):
    class Meta:
        verbose_name = "Тип сообщения"
        verbose_name_plural = "Типы сообщений"

    id = models.CharField("Уникальный код", max_length=32, validators=[MinLengthValidator(2)], primary_key=True)
    name = models.CharField("Наименование", max_length=255)

    def __str__(self):
        return self.name


class SMSTemplate(models.Model):
    class Meta:
        verbose_name = "Шаблон СМС"
        verbose_name_plural = "Шаблоны СМС"

    name = models.ForeignKey(
        SMSType,
        on_delete=models.CASCADE,
    )
    content = models.TextField("Содержимое", help_text="""Используется django.template""")


class SMSMessage(TimeStampedModel):
    class Meta:
        verbose_name = "SMS сообщение"
        verbose_name_plural = "SMS сообщения"

    uuid = models.UUIDField("Идентификатор", default=uuid4, unique=True, editable=False)
    recipients = models.CharField("Получатели", max_length=255, editable=False)
    content = models.TextField("Содержимое", editable=False)
    external_id = models.CharField("Идентификатор в СМС сервисе", max_length=100, null=True, blank=True)
    error_code = models.IntegerField("Код ошибки", null=True, editable=False)
    error_description = models.CharField(
        "Описание ошибки", max_length=255, null=True, editable=False
    )


class OTP(TimeStampedModel):
    class Meta:
        verbose_name = "Одноразовый пароль"
        verbose_name_plural = "Одноразовые пароли"
        unique_together = ("code", "mobile_phone")

    code = models.CharField("OTP", max_length=12, db_index=True, editable=False)
    verified = models.BooleanField("Подтверждён", default=False, editable=False)
    mobile_phone = PhoneNumberField("Мобильный телефон", editable=False)
    failed_verification_attempts = models.PositiveSmallIntegerField("Неудачное количество попыток", default=0)

    objects = OTPQueryset.as_manager()

    @classmethod
    def generate(cls, mobile_phone: PhoneNumber):
        with transaction.atomic():
            instance = cls.objects.create()

            hotp = pyotp.HOTP(settings.HOTP_KEY, digits=settings.OTP_LENGTH)

            instance.code = hotp.at(instance.pk)
            instance.mobile_phone = mobile_phone
            instance.save()
        return instance.code

    def update_failed_verification_attempts_amount(self):
        self.failed_verification_attempts += 1
        self.save(update_fields=['failed_verification_attempts'])
