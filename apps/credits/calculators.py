from datetime import date
from decimal import Decimal, ROUND_UP
from functools import cached_property
from typing import TYPE_CHECKING, List, Dict, Optional

from dateutil.relativedelta import relativedelta
from django.template.loader import get_template
from django.utils.html import format_html

from . import RepaymentMethod

if TYPE_CHECKING:
    from .models import CreditParams


def decimal_round(value: Optional[Decimal], rounding: int = 2) -> Decimal:
    if isinstance(value, Decimal):
        value = value.quantize(Decimal(f".{'1'.zfill(rounding)}"))
    return value


class Calculator:
    def __init__(self, amount: Decimal, interest: Decimal, period: int):
        self.amount = amount
        self.interest = interest
        self.period = period
        self.month = 1

    def calc(self) -> Decimal:
        raise NotImplementedError()

    @cached_property
    def payments(self) -> List[Decimal]:
        return [self.calc()] * self.period

    def first_month(self):
        return self.payments[0]

    def last_month(self):
        return self.payments[-1]

    def __iter__(self):
        self.month = 1
        return self

    def __next__(self):
        if self.month <= self.period:
            month = self.month - 1
            self.month += 1
            return self.payments[month]
        else:
            raise StopIteration

    def __getitem__(self, item):
        return self.payments[item]

    def __setitem__(self, key, value):
        raise ValueError

    def __repr__(self):
        return self.payments.__repr__()


class InstallmentCalculator(Calculator):
    def calc(self) -> Decimal:
        return Decimal(round(self.amount / self.period, 2))


class AnnuityCalculator(Calculator):
    def calc(self) -> Decimal:
        monthly_interest = self.interest / 12 / 100

        first_part = monthly_interest * ((1 + monthly_interest) ** self.period)
        second_part = (1 + monthly_interest) ** self.period - 1

        coefficient = first_part / second_part

        return Decimal(round(coefficient * self.amount, 2))


class DifferentiatedCalculator(Calculator):
    def calc(self) -> Decimal:
        pass

    @cached_property
    def payments(self) -> List[float]:
        monthly_interest = self.interest / 12 / 100
        main_debt_payment = self.amount / self.period

        monthly_payments = []
        amount = self.amount

        for month in range(self.period):
            interest_payment = Decimal(amount) * Decimal(monthly_interest)
            monthly_payment = round(Decimal(interest_payment) + Decimal(main_debt_payment), 2)
            monthly_payments.append(monthly_payment)
            amount -= main_debt_payment

        return monthly_payments


class CreditCalculator:
    METHOD_CALCULATORS = {
        RepaymentMethod.ANNUITY.name: AnnuityCalculator,
        RepaymentMethod.EQUAL_INSTALMENTS: DifferentiatedCalculator
    }

    def __get__(self, instance: "CreditParams", owner):
        if instance.interest_rate > 0:
            return self.METHOD_CALCULATORS[instance.repayment_method](
                instance.principal, instance.interest_rate, instance.period
            )
        else:
            return InstallmentCalculator(instance.principal, instance.interest_rate, instance.period)


def pv(fv: Decimal, rate: Decimal, days, base: int = 365):
    exp = Decimal(days / base)
    r = 1 + rate
    return fv * (r ** -exp)


def pv_deriv(fv: Decimal, rate: Decimal, days, base: int = 365):
    exp = Decimal(days / base)
    r = 1 + rate
    return -exp * fv * (r ** (-exp - 1))


def npv(principal: Decimal, payments: List[Decimal], rate: Decimal, first_date: date):
    for m, p in enumerate(payments):
        principal -= pv(p, rate, ((first_date + relativedelta(months=m + 1)) - first_date).days)
    return principal


def npv_deriv(payments: List[Decimal], rate: Decimal, first_date: date):
    result = 0
    for m, p in enumerate(payments):
        result -= pv_deriv(p, rate, ((first_date + relativedelta(months=m + 1)) - first_date).days)
    return result


