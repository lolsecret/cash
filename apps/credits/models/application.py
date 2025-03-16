from datetime import date, datetime
from typing import List, Tuple, Union, Optional
import os
import logging

from decimal import Decimal

from constance import config
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField

from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.db import models, transaction
from django.db.models import JSONField, Count, Max, Q
from django.forms import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django_fsm import FSMField, transition
from phonenumber_field.modelfields import PhoneNumberField
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from sequences import get_next_value

from apps.core.models import (
    UUIDModel,
    CharIDModel,
    City,
    Branch,
    Partner,
)
from apps.credits import (
    RepaymentMethod,
    CreditStatus,
    CreditContractStatus,
    Decision,
    DocumentCategory,
    STATUS_COLORS,
    CreditHistoryStatus, ReportType, CreditWayType,
)
from apps.credits.calculators import CreditCalculator, PaymentSchedule
from apps.credits.managers import (
    LeadQueryset,
    CreditApplicationManager,
    DocumentTypeQuerySet,
)

from apps.notifications.services import send_sms_find_template
from apps.people.models import Person, PersonalData
from apps.flow.mixins import ServiceHistoryMixin
from apps.users.models import User
from .application_fields import CreditApplicationVerigram
from .product import Product
from apps.accounts.models import Profile
from apps.flow import RejectReason
from apps.users import Roles

logger = logging.getLogger(__name__)


def upload_credit_images(instance, filename):
    return os.path.join('credit_images/%s' % instance.credit_id, filename)


def upload_credit_documents(instance, filename):
    return os.path.join('credit_documents/%s' % instance.credit_id, filename)


