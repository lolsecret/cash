from typing import Optional
from datetime import date
from dateutil.relativedelta import relativedelta

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import (
    PersonNameMixin,
    ContactMixin,
    AddressMixin,
    Bank,
)

from . import (
    Gender,
    MaritalStatus,
    RelationshipType,
)
from .managers import PersonQueryset, PersonFromIinManager
from .validators import IinValidator


class Address(AddressMixin):
    class Meta:
        verbose_name = _('Адрес')
        verbose_name_plural = _('Адреса')

    def __str__(self) -> str:
        return self.full_address


class PersonContact(PersonNameMixin, ContactMixin):
    class Meta:
        verbose_name = "Контактная информация"
        verbose_name_plural = "Контактная информация"

    def __str__(self):
        return " ".join([self.full_name, self.mobile_phone.__str__()])


class Person(models.Model):
    iin = models.CharField(
        "ИИН", max_length=12, unique=True, validators=[IinValidator]
    )
    gender = models.CharField(
        "Пол", max_length=16, null=True, blank=True, choices=Gender.choices
    )
    birthday = models.DateField("Дата рождения", null=True, blank=True)

    objects = PersonQueryset.as_manager()
    from_iin = PersonFromIinManager()

    class Meta:
        verbose_name = 'Физическое лицо'
        verbose_name_plural = 'Физические лица'

    def __str__(self):
        return self.iin

    @property
    def age(self) -> Optional[int]:
        if isinstance(self.birthday, date):
            return relativedelta(date.today(), self.birthday).years
        return None

    @property
    def user_exists(self):
        return hasattr(self, "user")


class PersonalData(TimeStampedModel, PersonNameMixin):
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name='Физическое лицо',
    )


    first_name = models.CharField("Имя", max_length=255, null=True, blank=True)
    last_name = models.CharField("Фамилия", max_length=255, null=True, blank=True)
    middle_name = models.CharField("Отчество", max_length=255, null=True, blank=True)

    marital_status = models.CharField(
        "Семейное положение",
        max_length=150,
        choices=MaritalStatus.choices,
        blank=True,
        null=True,
    )

    resident = models.BooleanField("Резидент", default=True)
    citizenship = models.CharField("Гражданство", max_length=255, null=True, blank=True)

    document_type = models.CharField(
        "Тип документа", max_length=100, null=True, blank=True
    )
    document_series = models.CharField(
        "Серия документа", max_length=100, null=True, blank=True
    )
    document_number = models.CharField(
        "Номер документа", max_length=50, null=True, blank=True
    )
    document_issue_date = models.DateField("Дата выдачи документа", null=True)
    document_exp_date = models.DateField("Срок действия документа", null=True)
    document_issue_org = models.CharField(
        "Орган выдачи документа", max_length=255, null=True, blank=True
    )

    # Данные супруги/а
    spouse_iin = models.CharField("ИИН Супруги/а", max_length=12, null=True, validators=[IinValidator])
    spouse_name = models.CharField("ФИО супруги/а", max_length=255, null=True, blank=True)
    spouse_phone = PhoneNumberField("Телефон супруги/а", null=True, blank=True)

    dependants_child = models.PositiveIntegerField("Количество детей", default=0)
    dependants_additional = models.PositiveIntegerField(
        "Количество прочих иждивенцев", default=0
    )

    education = models.CharField("Образование", max_length=255, null=True, blank=True)

    job_place = models.CharField("Место работы", max_length=255, null=True, blank=True)
    job_title = models.CharField("Должность", max_length=255, null=True, blank=True)

    reg_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        related_name="%(class)s_reg_related",
        null=True,
        blank=True,
        verbose_name=_("Адрес регистрации"),
    )
    real_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        related_name="%(class)s_real_related",
        null=True,
        blank=True,
        verbose_name=_("Фактический адрес проживания"),
    )
    same_reg_address = models.BooleanField(default=False)

    # Контактные данные
    mobile_phone = PhoneNumberField("Мобильный телефон", blank=True, null=True)
    home_phone = PhoneNumberField("Домашний телефон", blank=True, null=True)
    work_phone = PhoneNumberField("Рабочий телефон", blank=True, null=True)

    additional_contacts = models.ManyToManyField(
        PersonContact,
        through="AdditionalContactRelation",
        blank=True,
        verbose_name=_("Дополнительные контакты"),
    )

    loan_amount = models.DecimalField(
        "Сумма займа",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True)
    bank_account_number = models.CharField(_("Номер счета"), max_length=255, null=True, blank=True)

    # Работа
    organization = models.CharField(
        "Организация", max_length=255, null=True, blank=True
    )
    position = models.CharField(
        "Должность", max_length=255, null=True, blank=True
    )
    additional_income = models.DecimalField(
        "Дополнительный доход",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    job_experience = models.PositiveIntegerField("Стаж работы на тек. месте, мес", null=True, blank=True)
    total_job_experience = models.PositiveIntegerField("Общий стаж работы, мес", null=True, blank=True)
    has_overdue_loans = models.BooleanField(
        "Есть ли задолженность более 60 дней",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ("-created",)

    def __str__(self):
        return f"<Карточка заемщика № {self.pk}>"

    def get_real_address(self):
        return self.real_address or self.reg_address

    def additional_contact(self) -> Optional["AdditionalContactRelation"]:
        additional_contact = self.additional_contact_relation.first()
        if additional_contact:
            return self.additional_contact_relation.first()

        person_contact = PersonContact.objects.create()
        return self.additional_contact_relation.create(
            contact=person_contact
        )


def get_document_number(self):
    return f"{self.document_series or ''}{self.document_number or ''}"


@property
def get_all_data(self) -> dict:
    data = {}
    for field in self._meta.fields:
        if field.related_model:
            data[field.name] = getattr(self, field.name).__str__()
        else:
            data[field.name] = getattr(self, field.name)

    return data


class AdditionalContactRelation(models.Model):
    record = models.ForeignKey(
        PersonalData,
        on_delete=models.CASCADE,
        related_name='additional_contact_relation',
        null=True, blank=True
    )
    profile_record = models.ForeignKey(
        'accounts.ProfilePersonalRecord',
        on_delete=models.CASCADE,
        related_name='additional_contact_relation',
        null=True, blank=True
    )
    contact = models.ForeignKey(PersonContact, on_delete=models.CASCADE)
    relationship = models.CharField(
        "Тип связи с заёмщиком",
        max_length=100,
        null=True,
        blank=True,
        choices=RelationshipType.choices,
    )

    class Meta:
        verbose_name = "Дополнительный контакт"
        verbose_name_plural = "Дополнительные контакты"


class BankAccount(models.Model):
    record = models.OneToOneField(
        PersonalData,
        on_delete=models.CASCADE,
        related_name='bank_account',
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name=_("Наименование банка"),
    )
    account_number = models.CharField(_("Номер счета"), max_length=255, null=True, blank=True)


def personal_photo_path(instance, filename):
    return "photos/{0}/personal/{1}".format(instance.person.iin, filename)


def document_photo_path(instance, filename):
    return "photos/{0}/docs/{1}".format(instance.person.iin, filename)


class PersonalPhoto(models.Model):
    image = models.ImageField("Файл с изображением", upload_to=personal_photo_path)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="photos")


class DocumentPhoto(models.Model):
    image = models.ImageField("Файл с изображением", upload_to=document_photo_path)
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="document_photos"
    )
