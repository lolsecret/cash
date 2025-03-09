import os
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from apps.flow.mixins import ServiceHistoryMixin
from apps.people.models import Person, PersonalData
from apps.people.validators import IinValidator
from apps.flow.models import ServiceReason
from apps.credits import CreditHistoryStatus
from apps.credits.models import Lead, CreditApplication


def upload_pkb_file(instance, filename):
    return os.path.join('pkb_files/%s' % instance.id, filename)


class Guarantor(ServiceHistoryMixin):
    class Meta:
        verbose_name = "Гарант"
        verbose_name_plural = "Гаранты"
        ordering = ('pk',)

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        null=True,
        related_name="guarantor_persons",
        verbose_name="Физическое лицо гаранта"
    )
    person_record = models.ForeignKey(
        PersonalData,
        on_delete=models.CASCADE,
        related_name="guarantor_person_records",
        verbose_name="Персональные данные гаранта"
    )
    credit = models.ForeignKey(
        CreditApplication,
        on_delete=models.CASCADE,
        related_name="guarantors",
        verbose_name="Кредит"
    )
    otp_signature = models.CharField(
        "OTP код, использованный для подписи контракта",
        max_length=12,
        blank=True,
        null=True,
    )
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)

    def get_reference(self) -> str:
        return self.person.iin

    def __str__(self):
        return f"Гарант {self.person_record.__str__()}"

    def get_credit_report(self) -> 'CreditReport':
        credit_report, created = CreditReport.objects.get_or_create(
            guarantor=self,
            # credit=self.credit,
        )
        return credit_report

    def sign_with_otp(self, otp: str):
        self.otp_signature = otp
        self.signed_at = timezone.now()
        self.save(update_fields=["otp_signature", "signed_at"])