class CreditParams(models.Model):
    class Meta:
        verbose_name = "Параметры кредита"
        verbose_name_plural = "Параметры кредитов"

    principal = models.DecimalField(
        "Сумма кредита",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
    )
    interest_rate = models.DecimalField(
        "Номинальная процентная ставка",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=Decimal("0"),
    )
    period = models.PositiveSmallIntegerField(
        "Срок кредита", validators=[MinValueValidator(1)]
    )
    repayment_method = models.CharField(
        "Метод погашения",
        choices=RepaymentMethod.choices,
        default=RepaymentMethod.ANNUITY,
        max_length=20,
    )
    desired_repayment_day = models.PositiveSmallIntegerField(
        "Желаемый день погашения",
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    contract_date = models.DateField(
        "Дата заключения договора",
        null=True,
        auto_now_add=True
    )
    aeir = models.DecimalField(max_digits=5, decimal_places=2, null=True)  # noqa

    calculator = CreditCalculator()
    payment_schedule = PaymentSchedule()

    # calc_payments = PaymentsCalculator()

    def __str__(self):
        return "{} KZT на {} мес., ставка - {}%, {}".format(
            self.principal,
            self.period,
            self.interest_rate,
            self.get_repayment_method_display(),
        )

    @property
    def repayment_day(self):
        """Число месяца погашения, проверяем желаемую число месяца погашения,
        если нет, тогда число созданяю заявки,
        если число больше 28, тогда возвращаем 1"""
        day = self.desired_repayment_day or self.contract_date.day
        return day if day <= 28 else 1

    def repayment_date(self) -> date:
        """Метод возвращает 1 число следующего месяца, если текущая дата больше 28 числа"""
        contract_date = self.contract_date
        if contract_date.day > 28:
            return contract_date + relativedelta(months=1, day=1)
        return contract_date

    @property
    def monthly_payment(self):
        return self.calculator.first_month()

    @property
    def last_payment_date(self):
        payment_date = self.contract_date + relativedelta(months=self.period)
        if payment_date.weekday() >= 5:
            payment_date += relativedelta(days=7 - payment_date.weekday())
        return payment_date

    @property
    def payments(self):
        if hasattr(self, '_payments') and self._payments:
            return self._payments

        self._payments = self.payment_schedule.payments
        return self._payments

    @property
    def total_interest(self):
        return sum([payment.reward_amount for payment in self.payments])

    @property
    def overpayment(self):
        return sum([payment.monthly_payment for payment in self.payments])


class RejectionReason(models.Model):
    status = models.CharField("Статус", max_length=255)
    active = models.BooleanField("Активен", default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Причина отказа"
        verbose_name_plural = "Причины отказа"
        ordering = ['order']

    def __str__(self):
        return self.status

    def __repr__(self):
        return self.status


class Lead(TimeStampedModel, UUIDModel, ServiceHistoryMixin):
    class Meta:
        verbose_name = 'Лид'
        verbose_name_plural = '1. Лиды'
        ordering = ("-created",)

    borrower = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="leads",
        verbose_name=_('Borrower'),
    )
    borrower_data = models.ForeignKey(
        PersonalData,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="leads",
        verbose_name="Анкета заемщика",
    )
    borrower_iin = models.CharField(
        "ИИН", max_length=12, null=True,
    )
    first_name = models.CharField("Имя", max_length=255, null=True, blank=True)
    last_name = models.CharField("Фамилия", max_length=255, null=True, blank=True)
    middle_name = models.CharField("Отчество", max_length=255, null=True, blank=True)
    mobile_phone = PhoneNumberField(
        _('Mobile phone'),
        null=True,
        blank=True,
    )
    channel = models.ForeignKey(
        'Channel',
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads",
        verbose_name=_('Channel'),
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads",
        verbose_name=_('Product'),
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads",
        verbose_name=_('Partner'),
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads",
        verbose_name=_("City"),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads",
        verbose_name=_("Филиал"),
    )
    credit_params = models.ForeignKey(
        CreditParams,
        on_delete=models.PROTECT,
        related_name="leads",
        verbose_name="Параметры кредита",
        null=True,
        blank=True,
    )
    current_loan_amount = models.DecimalField(
        "Сумма действующего займа",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    # verified = models.BooleanField("Подтверждена OTP кодом", default=False)
    # verified_at = models.DateTimeField("Подтверждена в", null=True, blank=True, editable=False)
    # otp_apply = models.CharField(
    #     "OTP код, при подаче заявки",
    #     max_length=12,
    #     blank=True,
    #     null=True,
    # )

    rejected = models.BooleanField("Отклонена конвейером", default=False)
    reject_reason = models.CharField(
        "Причина отклонения", max_length=255, null=True, blank=True
    )
    is_done = models.BooleanField("Выполено", default=False)

    # cpa цети
    cpa_transaction_id = models.CharField(
        "transaction id в CPA цети",
        max_length=100,
        null=True,
        blank=True
    )

    # utm метки
    utm_source = models.CharField(
        "UTM метка",
        max_length=255,
        null=True,
        blank=True
    )
    utm_params = JSONField("utm params", null=True, blank=True)

    objects = LeadQueryset.as_manager()

    def __str__(self):
        return str(self.uuid)

    @property
    def full_name(self):
        return " ".join(filter(None, [self.last_name, self.first_name, self.middle_name]))

    def done(self):
        self.is_done = True
        self.save(update_fields=['is_done'])

    def reject(self, reason_code: Optional[RejectReason]) -> None:
        reject_reason = str(reason_code)
        if isinstance(reason_code, RejectReason):
            reject_reason = reason_code.label

        self.rejected = True
        self.reject_reason = reject_reason
        self.save(update_fields=['rejected', 'reject_reason'])

        try:
            self.credit.to_reject(reason=reason_code)
            self.credit.save()
        except Exception as exc:
            logger.error(
                "credit.to_reject error %s", exc,
                extra={'lead': self.pk, 'reason': reason_code}
            )

            try:
                template_name = 'REJECT'
                if isinstance(reason_code, RejectReason):
                    template_name = reason_code.name

                send_sms_find_template(
                    mobile_phone=self.mobile_phone,
                    template_name=template_name,
                )

            except Exception as exc:
                logger.error("send_sms_find_template error %s", exc)
                logger.exception(exc)

    # def verify(self, opt_code: str) -> None:
    #     self.verified = True
    #     self.verified_at = timezone.now()
    #     self.otp_apply = opt_code
    #     self.save(update_fields=["verified", "verified_at", "otp_apply"])

    def get_reference(self) -> str:
        return self.borrower.iin

    def check_params(self) -> None:
        if self.credit_params.principal not in self.product.principal_limits:
            self.reject(_("Указанная сумма не подходит по параметрам"))

        if self.credit_params.period not in self.product.period_limits:
            self.reject(_("Указанный период не подходит по параметрам"))

    def create_credit_application(self, manager: Optional[User] = None) -> 'CreditApplication':
        logger.info("create_credit_application %s", self.pk)
        # return CreditApplication.objects.create(
        #     lead=self,
        #     borrower=self.borrower,
        #     borrower_data=self.borrower_data,
        #     requested_params=self.credit_params,
        # )
        credit = CreditApplication.objects.create_from_lead(self)
        if manager:
            credit.manager = manager
        else:
            credit.manager_auto_select()

        return credit

    def get_credit_report(self):
        from .people import CreditReport
        credit_report, created = CreditReport.objects.get_or_create(lead=self)
        return credit_report


class CreditApplication(TimeStampedModel, ServiceHistoryMixin, CreditApplicationVerigram):
    class Meta:
        verbose_name = 'Кредитная заявка'
        verbose_name_plural = '2. Кредитные заявки'
        ordering = ('-created',)
        permissions = (
            ("can_reject", _("Может отменить")),
            ("can_import", _("Может импортировать")),
            ("can_export", _("Может экспортировать")),
            ("can_distribute", _("Перераспределение между кредитными менеджерами")),
            ("can_use_filter", _("Может использовать фильтр")),
            ("can_use_sort", _("Может использовать сортировку")),
            ("can_credit_report_request", _("Может запросить кредитный отчет")),
            ("can_return_for_revision", _("Может вернуть на доработку"))
        )

    lead = models.OneToOneField(
        Lead,
        related_name="credit",
        on_delete=models.SET_NULL,
        to_field="uuid",
        null=True,
        blank=True,
        verbose_name="Лид",
    )
    borrower = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credits",
        verbose_name="Заёмщик",
    )
    borrower_data = models.ForeignKey(
        PersonalData,
        on_delete=models.CASCADE,
        null=True,
        related_name="credits",
        verbose_name="Анкета заемщика",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='credits',
        verbose_name='Программа'
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="installment_loans",
        verbose_name="Партнер",
    )
    manager = models.ForeignKey(
        "users.User",  # noqa
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Менеджер",
    )
    requested_params = models.ForeignKey(
        CreditParams,
        on_delete=models.PROTECT,
        related_name="credits_requested",
        null=True, blank=True,
        verbose_name="Запрашиваемые параметры",
    )
    recommended_params = models.ForeignKey(
        CreditParams,
        on_delete=models.PROTECT,
        related_name="credits_recommended",
        blank=True,
        null=True,
        verbose_name="Рекомендуемые параметры",
    )
    approved_params = models.ForeignKey(
        CreditParams,
        on_delete=models.PROTECT,
        related_name="credits_approved",
        blank=True,
        null=True,
        verbose_name="Подтвержденные параметры",
    )
    way_type = models.CharField(
        "Путь заявки Онлайн/Оффлайн",
        choices=CreditWayType.choices,
        max_length=20,
        null=True,
        blank=True,
    )
    # status = models.CharField(
    #     "Статус",
    #     max_length=20,
    #     choices=CreditStatus.choices,
    #     default=CreditStatus.NEW,
    #     db_index=True,
    # )
    status = FSMField(
        choices=CreditStatus.choices,
        default=CreditStatus.NEW,
        protected=True
    )

    status_reason = models.CharField(
        "Причина присвоения статуса", max_length=255, blank=True, null=True
    )
    reject_reason = models.ForeignKey(
        RejectionReason,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Причина отказа",
    )

    verified = models.BooleanField("Подтверждена OTP кодом", default=False)
    otp_signature = models.CharField(
        "OTP код, использованный для подписи контракта",
        max_length=12,
        blank=True,
        null=True,
    )
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)

    guarantors_records = models.ManyToManyField(
        PersonalData,
        through="Guarantor",  # noqa
        related_name="guarantor_application"
    )

    # delivery_status = models.CharField(
    #     "Очет о доставке",
    #     max_length=20,
    #     choices=DeliveryStatus.choices,
    #     default=DeliveryStatus.NOT_DELIVERED
    # )

    objects = CreditApplicationManager()

    def __str__(self):
        return f"Кредитная заявка #{self.id}"

    def get_reference(self) -> str:
        return self.borrower.iin

    # region fsm transitions
    @transition(
        status,
        source=CreditStatus.NEW,
        target=CreditStatus.IN_PROGRESS
    )
    def to_check(self):
        """Запуск внутренних проверок"""

    @transition(
        status,
        source=(CreditStatus.IN_PROGRESS,
                CreditStatus.CALLBACK,
                CreditStatus.REJECTED,
                CreditStatus.FILLING),
        target=CreditStatus.IN_WORK
    )
    def to_work(self):
        """Направляем заявку в работу"""
        try:
            send_sms_find_template(mobile_phone=self.lead.mobile_phone, template_name='TO_WORK')

        except Exception as exc:
            logger.error("send_sms_find_template error %s", exc)
            logger.exception(exc)

        # pipeline = self.lead.product.pipeline
        # pipeline.retry_jobs(self)

    @transition(
        status,
        source=(CreditStatus.APPROVED, CreditStatus.FILLING),
        target=CreditStatus.IN_WORK_CREDIT_ADMIN
    )
    def to_work_credit_admin(self):
        """Направляем заявку в работу (кред.админ)"""
        self.way_type = CreditWayType.OFFLINE
        self.save(update_fields=["way_type"])

        try:
            CreditContract.create_from_application(self)
        except ValueError as exc:
            extra_log = {'credit': self.pk, 'contract': self.contract}
            logger.error("credit contract already exists error %s", exc, extra=extra_log)
            logger.exception(exc)

    @transition(
        status,
        source=(CreditStatus.APPROVED,),
        target=CreditStatus.TO_SIGNING
    )
    def to_signing(self):
        """На подписании"""
        self.way_type = CreditWayType.ONLINE
        self.save(update_fields=["way_type"])

        try:
            CreditContract.create_from_application(self)
            send_sms_find_template(self.lead.mobile_phone, template_name=CreditStatus.TO_SIGNING)

        except ValueError as exc:
            extra_log = {'credit': self.id, 'contract': self.pk}
            logger.error("credit contract already exists error %s", exc, extra=extra_log)

    @transition(
        status,
        source=(CreditStatus.TO_SIGNING,),
        target=CreditStatus.GUARANTOR_SIGNING,
    )
    def to_guarantor_signing(self):
        """На подписании у гаранта"""
        from .people import Guarantor
        try:
            for guarantor in self.guarantors.all():  # type: Guarantor
                additional_contact = guarantor.person_record.additional_contact()
                send_sms_find_template(
                    additional_contact.contact.mobile_phone,
                    template_name=CreditStatus.GUARANTOR_SIGNING
                )

        except ValueError as exc:
            extra_log = {'credit': self.id, 'contract': self.pk}
            logger.error("credit contract already exists error %s", exc, extra=extra_log)

    @transition(
        status,
        source=(CreditStatus.IN_WORK,),
        target=CreditStatus.CALLBACK
    )
    def callback(self):
        """Перезвонить"""

    @transition(
        status,
        source=(CreditStatus.IN_WORK,
                CreditStatus.CALLBACK),
        target=CreditStatus.FIN_ANALYSIS
    )
    def fin_analysis(self):
        """Фин аланиз, необходимо получить кред. отчет"""

    @transition(
        status,
        source=(CreditStatus.IN_WORK,
                CreditStatus.FIN_ANALYSIS,
                CreditStatus.FILLING),
        target=CreditStatus.DECISION
    )
    def to_decision(self):
        """Отпрвляем на решение КК"""
        from apps.credits.models import CreditDecision
        # Создаем новое голосование
        CreditDecision.objects.create(credit=self)

    @transition(
        status,
        source=CreditStatus.DECISION,
        target=CreditStatus.DECISION_CHAIRPERSON
    )
    def to_decision_chairperson(self):
        """Ожидает решение председателя"""

    @transition(
        status,
        source=(CreditStatus.DECISION,
                CreditStatus.DECISION_CHAIRPERSON,
                CreditStatus.IN_WORK_CREDIT_ADMIN),
        target=CreditStatus.FILLING,
        permission="credits.can_return_for_revision"
    )
    def rework(self):
        """Отправляем на доработку"""

    @transition(
        status,
        source=(CreditStatus.IN_WORK,
                CreditStatus.IN_WORK_CREDIT_ADMIN),
        target=CreditStatus.APPROVED
    )
    def to_approve(self):
        """Заявка одорбрена"""
        try:
            send_sms_find_template(mobile_phone=self.lead.mobile_phone, template_name='TO_APPROVE')

        except Exception as exc:
            logger.error("send_sms_find_template error %s", exc)
            logger.exception(exc)

    @transition(
        status,
        source=(CreditStatus.NEW,
                CreditStatus.IN_PROGRESS,
                CreditStatus.CALLBACK,
                CreditStatus.IN_WORK,
                CreditStatus.DECISION,
                CreditStatus.DECISION_CHAIRPERSON,
                CreditStatus.FIN_ANALYSIS,
                CreditStatus.IN_WORK_CREDIT_ADMIN,
                CreditStatus.APPROVED,
                CreditStatus.FILLING),
        target=CreditStatus.REJECTED
    )
    def to_reject(self, reason: Optional[RejectReason] = None):
        """Заявка отказана КК, отправим уведомление клиенту"""

        template_name = 'REJECT'
        if isinstance(reason, RejectReason):
            template_name = reason.name

        try:
            send_sms_find_template(
                mobile_phone=self.lead.mobile_phone,
                template_name=template_name,
            )

        except Exception as exc:
            extra_log = {'credit': self.pk, 'reason_code': reason}
            logger.error("send_sms_find_template error %s", exc, extra=extra_log)
            logger.exception(exc)

    @transition(
        status,
        source=(CreditStatus.IN_WORK_CREDIT_ADMIN, CreditStatus.TO_SIGNING, CreditStatus.GUARANTOR_SIGNING),
        target=CreditStatus.ISSUANCE
    )
    def issuance(self):
        """Кредит отправлен на выдачу, запустим фоновое задание создание клиента и контракта"""
        from ..services.payment_service import WithdrawalService

        if not self.is_signed:
            raise ValueError("Кредитная заявка %s не подписана" % self.pk)
        try:
            success = WithdrawalService.initiate_withdrawal_after_contract_sign(self.id)
            if success:
                logger.info(f"Автоматически инициирован вывод средств для договора {self.id}")
            else:
                logger.warning(f"Не удалось автоматически инициировать вывод средств для договора {self.id}")
        except Exception as e:
            logger.error(f"Ошибка при автоматическом инициировании вывода средств: {e}", exc_info=True)

        # if self.way_type == CreditWayType.ONLINE:
        #     from apps.credits.tasks import generate_and_save_credit_documents
        #     generate_and_save_credit_documents.delay(self.pk)

    @transition(
        status,
        source=CreditStatus.ISSUANCE,
        target=CreditStatus.ISSUED
    )
    def issued(self):
        """От 1С получаем callback Кредит выдан, отправим смс уведомление клиенту"""

    def get_transitions(self) -> dict:
        return {transition_status.target: transition_status.method
                for transition_status in self.get_available_status_transitions()}  # noqa

    def available_status_transitions(self) -> List[Tuple[str, str]]:
        return [(transition_status.target.name, transition_status.target.label)
                for transition_status in self.get_available_status_transitions()]  # noqa

    def get_transition_by_status(self, status) -> callable:
        transitions = self.get_transitions()
        assert status in transitions, "Ошибка смены статуса"

        next_status_method = transitions.get(status)
        assert next_status_method, "Ошибка смены статуса"

        return getattr(self, next_status_method.__name__)

    # endregion

    def reject(self, reason, comment=None):
        self.reject_reason = reason
        self.status_reason = comment
        self.to_reject()

    def to_issuance(self, signed_at: date, user: Union[Profile, User] = None, otp: str = None):
        # смена статуса у контракта
        self.contract.sign(signed_at, user, otp)
        self.issuance()

    def decision_status(self, user: "User"):
        # TODO: проверим роль меняющего
        #  выполоним доп действие
        # if user.role != Roles.CREDIT_ADMIN:
        #     return False

        result = self.change_status(
            source=[CreditStatus.IN_PROGRESS],
            target=CreditStatus.DECISION,
        )
        return bool(result)

    @property
    def get_all_data(self) -> dict:
        data = {}
        for field in self._meta.fields:
            if field.related_model:
                data[field.name] = getattr(self, field.name).__str__()
            else:
                data[field.name] = getattr(self, field.name)

        borrower = self.lead.borrower_data.get_all_data
        for k, v in borrower.items():
            data[k] = v
        return data

    def serialize_hook(self, hook):
        return {
            'hook': hook.dict(),
            'data': model_to_dict(self),
        }

    def online_sign_flow(self, *, profile_type: str, user: Union[Profile, User], otp: str):
        signed_at = timezone.localtime().date()

        self.to_issuance(signed_at, user, otp)
        self.save()

        self.save()

    def sign_manual(self):
        self.signed_at = timezone.now()
        self.save(update_fields=["signed_at"])

    def sign_with_otp(self, otp: str):
        self.verified = True
        self.otp_signature = otp
        self.signed_at = timezone.now()
        self.save(update_fields=["verified", "otp_signature", "signed_at"])

    @property
    def is_signed(self):
        return bool(self.signed_at) or bool(self.otp_signature)

    @property
    def is_approved(self) -> bool:
        return self.status == CreditStatus.APPROVED

    def init_credit_params(self) -> None:
        credit_params = model_to_dict(self.requested_params, exclude=['id', 'aeir'])
        # Вызываем save чтобы рассчитался ГЭСВ
        self.requested_params.save()

        if not self.recommended_params:
            self.recommended_params = CreditParams.objects.create(**credit_params)
            # Вызываем save чтобы рассчитался ГЭСВ
            self.recommended_params.save()

        if not self.approved_params:
            self.approved_params = CreditParams.objects.create(**credit_params)
            # Вызываем save чтобы рассчитался ГЭСВ
            self.approved_params.save()

        self.save(update_fields=['recommended_params', 'approved_params'])

    def init_biometry_photos(self) -> 'ApplicationFaceMatchPhoto':
        if not self.biometry_photos.exists():
            logger.info("credit init_biometry_photos %s", self.pk)
            return ApplicationFaceMatchPhoto.objects.create(credit=self)

        return self.biometry_photos.last()

    def manager_auto_select(self):
        credit_managers = User.objects.filter(Q(role=Roles.CREDIT_MANAGER) & Q(is_active=True)).order_by('id')

        if not self.manager and credit_managers.exists():
            latest_credit_manager_list = CreditApplication.objects \
                .filter(manager__isnull=False) \
                .values_list('manager_id', flat=True) \
                .distinct() \
                .order_by('-id')
            current_credit_manager = credit_managers.exclude(id=latest_credit_manager_list[0]).first()

            self.manager = current_credit_manager
        else:
            self.manager = User.objects.get(id=settings.MANAGER_AUTO_SELECTION_ID)
        self.save(update_fields=['manager'])

    def has_guarantors(self) -> bool:
        return self.guarantors.exists()

    @property
    def decision(self) -> 'CreditDecision':
        try:
            return self.decisions.latest('pk')
        except CreditDecision.DoesNotExist:
            return CreditDecision.objects.create(credit=self)

    def get_status_color(self):
        return STATUS_COLORS.get(self.status, 'info')

    def has_status_permission(self, user: "User", perm: str):
        app_label, codename = perm.split(".")
        return user.groups.filter(status_permissions__permission=Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        )[:1], status_permissions__status=self.status).exists()

    # @property
    # def repayment_plan(self) -> RepaymentPlan:
    #     repayment_plan = self.product.repayment_methods.filter(
    #         repayment_method=self.approved_params.repayment_method
    #     ).first()
    #     if repayment_plan:
    #         return repayment_plan
    #     raise ValueError(f"Не указан product_code для {self.approved_params.repayment_method}")
    #
    # @property
    # def product_code(self):
    #     return self.repayment_plan.product_code
    #
    # @property
    # def prefix_contract_code(self):
    #     return self.repayment_plan.prefix_contract_code
    #
    # @property
    # def contract_number(self):
    #     prefix_contract_code = self.repayment_plan.prefix_contract_code
    #     branch_code = self.lead.city.branch_code
    #     number = generate_num(self.id, length=6)
    #     return prefix_contract_code + branch_code + number

    def get_credit_report(self):
        from .people import CreditReport
        credit_report, created = CreditReport.objects.get_or_create(credit=self)
        return credit_report

    @property
    def get_contract_number(self):
        """Генерация номера договора на основе заявки"""
        product_code = self.product.contract_code
        branch_index = self.lead.branch.index
        credit_number = str(self.pk).zfill(5)
        return f"{product_code}{branch_index}{credit_number}"