def calc_aeir(  # noqa
        principal: Decimal,
        interest_rate: Decimal,
        first_date: date,
        payments: List[Decimal],
        threshold: float = 1e-3,
        max_iterations: int = 100,
):
    """Расчет ГЭСВ"""
    if not principal or not interest_rate or not first_date:
        return 0
    _rate = interest_rate / 100
    for i in range(max_iterations):
        _npv = npv(principal, payments, _rate, first_date)
        if abs(_npv) <= threshold:
            return decimal_round(_rate * 100)
        _dnpv = npv_deriv(payments, _rate, first_date)
        _rate -= _npv / _dnpv
    raise ValueError("Cannot calculate apr after %d iterations" % max_iterations)


class Payment:
    """
    Класс платежа для одного месяца в графике платежа
    """

    def __init__(
            self,
            month: int,
            maturity_date: date,
            principal_amount: Decimal,
            reward_amount: Decimal,
            monthly_payment: Decimal,
            remaining_debt: Decimal
    ):
        """
        :param maturity_date: Дата погашения
        :param principal_amount: основная сумма долго
        :param reward_amount: Сумма вознаграждения
        :param monthly_payment: Ежемесячный платеж
        :params remaining_debt: Остаток долга на дату следующего погашения
        """
        self.month = month
        self.maturity_date = maturity_date
        self.principal_amount = principal_amount
        self.reward_amount = reward_amount
        self.monthly_payment = monthly_payment
        self.remaining_debt = remaining_debt

    def as_html(self) -> str:
        return format_html(f"<td>{self.month}</td>") + \
               format_html(f"<td>{self.maturity_date}</td>") + \
               format_html(f"<td>{self.principal_amount}</td>") + \
               format_html(f"<td>{self.reward_amount}</td>") + \
               format_html(f"<td>{self.monthly_payment}</td>") + \
               format_html(f"<td>{self.remaining_debt}</td>")


class AnnuityPaymentScheduleOld(AnnuityCalculator):
    template = "credits/payment_schedule.html"

    def __init__(self, instance: 'CreditParams', owner):
        self.interest_rate = instance.interest_rate
        # self.ir_is_pm = instance.interest_rate / (12 * 100)
        self.ir_is_pm = instance.interest_rate * 30 / (360 * 100)
        self.monthly_payment = instance.monthly_payment
        self.total_payments = instance.monthly_payment * instance.period
        self.principal = instance.principal
        self.overpayment = self.total_payments - instance.principal
        # self.payment_date = instance.contract_date
        self.payment_date = instance.repayment_date()
        self.period = instance.period
        self._payments = []

    @cached_property
    def payments(self) -> List[Payment]:
        remaining_debt = self.principal
        for month in range(1, self.period + 1):
            monthly_pay = self.principal * self.ir_is_pm / (1 - (1 + self.ir_is_pm) ** (self.period * -1))
            reward_amount = remaining_debt * self.ir_is_pm
            principal_amount = monthly_pay - reward_amount
            remaining_debt -= principal_amount

            payment = Payment(
                month=month,
                maturity_date=self.payment_date + relativedelta(months=month),
                principal_amount=principal_amount,
                reward_amount=reward_amount,
                monthly_payment=self.monthly_payment,
                remaining_debt=remaining_debt,
            )
            self._payments.append(payment)

        return self._payments

    def __iter__(self):
        self.month = 1
        return self

    def __next__(self):
        if self.month <= self.period:
            month = self.month - 1
            self.month += 1
            return self.payments[month]
        else:
            raise StopIteration

    def __getitem__(self, item):
        return self.payments[item]

    def __setitem__(self, key, value):
        raise ValueError

    def __repr__(self):
        return self.payments.__repr__()

    def as_html(self) -> str:
        template = get_template(self.template)
        return template.render({"payments": self})


