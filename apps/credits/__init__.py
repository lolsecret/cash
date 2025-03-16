from typing import List
from dataclasses import dataclass, field

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

default_app_config = 'apps.credits.apps.CreditsConfig'


class RepaymentMethod(TextChoices):
    ANNUITY = 'ANNUITY', _('Аннуитетный')
    EQUAL_INSTALMENTS = 'EQUAL_INSTALMENTS', _('Равными долями')

    @classmethod
    def code_for_1c(cls, method: str) -> str:
        codes = {
            cls.ANNUITY.name: "A",
            cls.EQUAL_INSTALMENTS.name: "D"
        }
        return codes[method]


class CreditWayType(TextChoices):
    OFFLINE = 'OFFLINE', _('Оффлайн')
    ONLINE = 'ONLINE', _('Онлайн')


class PaymentStatus(TextChoices):
    NOT_PAID = 'NOT_PAID', _('Не Оплачено')
    PAID = 'PAID', _('Оплачено')
    CANCELED = 'CANCELED', _('Отменен при оплате')
    PAYMENT_ERROR = 'PAYMENT_ERROR', _('Ошибка оплаты')
    IN_PROGRESS = 'IN_PROGRESS', _("В процессе")
    WAITING = 'WAITING', _("В ожидании")


class WithdrawalStatus(TextChoices):
    PENDING = 'PENDING', 'Ожидает обработки'
    PROCESSING = 'PROCESSING', 'В процессе'
    COMPLETED = 'COMPLETED', 'Завершен'
    FAILED = 'FAILED', 'Ошибка'
    CANCELED = 'CANCELED', 'Отменен'


class CreditStatus(TextChoices):
    NEW = 'NEW', _('Новая')
    IN_PROGRESS = 'IN_PROGRESS', _('В процессе')
    IN_WORK = 'IN_WORK', _('В работе')
    IN_WORK_CREDIT_ADMIN = 'IN_WORK_CREDIT_ADMIN', _('В работе (кред.админ)')
    TO_SIGNING = 'TO_SIGNING', _('На подписании')
    GUARANTOR_SIGNING = 'GUARANTOR_SIGNING', _('На подписании гаранта')

    FIN_ANALYSIS = 'FIN_ANALYSIS', _('Фин Анализ')
    DECISION = 'DECISION', _('На рассмотрении')
    DECISION_CHAIRPERSON = 'DECISION_CHAIRPERSON', _('Ожидает решение (председатель)')
    FILLING = 'FILLING', _('На доработке')

    VISIT = 'VISIT', _('Выезд')
    CALLBACK = 'CALLBACK', _('Перезвонить')

    APPROVED = 'APPROVED', _('Одобрен')
    REJECTED = 'REJECTED', _('Отказ')
    CANCEL = 'CANCEL', _('Отмена')

    ISSUANCE = 'ISSUANCE', _('Выдача')
    ISSUED = 'ISSUED', _('Выдан')

    @classmethod
    def color(cls, status):
        return 'danger'


STATUS_COLORS = {
    CreditStatus.NEW: 'info',
    CreditStatus.IN_PROGRESS: 'info',
    CreditStatus.IN_WORK: 'info',
    CreditStatus.APPROVED: 'info',
    CreditStatus.CANCEL: 'info',
    CreditStatus.FIN_ANALYSIS: 'warning',
    CreditStatus.DECISION: 'primary',
    CreditStatus.FILLING: 'info',
    CreditStatus.CALLBACK: 'purple',
    CreditStatus.REJECTED: 'danger',
    CreditStatus.ISSUANCE: 'pink',
    CreditStatus.ISSUED: 'success',
    CreditStatus.DECISION_CHAIRPERSON: 'secondary',
}


