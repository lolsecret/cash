from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django_extensions.db.models import TimeStampedModel

from apps.core.models import PersonNameMixin, Bank
from apps.flow.mixins import ServiceHistoryMixin
from apps.people import MaritalStatus
from apps.people.models import Person, PersonContact, Address
from apps.people.validators import IinValidator


def profile_selfie_path(instance, filename):
    directory = instance.profile.id
    if hasattr(instance.profile, 'person') and instance.profile.person:
        directory = instance.profile.person.iin
    return "photos/{0}/personal/{1}".format(directory, filename)

def bank_statement_path(instance, filename):
    directory = instance.profile.id
    if hasattr(instance.profile, 'person') and instance.profile.person:
        directory = instance.profile.person.iin
    return "statements/{0}/{1}".format(directory, filename)

class ProfileManager(BaseUserManager):
    def get_by_natural_key(self, username):
        try:
            return super().get_by_natural_key(username)
        except Profile.DoesNotExist:
            return self.get(email=username)


class Profile(AbstractUser):
    USERNAME_FIELD = 'phone'

    username = None
    phone = PhoneNumberField(unique=True, null=True, blank=True)
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="personal_account",
        verbose_name="Заёмщик",
    )
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this profile belongs to. A profile will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="profile_set",
        related_query_name="profile",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('profile permissions'),
        blank=True,
        help_text=_('Specific permissions for this profile.'),
        related_name="profile_set",
        related_query_name="profile",
    )
    is_registered = models.BooleanField("Зарегистрирован", default=False)

    objects = ProfileManager()

    class Meta:
        verbose_name = "Пользователь ЛК"
        verbose_name_plural = "Пользователи ЛК"

    def get_username(self):
        return str(self.email or self.phone.as_e164)

    def register_completed(self):
        self.last_login = timezone.now()
        self.is_registered = True
        self.save(update_fields=['is_registered'])

    def __str__(self):
        return self.get_username()


class ProfilePersonalRecord(TimeStampedModel, PersonNameMixin, ServiceHistoryMixin):
    profile = models.OneToOneField(
        Profile,
        on_delete=models.CASCADE,
        related_name="personal_record",
        verbose_name="Пользователь ЛК",
    )

    bank_account_number = models.CharField(_("Номер счета"), max_length=255, null=True, blank=True)

    selfie = models.ImageField(
        "Селфи пользователя ЛК",
        upload_to=profile_selfie_path,
        null=True,
        blank=True,
    )
    # TODO: будем использовать для ручной подругзки документа
    id_document_pdf = models.FileField(
        "Фото документа",
        upload_to=profile_selfie_path,
        null=True,
        blank=True,
        help_text="Фото документа в pdf",
    )
    document_photo = models.ImageField(
        "Файл с изображением документа",
        upload_to=profile_selfie_path,
        blank=True, null=True,
    )
    validated = models.BooleanField("Прошел валидацию", null=True)
    similarity = models.FloatField(
        "коэффициент сходства", null=True, blank=True,  validators=[MinValueValidator(0.0)]
    )
    attempts = models.PositiveSmallIntegerField("Кол-во попыток", null=True, default=0)

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
    document_issue_date = models.DateField("Дата выдачи документа", null=True, blank=True)
    document_exp_date = models.DateField("Срок действия документа", null=True, blank=True)
    document_issue_org = models.CharField(
        "Орган выдачи документа", max_length=255, null=True, blank=True
    )

    # Данные супруги/а
    spouse_iin = models.CharField("ИИН Супруги/а", max_length=12, blank=True, null=True, validators=[IinValidator])
    spouse_name = models.CharField("ФИО супруги/а", max_length=255, null=True, blank=True)
    spouse_phone = PhoneNumberField("Телефон супруги/а", null=True, blank=True)

    dependants_child = models.PositiveIntegerField("Количество иждивенцев", default=0)
    dependants_additional = models.PositiveIntegerField(
        "Количество прочих иждивенцев", default=0
    )
    bank_statement = models.FileField(
        "Банковская выписка",
        upload_to=bank_statement_path,
        null=True,
        blank=True,
    )
    average_monthly_income = models.DecimalField(
        "Средний ежемесячный доход",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    income_calculated_at = models.DateTimeField(
        "Дата расчета дохода",
        null=True,
        blank=True
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
        through="people.AdditionalContactRelation",
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
        default=False
    )
    class Meta:
        verbose_name = "Регистрационные данные"
        verbose_name_plural = "Регистрационные данные пользователей ЛК"
        ordering = ("-created",)

    def __str__(self):
        person_id = self.profile.person and self.profile.person.iin or self.profile.id
        return f"<Данные пользователя ЛК {person_id} № {self.pk}>"

    def save_selfie(self, img):
        self.selfie = img
        self.save(update_fields=['selfie'])

    def get_reference(self) -> str:
        return self.profile.person.iin # noqa


class BankAccount(TimeStampedModel):
    record = models.ForeignKey(
        ProfilePersonalRecord,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        verbose_name=_("Профиль"),
    )
    iban = models.CharField(_("IBAN номер"), max_length=34, unique=True)
    bank_name = models.CharField(_("Название банка"), max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _("Банковский счет")
        verbose_name_plural = _("Банковские счета")
        ordering = ['-created']

    def __str__(self):
        return f"{self.bank_name} ({self.iban})"


class BankCard(TimeStampedModel):
    record = models.ForeignKey(
        ProfilePersonalRecord,
        on_delete=models.CASCADE,
        related_name="bank_cards",
        verbose_name=_("Профиль"),
    )
    card_number = models.CharField(_("Номер карты"), max_length=16, unique=True)
    expiration_date = models.DateField(_("Срок действия"), null=True, blank=True)
    card_holder = models.CharField(_("Держатель карты"), max_length=255, null=True, blank=True)
    card_type = models.CharField(
        _("Тип карты"),
        max_length=10,
        choices=[("VISA", "VISA"), ("MASTERCARD", "MasterCard")], null=True, blank=True
    )

    class Meta:
        verbose_name = _("Банковская карта")
        verbose_name_plural = _("Банковские карты")
        ordering = ['-created']

    def __str__(self):
        return f"{self.card_type} ****{self.card_number[-4:]}"