class CreditReport(TimeStampedModel):
    class Meta:
        verbose_name = _("Кредитное досье")
        verbose_name_plural = _("Кредитные досье")

    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credit_report",
        verbose_name="Кредитная заявка"
    )

    credit = models.OneToOneField(
        CreditApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credit_report",
        verbose_name="Кредитная заявка"
    )
    guarantor = models.OneToOneField(
        Guarantor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credit_report",
        verbose_name="Гарант"
    )

    # 1C действующие кредиты
    current_loan_payments = models.DecimalField(
        "Наличие действующих кредитов в 1C",
        max_digits=16,
        decimal_places=2,
        default=Decimal(0)
    )

    # ПКБ Soho скоринг
    soho_id_query = models.IntegerField(
        "ID запроса по Soho скорингу", blank=True, null=True
    )
    soho_score = models.PositiveSmallIntegerField(
        "Скор-балл по Soho скорингу", blank=True, null=True
    )

    # ПКБ Поведенческий скоринг
    behavior_id_query = models.IntegerField(
        "ID запроса по поведенческому скорингу", blank=True, null=True
    )
    behavior_score = models.PositiveSmallIntegerField(
        "Скор-балл по поведенческому скорингу", blank=True, null=True
    )
    behavior_default_prob = models.CharField(
        "Вероятность дефолта в течение 12 месяцев",
        max_length=100,
        blank=True,
        null=True,
    )
    behavior_risk_grade = models.CharField(
        "Категория риска", max_length=20, blank=True, null=True
    )
    behavior_bad_rate = models.CharField("", max_length=255, blank=True, null=True)
    behavior_cause = models.TextField(
        "Объяснение низкого скор-балла или его отсутствия", blank=True, null=True,
    )

    # ПКБ Custom Scoring
    custom_scoring_flags = models.JSONField(
        "ПКБ Custom Scoring flags",
        blank=True, null=True,
    )
    custom_scoring_reason_found = models.ManyToManyField(
        ServiceReason,
        related_name="+",
        verbose_name="Найден в списках ПКБ Custom Scoring",
        blank=True,
    )

    # ПКБ Сусн
    susn_reason_found = models.ManyToManyField(
        ServiceReason,
        related_name="+",
        verbose_name="Найден в списках ПКБ СУСН",
        blank=True,
    )

    # ПКБ Доп. источники
    pkb_additional_reason_found = models.ManyToManyField(
        ServiceReason,
        related_name="+",
        verbose_name="Найден в списках ПКБ доп источники",
        blank=True,
    )

    # ПКБ Telco Score
    telco_score = models.PositiveSmallIntegerField(
        "Скор-балл по Telco скорингу", blank=True, null=True
    )

    # ПКБ отчет
    pkb_query_last_30 = models.PositiveIntegerField(null=True)
    pkb_query_last_90 = models.PositiveIntegerField(null=True)
    pkb_query_last_120 = models.PositiveIntegerField(null=True)
    pkb_query_last_180 = models.PositiveIntegerField(null=True)
    pkb_query_last_360 = models.PositiveIntegerField(null=True)

    # PKB Credit report
    pkb_credit_report = models.FileField(
        "Кредитный отчет ПКБ",
        upload_to=upload_pkb_file,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"<Кредитное досье №{self.pk}>"

    @property
    def last_receipt_amount(self):
        """Размер последнего поступления по доходам"""
        last_receipt = self.income_receipts.last()
        if last_receipt:
            return last_receipt.amount
        return Decimal(0)

    @property
    def debt_ratio(self):
        """Коэффициент долговой нагрузки"""
        last_receipt_amount = self.last_receipt_amount
        if last_receipt_amount <= 0 or self.current_loan_payments == 0:
            return Decimal(0)
        return self.current_loan_payments / last_receipt_amount

    debt_ratio.fget.short_description = "Коэффициент долговой нагрузки"  # noqa

    @property
    def custom_score(self):
        flags = self.custom_scoring_flags
        return "; ".join(
            ['%s: %s' % (key, value) for (key, value) in flags.items()]) if isinstance(flags, dict) else ''


class IncomeReceipt(models.Model):
    class Meta:
        verbose_name = _("Поступление доходов")
        verbose_name_plural = _("Поступления доходов")
        ordering = ("date",)

    report = models.ForeignKey(
        CreditReport, on_delete=models.CASCADE, related_name="income_receipts"
    )
    date = models.DateField("Дата поступления")
    amount = models.DecimalField(
        "Сумма",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
    )
    company_name = models.CharField("Наименование организации", max_length=255)
    company_bin = models.CharField("БИН организации", max_length=12, validators=[IinValidator])


class BusinessInfo(models.Model):
    credit = models.OneToOneField(
        'credits.CreditApplication',  # noqa
        on_delete=models.CASCADE,
        related_name='business_info',
    )
    name = models.CharField("Наименование ИП", max_length=255)
    branch = models.CharField("Отрасль", max_length=255)
    place = models.CharField("Место бизнеса", max_length=255)
    working_since = models.PositiveSmallIntegerField("Время работы ИП", null=True)
    website_social = models.CharField("Веб сайт/соц. сети", max_length=255)
    description = models.TextField("Описание бизнеса", null=True)
    expert_opinion = models.TextField("Заключение кредитного эксперта", null=True)
    funding_plan = models.TextField("План финансирования", null=True)


class NegativeStatus(models.Model):
    credit = models.ForeignKey(
        'credits.CreditApplication',  # noqa
        on_delete=models.CASCADE,
        related_name="negative_statuses"
    )
    guarantor = models.ForeignKey(
        'credits.Guarantor',  # noqa
        on_delete=models.CASCADE,
        related_name="negative_statuses",
        null=True,
        blank=True,
    )
    status_id = models.CharField("Статус id", max_length=10, null=True)
    title = models.CharField("Название", max_length=150)
    registration_date = models.DateField("Дата регистации", null=True)
    role = models.CharField("Название роли", max_length=150, null=True)
    role_code = models.CharField("Код роли", max_length=150, null=True)


class CreditHistory(models.Model):
    class Meta:
        verbose_name = "Кредитная история(Контракта)"
        verbose_name_plural = "Кредитная история(Контракты)"

    credit = models.ForeignKey(
        'credits.CreditApplication',  # noqa
        on_delete=models.CASCADE,
        related_name="credit_history"
    )
    status = models.CharField("Статус контракта", max_length=50, choices=CreditHistoryStatus.choices)
    financial_institution = models.CharField("Кредитор", max_length=255, null=True)
    guarantee_type = models.CharField("Вид обеспечения", max_length=255, null=True)
    subject_role_code = models.CharField("Роль код", max_length=150)
    subject_role = models.CharField("Роль", max_length=150)
    agreement_number = models.CharField("Номер договора", max_length=100, null=True)
    start_date = models.DateField("Дата начала срока действия договора")
    end_date = models.DateField("Дата окончания срока действия договора")
    actual_end_date = models.DateField("Дата фактического завершения", null=True)
    total_amount = models.DecimalField(
        "Общая сумма договора",
        max_digits=15,
        decimal_places=2,
        null=True,
    )
    outstanding_amount = models.DecimalField(
        "Непогашенная сумма по кредиту",
        max_digits=15,
        decimal_places=2,
        null=True,
    )
    monthly_payment = models.DecimalField(
        "Сумма периодического платежа",
        max_digits=15,
        decimal_places=2,
        null=True,
    )
    interest_rate = models.DecimalField(
        "Процентная ставка",
        max_digits=15,
        decimal_places=2,
        null=True,
    )
    number_of_installments = models.IntegerField("Общее количество платежей", null=True)
    number_of_outstanding_installments = models.IntegerField("Кол-во непогашенных(предстоящих) платежей", null=True)
    overdue_days = models.IntegerField("Количество дней просрочки", null=True)
    overdue_amount = models.DecimalField(
        "Сумма просроченных взносов",
        max_digits=15,
        decimal_places=2,
        default=0,
        null=True,
    )