class CreditContractStatus(TextChoices):
    CREATED = "CREATED", _("Создан")
    ISSUED = "ISSUED", _("Выдан")
    REPAY = "REPAY", _("Погашается")
    RESTRUCTURED = "RESTRUCTURED", _("Реструктурирован")
    DEBITED = "DEBITED", _("Списан")
    SCHEDULED_FOR_EARLY = "SCHEDULED_FOR_EARLY", _("Запланирован на досрочное погашение")
    REPAID_EARLY = "REPAID_EARLY", _("Досрочно погашен")
    TRANSFERRED_TO_COURT = "TRANSFERRED_TO_COURT", _("Передан в суд")
    EXPIRED = "EXPIRED", _("Просрочен")
    REPAID = "REPAID", _("Погашен")


@dataclass
class FinReportType:
    const_name: str
    name: str
    calculated: bool = False
    values: List[float] = field(default_factory=list)


class ReportType(TextChoices):
    REVENUE = 'REVENUE', _("Выручка")
    GAIN = 'GAIN', _("Маржа в %")
    NET_COST = 'NET_COST', _("Себестоимость")
    GROSS_PROFIT = 'GROSS_PROFIT', _("Валовая прибыль")
    TOTAL_BUSINESS_EXPENSES = 'TOTAL_BUSINESS_EXPENSES', _("ИТОГО Расходы по бизнесу")
    BUSINESS_PROFIT = 'BUSINESS_PROFIT', _("Прибыль от бизнеса")
    OTHER_INCOMES = 'OTHER_INCOMES', _("Прочие доходы")
    OTHER_EXPENSES = 'OTHER_EXPENSES', _("Прочие расходы (семейные)")
    NET_PROFIT = 'NET_PROFIT', _("Чистая прибыль")
    CURRENT_LOAN_INSTALLMENT = 'CURRENT_LOAN_INSTALLMENT', _("Взнос по текущим кредитам")
    ESTIMATED_LOAN_INSTALLMENT = 'ESTIMATED_LOAN_INSTALLMENT', _("Взнос по предполагаемому кредиту")
    NET_RESIDUE_IN_CASH = 'NET_RESIDUE_IN_CASH', _("Чистый остаток")
    NET_RESIDUE_IN_PERCENT = 'NET_RESIDUE_IN_PERCENT', _("Чистый остаток в процентах")

    @classmethod
    def initial_data(cls):
        return [
            cls.field(cls.REVENUE),
            cls.field(cls.GAIN, calculated=True),
            cls.field(cls.NET_COST),
            cls.field(cls.GROSS_PROFIT, calculated=True),
            cls.field(cls.TOTAL_BUSINESS_EXPENSES, calculated=True),
            cls.field(cls.BUSINESS_PROFIT, calculated=True),
            cls.field(cls.OTHER_INCOMES),
            cls.field(cls.OTHER_EXPENSES),
            cls.field(cls.NET_PROFIT, calculated=True),
            cls.field(cls.ESTIMATED_LOAN_INSTALLMENT),
            cls.field(cls.CURRENT_LOAN_INSTALLMENT),
            cls.field(cls.NET_RESIDUE_IN_CASH, calculated=True),
            cls.field(cls.NET_RESIDUE_IN_PERCENT, calculated=True),
        ]

    @staticmethod
    def field(const, *, name=None, is_expense=False, calculated=False):
        if isinstance(const, ReportType):
            const_name = const.name
            name = str(const.label)

        else:
            const_name = name = const

        return {
            'const_name': const_name,
            'name': str(name),
            'is_expense': is_expense,
            'calculated': calculated,
            'data': []
        }


class Decision(TextChoices):
    FOR = 'FOR', 'За'
    AGAINST = 'AGAINST', 'Против'


class DocumentCategory(TextChoices):
    BORROWER_DOCS = 'BORROWER_DOCS', _('Документы по клиенту')
    CREDIT_DOCS = 'CREDIT_DOCS', _('Документы по кредиту')
    GUARANTOR_DOCS = 'GUARANTOR_DOCS', _('Документы гаранта')
    FINANCIAL_ANALYSIS_DOCS = 'FINANCIAL_ANALYSIS_DOCS', _('Документы для финансового анализа')
    OTHER_DOCS = 'OTHER_DOCS', _('Прочие документы')


class CreditHistoryStatus(TextChoices):
    CURRENT = "CURRENT", _("Действующий")
    TERMINATED = "TERMINATED", _("Завершенный")
