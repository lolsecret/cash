from decimal import Decimal
from uuid import uuid4
from django.core.validators import MinValueValidator

from tinymce import models as tinymce_models
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField
from mptt.models import MPTTModel, TreeForeignKey

from apps.core import NotificationTextType


class UUIDModel(models.Model):
    class Meta:
        abstract = True

    uuid = models.UUIDField("Идентификатор", default=uuid4, unique=True, editable=False)


class CharIDModel(models.Model):
    class Meta:
        abstract = True

    id = models.CharField("Уникальный код", max_length=32, primary_key=True)


class City(models.Model):
    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ("name",)

    name = models.CharField(max_length=255, verbose_name='Название')
    code = models.CharField("Код", max_length=20, blank=True, help_text="Код из системы доставки MyKhat")
    branch_code = models.CharField(
        "Код филиала",
        max_length=2,
        null=True,
        help_text="""Код филиала используется для формирования номера договора для рассрочки"""
    )

    def __str__(self):
        return self.name


class PersonNameMixin(models.Model):
    first_name = models.CharField("Имя", max_length=255, null=True, blank=True)
    last_name = models.CharField("Фамилия", max_length=255, null=True, blank=True)
    middle_name = models.CharField("Отчество", max_length=255, null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def full_name(self):
        return " ".join(filter(None, [self.last_name, self.first_name, self.middle_name]))


class ContactMixin(models.Model):
    mobile_phone = PhoneNumberField("Мобильный телефон", blank=True, null=True)
    home_phone = PhoneNumberField("Домашний телефон", blank=True, null=True)
    work_phone = PhoneNumberField("Рабочий телефон", blank=True, null=True)
    email = models.EmailField("Email", blank=True, null=True)

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    class Meta:
        abstract = True

    country = models.CharField('Страна', max_length=255, null=True, blank=True)
    region = models.CharField('Регион', max_length=255, null=True, blank=True)
    city = models.CharField('Город', max_length=255, null=True, blank=True)
    district = models.CharField('Район', max_length=255, null=True, blank=True)
    street = models.CharField('Улица', max_length=255, null=True, blank=True)
    building = models.CharField('Дом / здание', max_length=100, null=True, blank=True)
    corpus = models.CharField('Корпус', max_length=100, null=True, blank=True)
    flat = models.CharField('Квартира', max_length=50, null=True, blank=True)

    @property
    def full_address(self) -> str:
        data = (
            self.country,
            self.region,
            self.city,
            self.district,
            self.street,
            self.building,
            self.corpus,
            self.flat,
        )
        return ", ".join([field.title() for field in data if field])


class Partner(TimeStampedModel):
    class Meta:
        verbose_name = _("Партнёр")
        verbose_name_plural = _("Партнёры")

    name = models.CharField("Наименование", max_length=255)

    def __str__(self):
        return self.name


class Branch(MPTTModel):
    class Meta:
        verbose_name = 'Филиал'
        verbose_name_plural = 'Филиалы'

    name = models.CharField(max_length=255, verbose_name='Название')
    index = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name='Адрес')
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children',
        db_index=True,
        verbose_name='Родительский элемент'
    )

    def __str__(self):
        return self.name


class Bank(models.Model):
    class Meta:
        verbose_name = 'Банк'
        verbose_name_plural = 'Банки Казахстана'

    name = models.CharField(_('Название'), max_length=255)
    bic = models.CharField(_("Bank Identifier Code"), max_length=255, null=True)

    def __str__(self):
        return self.name


class PrintForm(TimeStampedModel):
    class Meta:
        verbose_name = "Печатная форма"
        verbose_name_plural = "Печатные формы"

    name = models.CharField("Название", max_length=255)
    slug = models.SlugField(
        "Путь",
        unique=True,
        allow_unicode=True,
        help_text="""Путь который будет добавляться в конце url: /print/{uuid}/{путь}"""
    )
    template = models.TextField("Шаблон")
    is_active = models.BooleanField("Активен", default=True)

    def __str__(self):
        return self.name


class CreditIssuancePlan(models.Model):
    issuance_plan = models.DecimalField(
        "План выдачи",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
    )
    year = models.PositiveSmallIntegerField('Год')
    month = models.PositiveSmallIntegerField('Месяц')

    class Meta:
        verbose_name = "План выдачи на месяц"
        verbose_name_plural = "Настройки: План выдачи на месяц"
        unique_together = ('year', 'month')
        ordering = 'year', 'month'

    def __str__(self):
        return f"{self._meta.verbose_name} {self.issuance_plan}"


class Document(TimeStampedModel):
    title = models.CharField("Наименование", max_length=255)
    document = models.FileField("Файл", upload_to="manager_documents/")

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"

    def __str__(self):
        return self.title


class FAQ(TimeStampedModel):
    question = models.CharField("Вопрос", max_length=255)
    answer = tinymce_models.HTMLField("Ответ")
    sort = models.SmallIntegerField()

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"

    def __str__(self):
        return self.question


class NotificationText(TimeStampedModel):
    code = models.CharField("Код уведомления", max_length=25, null=True, blank=True)
    error_field = models.CharField("Короткое название поля ошибки", max_length=25, null=True, blank=True)
    text = models.TextField("Описание уведомления", null=True, blank=True)
    type = models.CharField("Тип уведомления", max_length=25, choices=NotificationTextType.choices)

    class Meta:
        verbose_name = "Текст уведомлений"
        verbose_name_plural = "Настройки: Текста уведомлений"

    def __str__(self):
        return f'<Текст уведомлений: {self.pk}. {self.code}>'