class StatusTransition(TimeStampedModel):
    class Meta:
        verbose_name = "Изменение статуса"
        verbose_name_plural = "Изменения статуса"
        ordering = ("created",)

    status = models.CharField("Статус", max_length=20, choices=CreditStatus.choices, default=CreditStatus.NEW)
    credit = models.ForeignKey(
        CreditApplication, on_delete=models.CASCADE, related_name="status_transitions"
    )
    reason = models.CharField("Причина", max_length=255, blank=True, null=True)

    def __repr__(self):
        return f"{self.credit_id} - {self.modified} - {self.status}"


class CreditContract(TimeStampedModel):
    class Meta:
        verbose_name = "Кредитный контракт"
        verbose_name_plural = "3. Кредитные контракты"
        ordering = ("-signed_at",)

    credit = models.OneToOneField(
        CreditApplication,
        related_name="contract",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Заявка",
    )
    product = models.ForeignKey(
        Product,
        related_name="contracts",
        on_delete=models.PROTECT,
        verbose_name="Продукт",
    )
    signed_user_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        blank=True, null=True,
    )
    signed_user_object_id = models.PositiveIntegerField(null=True)
    signed_user = GenericForeignKey(
        'signed_user_content_type',
        'signed_user_object_id',
    )
    borrower = models.ForeignKey(
        Person,
        related_name="contracts",
        on_delete=models.PROTECT,
        verbose_name="Заёмщик",
    )
    params = models.ForeignKey(
        CreditParams, on_delete=models.PROTECT, verbose_name="Параметры кредита"
    )
    contract_number = models.CharField(
        "Номер договора", max_length=20, blank=True, null=True
    )
    contract_date = models.DateTimeField(
        "Дата контракта", null=True, blank=True
    )
    contract_status = models.CharField(
        "Статус контракта",
        choices=CreditContractStatus.choices,
        default=CreditContractStatus.CREATED,
        null=True,
        blank=True,
        max_length=50
    )
    reward = models.DecimalField(
        "Вознограждение",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
        default=Decimal(0),
    )
    payments = ArrayField(
        verbose_name="Платежи",
        base_field=JSONField(),
        default=list,
    )
    remaining_principal = models.DecimalField(
        "Сумма кредита",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
    )
    overdue_amount = models.DecimalField(
        "Просроченная задолженость",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
        default=Decimal(0),
    )
    penalty_amount = models.DecimalField(
        "Сумма пени",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal(0))],
        default=Decimal(0),
    )
    overdue_days = models.IntegerField("Количество просроченных дней", default=0)

    signed_at = models.DateField("Дата подписания")
    closed_at = models.DateField("Дата закрытия", null=True, blank=True)

    otp_signature = models.CharField(
        "OTP код, использованный для подписи контракта",
        max_length=12,
        blank=True,
        null=True,
    )

    # objects = CreditContractQueryset.as_manager()

    @classmethod
    @transaction.atomic
    def create_from_application(cls, credit: CreditApplication) -> 'CreditContract':
        if cls.objects.filter(credit=credit).exists():
            raise ValueError("Контракт уже существует для кредитной заявки %s" % credit.pk)

        credit.signed_at = timezone.now()

        # Обновление contract_date у подтвержденных параметров
        approved_params = credit.approved_params
        approved_params.contract_date = credit.signed_at
        approved_params.save()

        # Для создания контракта используем подтвержденные параметры
        contract_params = credit.approved_params
        contract_params.pk = None
        contract_params.save()

        product_code = credit.product.contract_code
        branch_index = credit.lead.branch.index

        # TODO: сделать глобальную настройку
        year = credit.signed_at.strftime("%y")
        contract_sequence = get_next_value(f"contract_number-{year}")
        credit_number = str(contract_sequence).zfill(4)

        contract_number = f"{product_code}{branch_index}{year}{credit_number}"

        # Создадим контракт после подписания
        contract = cls(
            credit=credit,
            product=credit.product,
            borrower=credit.borrower,
            params=contract_params,
            contract_number=contract_number,
            remaining_principal=contract_params.principal,
            signed_at=credit.signed_at.date(),
            contract_date=credit.signed_at,
        )
        contract.save()
        credit.save(update_fields=['signed_at'])
        return contract

    @transaction.atomic
    def sign(self, signed_at: date, user: Union[Profile, User] = None, otp: str = None):
        signed_at_utc = datetime.combine(signed_at, datetime.min.time(), tzinfo=timezone.utc)

        # Обновление contract_date у подтвержденных параметров
        approved_params = self.credit.approved_params
        approved_params.contract_date = signed_at_utc.date()
        params = self.params
        params.contract_date = signed_at_utc.date()

        self.signed_at = signed_at_utc.date()
        self.contract_date = signed_at_utc
        self.contract_status = CreditContractStatus.ISSUED
        self.signed_user = user
        self.otp_signature = otp
        self.credit.sign_with_otp(otp)

        self.save()
        approved_params.save()
        params.save()


