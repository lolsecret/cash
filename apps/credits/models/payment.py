import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from apps.people.models import Person
from apps.credits import PaymentStatus, WithdrawalStatus
from apps.credits.models import CreditContract
from apps.flow.mixins import ServiceHistoryMixin
from apps.accounts.models import BankCard

class CreditApplicationPayment(TimeStampedModel, ServiceHistoryMixin):
    """
    Model for storing payment information for credit applications.

    This model tracks payments made toward a credit contract, including
    payment status, amount, and payment gateway details.
    """

    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-created']

    contract = models.ForeignKey(
        CreditContract,
        on_delete=models.CASCADE,
        related_name='contract_payments',
        verbose_name="Кредитный контракт",
        null=True, blank=True
    )
    status = models.CharField(
        "Статус",
        max_length=50,
        choices=PaymentStatus.choices,
        default=PaymentStatus.NOT_PAID,
        db_index=True
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    _pay_link = models.CharField("Ссылка на оплату", max_length=250, null=True, blank=True)
    order_id = models.CharField(
        "Идентификатор заказа",
        max_length=100,
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contract_payments",
        verbose_name="Физическое лицо",
    )
    hash = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    contract_number = models.CharField("Номер контракта из 1С", max_length=50, null=True, blank=True)
    contract_date = models.DateField("Дата контракта из 1С", null=True, blank=True)

    # Payment response data
    payment_response = models.JSONField("Данные ответа платежной системы", null=True, blank=True)

    def __str__(self) -> str:
        status_display = dict(PaymentStatus.choices).get(self.status, self.status)
        return f"Платеж #{self.pk} - {self.amount} KZT - {status_display}"

    @property
    def pay_link(self):
        """Public getter for the payment link."""
        return self._pay_link

    def change_status(self, status: str) -> None:
        """
        Update the payment status.

        Args:
            status: New status from PaymentStatus choices
        """
        old_status = self.status
        self.status = status
        self.save(update_fields=['status'])

        # Add history entry if needed
        if old_status != status and hasattr(self, 'history'):
            # Log the status change in the history if ServiceHistoryMixin is properly set up
            pass

    def generate_and_save_order_id(self):
        """
        Generate a unique order ID for this payment based on payment ID and current date.

        Returns:
            The generated order ID
        """
        today = timezone.localdate()
        formatted_date = today.strftime("%d%m%Y")

        order_id = f'payment-{self.pk}-{formatted_date}'
        self.order_id = order_id
        self.save(update_fields=['order_id'])
        return order_id

    def get_reference(self) -> str:
        """
        Get a reference ID for this payment.

        Returns:
            The borrower's IIN or another identifier
        """
        return self.contract.borrower.iin

    @property
    def is_paid(self) -> bool:
        """Check if the payment has been paid."""
        return self.status == PaymentStatus.PAID


class CreditWithdrawal(TimeStampedModel, ServiceHistoryMixin):
    """
    Модель для вывода средств по кредитному договору.
    """

    class Meta:
        verbose_name = "Вывод средств"
        verbose_name_plural = "Выводы средств"
        ordering = ['-created']

    contract = models.ForeignKey(
        CreditContract,
        on_delete=models.CASCADE,
        related_name='withdrawals',
        verbose_name="Кредитный контракт"
    )
    amount = models.DecimalField(
        "Сумма вывода",
        max_digits=12,
        decimal_places=2
    )
    status = models.CharField(
        "Статус",
        max_length=50,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.PENDING,
        db_index=True
    )
    order_id = models.CharField(
        "Идентификатор заказа",
        max_length=100,
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )
    tokenize_transaction_id = models.CharField(
        "ID транзакции токенизации",
        max_length=100,
        null=True,
        blank=True
    )
    tokenize_form_url = models.URLField(
        "URL для токенизации карты",
        max_length=500,
        null=True,
        blank=True
    )
    withdrawal_response = models.JSONField(
        "Ответ платежной системы",
        null=True,
        blank=True
    )
    error_message = models.TextField(
        "Сообщение об ошибке",
        blank=True,
        null=True
    )
    completed_at = models.DateTimeField(
        "Дата завершения",
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Вывод #{self.pk} - {self.amount} KZT - {self.get_status_display()}"

    def get_reference(self) -> str:
        """Получение идентификатора для отслеживания в внешних системах."""
        return self.contract.borrower.iin

    def complete(self):
        """Отметить вывод средств как завершенный."""
        self.status = WithdrawalStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def fail(self, error_message=None):
        """Отметить вывод средств как неудачный."""
        self.status = WithdrawalStatus.FAILED
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])

    def generate_order_id(self):
        """Генерирует уникальный ID для платежной системы."""
        today = timezone.localdate()
        formatted_date = today.strftime("%Y%m%d%H%M%S")
        order_id = f"withdrawal-{self.contract.id}-{self.pk}-{formatted_date}"
        self.order_id = order_id
        self.save(update_fields=['order_id'])
        return order_id
