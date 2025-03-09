from decimal import Decimal

from django.contrib.postgres.fields import DecimalRangeField, IntegerRangeField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import PositiveIntegerField
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from apps.core.models import CharIDModel, Partner
from apps.credits import RepaymentMethod
from apps.flow.models import Pipeline, ServiceReason


class Channel(CharIDModel):
    class Meta:
        verbose_name = _("Канал продаж")
        verbose_name_plural = _("Настройки: Каналы продаж")

    name = models.CharField("Наименование", max_length=255)

    def __str__(self):
        return self.name


class FinancingType(models.Model):
    class Meta:
        verbose_name = _("Вид финансирования")
        verbose_name_plural = _("Настройки: Вид финансирования")

    name = models.CharField("Название", max_length=255)

    def __str__(self):
        return self.name


class FundingPurpose(models.Model):
    class Meta:
        verbose_name = _("Цель финансирования")
        verbose_name_plural = _("Настройки: Цель финансирования")

    name = models.CharField("Название", max_length=255)

    def __str__(self):
        return self.name


class Product(TimeStampedModel, CharIDModel):
    class Meta:
        verbose_name = _("Кредитный продукт")
        verbose_name_plural = _("Настройки: Кредитные продукты")

    name = models.CharField('Наименование', max_length=255)

    financing_purpose = models.ForeignKey(
        FundingPurpose,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Цель финансирования'
    )
    financing_type = models.ForeignKey(
        FinancingType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Вид финансирования'
    )
    bonus_days = models.PositiveIntegerField(
        _("Бонусные дни (без процентов)"),
        default=15,
    )
    contract_code = models.CharField('Код в номере контракта', max_length=2, null=True)
    partner = models.ForeignKey(
        Partner,
        on_delete=models.SET_NULL,
        related_name="products",
        blank=True,
        null=True,
        verbose_name=_("Партнёр"),
    )
    interest_rate = models.DecimalField(
        _("Годовая процентная ставка"),
        max_digits=5,
        decimal_places=2,
        default=Decimal(0),
    )
    principal_limits = DecimalRangeField(
        _("Ограничения по сумме"),
        default="[200000, 3000000]",
    )
    period = PositiveIntegerField(
        _("Срок"), default="20"
    )
    max_loan_amount = models.PositiveIntegerField(
        _("Максимальная сумма кредита"),
        null=True, blank=True,
    )

    # contract_template = models.ForeignKey(
    #     PrintForm,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     verbose_name='Шаблон договора'
    # )
    minimum_income = models.DecimalField(
        _("Минимальная сумма дохода"), max_digits=12, decimal_places=2, default=Decimal(0)
    )
    maximum_loan_amount_with_minimum_income = models.DecimalField(
        _("Максимальная сумма кредита при минимальном доходе"), max_digits=12, decimal_places=2, default=Decimal(0)
    )

    age_limits_male = IntegerRangeField(
        _("Ограничения по возрасту для мужчин"), blank=True, null=True
    )
    age_limits_female = IntegerRangeField(
        _("Ограничения по возрасту для женщин"), blank=True, null=True
    )
    age_limits_active = models.BooleanField(
        _("Ограничения по возрасту активны"), default=True
    )
    max_debt_ratio = models.DecimalField(
        _("Максимальный коэффициент долговой нагрузки (КДН)"),
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0)), MaxValueValidator(Decimal(1))],
        default=Decimal("0.5"),
    )
    finance_report_month_count = models.PositiveSmallIntegerField(
        _("Период фин.анализа"), default=6
    )

    # Soho Score
    pkb_soho_min_score = models.PositiveSmallIntegerField(
        _("Минимальный балл по Soho Score"), default=0
    )

    pkb_behavioral_min_score = models.PositiveIntegerField(
        _("Минимальный балл по поведенческому скорингу"), default=0
    )
    pkb_behavioral_allow_blank = models.BooleanField(
        _("Пропускать заёмщиков без балла по поведенческому скорингу"), default=False
    )

    reduction_factor = models.DecimalField(
        _("Понижающий коэффициент"),
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0)), MaxValueValidator(Decimal(1))],
        default=Decimal("0.5"),
    )
    gkb_incomes_enable = models.BooleanField(_("Активировать проверку по доходам"), default=False)
    gkb_incomes_min_income_for_check = models.DecimalField(
        _("Минимальная сумма займа для проверки по доходам"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=Decimal("0"),
    )
    gkb_incomes_min_last_month = models.PositiveSmallIntegerField(
        _("Наличие не менее одного платежа за последних месяцев"),
        default=0
    )

    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",
        verbose_name=_("Конвейер"),
    )

    # hooks = models.ForeignKey(
    #     Pipeline,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     verbose_name="Веб хуки"
    # )
    accounting_prefix_code = models.CharField(_("Префикс в 1С"), max_length=12, null=True, blank=True)
    accounting_annuity = models.CharField(
        _("Код 1С Аннуитетный"), max_length=20, null=True, blank=True
    )
    accounting_equal_instalments = models.CharField(
        _("Код 1С Дифференцированный"), max_length=20, null=True, blank=True
    )

    reject_reasons = models.ManyToManyField(
        ServiceReason,
        blank=True,
        verbose_name=_("Включить проверки"),
    )

    is_active = models.BooleanField(_("Активен"), default=False)

    # objects = ProductManager()

    def __str__(self):
        return self.name

    # def get_merchant_commission_by_period(self, period):
    #     credit_term = self.merchant_commission.filter(period=period).values('interest_rate').first()
    #     return credit_term['interest_rate'] if credit_term else self.interest_rate


class RepaymentPlan(models.Model):
    class Meta:
        verbose_name = _("Метод погашения")
        verbose_name_plural = _("Доступные методы погашения")
        unique_together = ('product', 'repayment_method')

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='repayment_methods',
    )
    repayment_method = models.CharField(
        _("Метод погашения"),
        choices=RepaymentMethod.choices,
        default=RepaymentMethod.ANNUITY,
        max_length=20
    )
    prefix_contract_code = models.CharField(_("Префикс для номера договора"), max_length=5, default='')
    product_code = models.CharField(_("Код продукта в 1С"), max_length=12)
    is_active = models.BooleanField(_("Активен"), default=True)

    def __str__(self):
        return self.get_repayment_method_display()