class CreditFinance(models.Model):
    FINANCE_REPORT_MONTH = 6

    class Meta:
        verbose_name = _("Финансовые данные")
        verbose_name_plural = _("Финансовые данные")

    credit = models.OneToOneField(
        CreditApplication,
        on_delete=models.CASCADE,
        related_name='credit_finance',
    )
    financial_info_period = models.DateField(_("Текущий период"), blank=True, null=True)
    formation_time = models.TimeField(_("Время формирования кассы"), blank=True, null=True)
    cash_box = models.PositiveIntegerField(_("Касса"), default=0)
    avg_daily_revenue = models.PositiveIntegerField(_("Среднесуточный размер выручки"), default=0)
    economy = models.PositiveIntegerField(_("Сбережения"), default=0)
    tmz = models.PositiveIntegerField(_("ТМЗ"), default=0)
    receivable = models.PositiveIntegerField(_("Дебиторская задолженность"), default=0)

    # Total working capital = sum(cash_box, receivable, economy, tmz, other_current_assets)
    total_working_capital = models.PositiveIntegerField(_("Всего оборотных средств"), default=0)
    equipment = models.PositiveIntegerField(_("Оборудование"), default=0)
    transport = models.PositiveIntegerField(_("Транспорт"), default=0)
    real_property = models.PositiveIntegerField(_("Недвижимость"), default=0)

    # Total fixed assets = sum(equipment, transport, real_property)
    total_fixed_assets = models.PositiveIntegerField(_("Всего основных средств"), default=0)

    # Other current assets
    other_current_assets = models.PositiveIntegerField(_("Прочие оборотные активы"), default=0)

    # Active currency rate
    active_currency_rate = models.PositiveIntegerField(_("Валюта баланса (Актив)"), default=0)
    credit_debt = models.PositiveIntegerField(_("Кредитная задолженность (долги за товар и прочее)"), default=0)
    credit_debt_current = models.PositiveIntegerField(_("Задолженность по текущим кредитам"), default=0)
    credit_debt_total = models.PositiveIntegerField(_("Всего кредитная задолженность"), default=0)
    equity = models.IntegerField(_("Собственный капитал"), default=0)

    # Passive currency rate
    passive_currency_rate = models.PositiveIntegerField(_("Валюта баланса (Пассив)"), default=0)

    profit_report_filled_at = models.DateTimeField(_("Дата заполнения ОПиУ"), blank=True, null=True)
    profit_report_duration = models.DurationField(_("ОПиУ"), blank=True, null=True)

    begin_date = models.DateField(_("Дата начала"), blank=True, null=True)
    end_date = models.DateField(_("Дата конца периода"), blank=True, null=True)
    finance_report = JSONField("Отчет о прибылях и убытках", null=True, blank=True)
    report_comment = models.TextField(_("Комментарий"), blank=True, null=True)

    def save(self, *args, **kwargs):
        self.update_fin_data()
        super().save(*args, **kwargs)

    def update_fin_data(self):
        self.total_working_capital = sum([
            self.cash_box,
            self.receivable,
            self.economy,
            self.tmz,
            self.other_current_assets
        ])
        self.active_currency_rate = sum([self.total_working_capital, self.total_fixed_assets])
        self.credit_debt_total = sum([self.credit_debt, self.credit_debt_current])
        self.equity = self.active_currency_rate - self.credit_debt_total

    def finance_report_default(self):
        fields = []
        for report in ReportType.initial_data():
            report['data'] = [0 for _ in range(self.credit.product.finance_report_month_count + 1)]
            report.pop('calculated')
            fields.append(report)

        return fields

    def finance_report_init(self):
        self.finance_report = self.finance_report_default()
        self.save(update_fields=['finance_report'])

    @property
    def equity_to_assets_ratio(self):
        # coefficient_14
        if self.equity is None or self.total_fixed_assets is None:
            return None
        if self.total_fixed_assets == 0:
            return 0
        return self.equity / self.total_fixed_assets * 100

    @property
    def net_balance_percentage(self):
        """Чистый остаток в процентах"""
        if bool(self.finance_report):
            report_filter = lambda item: item['const_name'] == ReportType.NET_RESIDUE_IN_PERCENT.name
            report = next(filter(report_filter, self.finance_report), None)
            if isinstance(report, dict) and isinstance(report.get('data'), list) and len(report.get('data')):
                return round(report.get('data', [])[-1])
        return 0

    @property
    def equity_div_debit(self) -> float:
        if self.active_currency_rate > 0:
            return round(self.equity / self.active_currency_rate * 100, 2)
        return 0

    def get_credit_debt_current_from_credit_history(self) -> Decimal:
        """Задолженность по текущим кредитам из кредитного отчета"""
        params = dict(
            status=CreditHistoryStatus.CURRENT,
            outstanding_amount__isnull=False,
        )
        return sum(self.credit.credit_history.filter(**params).values_list('outstanding_amount', flat=True))

    def get_monthly_payment_from_credit_history(self) -> Decimal:
        """Взнос по текущим кредитам из кредитного отчета"""
        params = dict(
            status=CreditHistoryStatus.CURRENT,
            monthly_payment__isnull=False,
        )
        return sum(self.credit.credit_history.filter(**params).values_list('monthly_payment', flat=True))


