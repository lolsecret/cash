from django.contrib.auth import get_user_model
from django.db import models, connection
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType

from django_extensions.db.models import TimeStampedModel

from apps.core.models import PersonNameMixin
from apps.people.validators import IinValidator

from . import BlackListReason, BlackListSource, AdminHistoryAction

User = get_user_model()


class BlackListMember(PersonNameMixin, TimeStampedModel):
    class Meta:
        verbose_name = _("Член чёрного списка")
        verbose_name_plural = _("Члены чёрного списка")

    iin = models.CharField(
        "ИИН",
        max_length=12,
        unique=True,
        blank=True,
        null=True,
        validators=[IinValidator()],
    )
    birthday = models.DateField("Дата рождения", null=True, blank=True)
    reason = models.CharField(
        "Причина включения в список",
        max_length=20,
        choices=BlackListReason.choices,
        default=BlackListReason.AML,
    )
    note = models.CharField("Примечание", max_length=255, blank=True, null=True)
    manager = models.ForeignKey(
        User, verbose_name="Добавил в список", null=True, on_delete=models.SET_NULL
    )
    source = models.PositiveSmallIntegerField(
        choices=BlackListSource.choices, default=BlackListSource.CUSTOM, editable=False
    )


class Region(models.Model):
    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ("name",)

    name = models.CharField(max_length=255, verbose_name='Название')
    code = models.CharField("Код", max_length=20)
    region_id = models.IntegerField("Id региона")
    is_active = models.BooleanField("Активно")

    def __str__(self):
        return f"{self.name} ({self.code})"


class IndividualProprietorList(models.Model):
    class Meta:
        verbose_name = 'Индивидуальный Предприниматель'
        verbose_name_plural = 'Список Индивидуальных Предпринимателей'
        ordering = ('iin',)

    iin = models.CharField('ИИН', max_length=15, primary_key=True)
    name = models.CharField('Наименование ИП', max_length=500, null=True)
    full_name = models.CharField('ФИО руководителя', max_length=500, null=True)
    kato_code = models.CharField('КАТО', max_length=255, null=True, blank=True)
    date_reg = models.DateField('Дата регистрации', null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Регион")
    created_at = models.DateTimeField("Синхронизировано", auto_now_add=True, null=True)

    def __str__(self):
        return " ".join([self.iin, self.full_name])

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))  # noqa


class AdminHistory(TimeStampedModel):
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Автор изменения",
    )
    action_type = models.CharField(
        'Тип Действия',
        max_length=20,
        choices=AdminHistoryAction.choices,
        default=AdminHistoryAction.CHANGE
    )
    action_description = models.CharField("Описание действия", max_length=255, null=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        blank=True, null=True,
    )
    object_id = models.PositiveIntegerField(null=True)

    field_name = models.CharField("Название поля", max_length=255, null=True, blank=True)
    field_before = models.CharField("Поле до изменения", max_length=255, null=True, blank=True)
    field_after = models.CharField("Поле после изменения", max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'История изменений'
        verbose_name_plural = 'Список историй изменений'

    def __str__(self):
        return f'{self.get_action_type_display()} {self.field_name} в {self.content_type}'