class AnnuityPaymentSchedule:
    def __init__(self, instance: 'CreditParams', owner=None) -> None:
        self.principal: Decimal = instance.principal
        self.period: int = instance.period
        self.interest_rate: Decimal = instance.interest_rate / 100
        self.payment_date = instance.repayment_date()
        self.contract_date = instance.contract_date
        self.today = date.today()

    @cached_property
    def factor(self):
        discounting_factor = 0
        cumulative_days = 0
        for _ in range(self.period):
            cumulative_days += 30
            discounting_factor += decimal_round(1 / (1 + self.interest_rate / 12) ** Decimal(cumulative_days / 30), 10)
        return Decimal(discounting_factor)

    def interest(self, amount: Decimal, rate: Decimal, period=30, base=360):
        """Calculate interest for a current period"""
        return decimal_round(amount * rate * period / base, 2)

    @property
    def monthly_payment(self):
        return decimal_round(self.principal / self.factor, 2)

    def maturity_date(self, month):
        next_date = self.payment_date + relativedelta(months=month)
        if month == self.period:
            next_date = self.contract_date + relativedelta(months=self.period)

        if next_date.weekday() >= 5:
            next_date += relativedelta(days=7 - next_date.weekday())
        return next_date

    def difference_between_days(self): # noqa
        return (self.contract_date + relativedelta(months=1, day=1) - self.contract_date).days

    @property
    def payments(self):
        remaining_debt = self.principal
        payments: List[Payment] = []
        for month in range(self.period):
            monthly_payment = self.monthly_payment
            reward_amount = self.interest(remaining_debt, self.interest_rate, 30, 360)
            principal_amount = decimal_round(monthly_payment - reward_amount)
            if self.contract_date.day > 28:
                daily_rate = reward_amount / 30 * self.difference_between_days()

                # Расчет Первого платежа если дата выдачи после 28 чисел
                if month == 0:
                    monthly_payment = principal_amount + reward_amount + daily_rate

                    reward_amount += daily_rate

                # Если платеж последний остаток долга перенесем в ежемесячный платеж
                elif month == self.period - 1:
                    reward_amount -= daily_rate
                    monthly_payment = decimal_round(monthly_payment + remaining_debt - principal_amount - daily_rate)
                    principal_amount = decimal_round(monthly_payment - reward_amount)

            elif month == self.period - 1:
                monthly_payment = monthly_payment + remaining_debt - principal_amount
                principal_amount = remaining_debt

            remaining_debt = remaining_debt - principal_amount
            payments.append(Payment(
                month=month,
                maturity_date=self.maturity_date(month + 1),
                principal_amount=principal_amount,
                reward_amount=reward_amount,
                monthly_payment=monthly_payment,
                remaining_debt=remaining_debt,
            ))

        return payments


class DifferentiatedPaymentSchedule(AnnuityPaymentSchedule):
    @cached_property
    def payments(self) -> List[Payment]:
        main_debt_payment = decimal_round(self.principal / self.period)
        principal = self.principal
        payments: List[Payment] = []

        for month in range(1, self.period + 1):
            interest_payment = decimal_round(self.interest_rate * principal * 30 / 360)
            remaining_debt = decimal_round(principal - main_debt_payment)
            if self.contract_date.day > 28:
                daily_rate = interest_payment / 30 * self.difference_between_days()

                # Расчет Первого платежа если дата выдачи после 28 чисел
                if month == 1:
                    interest_payment += daily_rate

                # Если платеж последний остаток долга перенесем в ежемесячный платеж
                elif month == self.period:
                    interest_payment -= daily_rate

            if month == self.period:
                main_debt_payment = principal
                remaining_debt = Decimal(0)

            payment = Payment(
                month=month,
                maturity_date=self.maturity_date(month),
                principal_amount=main_debt_payment,
                reward_amount=interest_payment,
                monthly_payment=decimal_round(Decimal(interest_payment) + Decimal(main_debt_payment)),
                remaining_debt=remaining_debt
            )
            payments.append(payment)
            principal -= main_debt_payment

        return payments


class PaymentSchedule:
    METHOD_CALCULATORS = {
        RepaymentMethod.ANNUITY.name: AnnuityPaymentSchedule,
        RepaymentMethod.EQUAL_INSTALMENTS.name: DifferentiatedPaymentSchedule
    }

    def __get__(self, instance: "CreditParams", owner):
        return self.METHOD_CALCULATORS[instance.repayment_method](
            instance, owner
        )