class FinanceReportType(models.Model):
    class Meta:
        verbose_name = _("Отчет о прибылях и убытка")
        verbose_name_plural = _("Отчеты о прибылях и убытка")
        ordering = ('position',)

    name = models.CharField('Название', max_length=255)
    const_name = models.CharField('Константное название', max_length=200, unique=True)
    is_expense = models.BooleanField('Это убыток', default=False)
    calculated = models.BooleanField('Рассчитанный', default=False)
    position = models.IntegerField('Позиция', default=1)

    def __str__(self):
        return self.name


class CreditDecision(TimeStampedModel):
    class Meta:
        verbose_name = _("Решение по кредиту")
        verbose_name_plural = _("Настройки: Решения по кредиту")
        ordering = ('created',)

    credit = models.ForeignKey(
        CreditApplication,
        on_delete=models.CASCADE,
        related_name='decisions'
    )

    def vote(self, *, manager: User, status: Decision, comment: str):
        self.votes.create(
            manager=manager,
            status=status,
            comment=comment,
        )

    def allowed_vote(self, user: "User"):
        """Одобрим, если менеджер еще не голосовал"""
        return not self.votes.filter(manager=user).exists()

    def is_already_voted(self, user: "User"):
        return not self.allowed_vote(user)

    def members_quorum(self):
        """Проверяемдостаточно ли голосов для принятия решения"""
        return self.votes.count() >= 2

    def voting_results(self) -> List[Decision]:
        return self.votes.values_list('status', flat=True)


class CreditDecisionVote(TimeStampedModel):
    manager = models.ForeignKey(
        "users.User",  # noqa
        on_delete=models.CASCADE,
        related_name='manager_decisions',
    )
    decision = models.ForeignKey(
        CreditDecision,
        models.CASCADE,
        related_name='votes',
    )
    status = models.CharField("Решение", max_length=100, choices=Decision.choices)
    comment = models.TextField("Комментарий", blank=True)

    # objects = CreditDecisionVoteQueryset.as_manager()

    class Meta:
        unique_together = ('manager', 'decision')

    @property
    def approved(self):
        return self.status == Decision.FOR

    @property
    def rejected(self):
        return not self.approved


class DocumentGroup(models.Model):
    id = models.CharField("Код группы", max_length=64, primary_key=True, unique=True)
    name = models.CharField("Название", max_length=255)
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    show_label = models.BooleanField("Показывать названия", default=True)

    class Meta:
        verbose_name = _("Группа документов")
        verbose_name_plural = _("Группы документов")
        ordering = ('order',)


class DocumentType(models.Model):
    code = models.CharField("Код документа", max_length=64)
    name = models.CharField("Название типа документа", max_length=255)
    group = models.ForeignKey(
        DocumentGroup,
        on_delete=models.PROTECT,
        related_name='document_types',
    )
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    active = models.BooleanField("Активен", default=True)

    objects = DocumentTypeQuerySet.as_manager()

    class Meta:
        verbose_name = _("Тип документа")
        verbose_name_plural = _("Типы документов")
        unique_together = ('code', 'group')
        ordering = ('order',)

    def __str__(self):
        return self.name


class CreditDocument(models.Model):
    class Meta:
        verbose_name = _("Документ")
        verbose_name_plural = _("Электронное досье")

    credit = models.ForeignKey(
        'CreditApplication',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Тип документа",
    )
    document = models.FileField(upload_to=upload_credit_documents)
    image = models.ImageField(upload_to=upload_credit_images)
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(64, 64)],
        format='JPEG',
        options={'quality': 60}
    )

    # objects = CreditDocumentQuerySet.as_manager()

    @property
    def filename(self):
        if self.document:
            return os.path.basename(self.document.name)

        elif self.image:
            return os.path.basename(self.image.name)

        return None


class Comment(TimeStampedModel):
    class Meta:
        verbose_name = _("Коммент")
        verbose_name_plural = _("Комментарии")
        ordering = ('created',)

    credit = models.ForeignKey(
        CreditApplication,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Автор",
    )
    content = models.TextField("Содержимое")


def borrower_photo_path(instance: 'ApplicationFaceMatchPhoto', filename):
    return "photos/{0}/personal/{1}".format(instance.credit.lead.uuid, filename)


def document_photo_path(instance: 'ApplicationFaceMatchPhoto', filename):
    return "photos/{0}/docs/{1}".format(instance.credit.lead.uuid, filename)


class ApplicationFaceMatchPhoto(TimeStampedModel):
    class Meta:
        verbose_name = _("Изображение для биометрии")
        verbose_name_plural = _("Изображение для биометрии")
        ordering = ("-created",)

    credit = models.ForeignKey(
        'CreditApplication',
        on_delete=models.CASCADE,
        related_name='biometry_photos',
        null=True,
    )

    borrower_photo = models.ImageField(
        "Файл с изображением фото заемщика",
        upload_to=borrower_photo_path,
        blank=True, null=True,
    )
    document_file = models.FileField(
        "Файл с pdf документа",
        upload_to=document_photo_path,
        blank=True, null=True,
    )
    document_photo = models.ImageField(
        "Файл с изображением документа",
        upload_to=document_photo_path,
        blank=True, null=True,
    )
    similarity = models.FloatField("коэффициент сходства", null=True, validators=[MinValueValidator(0.0)])
    attempts = models.PositiveSmallIntegerField(default=0)
    vendor = models.CharField("Вендор", null=True, max_length=255)
    query_id = models.CharField("Query ID", null=True, max_length=255)

    def __str__(self):
        return f"{_('Изображение для биометрии')} {self.pk}"

    def attempts_increment(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])
