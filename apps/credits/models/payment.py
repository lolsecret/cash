from django.db import models
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from apps.credits import PaymentStatus
from apps.credits.models import CreditContract
from apps.credits.services.payment_service import PaymentIntegration
from apps.flow.mixins import ServiceHistoryMixin
from apps.people.models import Person


class CreditApplicationPayment(TimeStampedModel, ServiceHistoryMixin):
    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"

    payment_class = PaymentIntegration()
    contract = models.ForeignKey(
        CreditContract,
        on_delete=models.CASCADE,
        related_name='contract_payments',
        verbose_name="Кредитный контракт",
        null=True,
    )
    status = models.CharField(max_length=50, choices=PaymentStatus.choices, default=PaymentStatus.NOT_PAID)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    _pay_link = models.CharField(null=True, max_length=250)
    order_id = models.CharField(max_length=21, unique=True, db_index=True, null=True)
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
    contract_date = models.DateField("Номер контракта из 1С", null=True, blank=True)

    def __str__(self) -> str:
        return f"№ {self.pk} сумма {self.amount}: {'Оплачен' if self.status == PaymentStatus.PAID  else 'Не оплачен'}"

    @property
    def pay_link(self):
        return self._pay_link

    def change_status(self, status: PaymentStatus) -> None:
        self.status = status
        self.save(update_fields=['status'])

    def generate_and_save_order_id(self):
        today = timezone.localdate()
        formatted_date = today.strftime("%d%m%Y")

        order_id = f'{self.pk}{formatted_date}'
        self.order_id = order_id
        self.save(update_fields=['order_id'])
        return order_id

    def get_reference(self) -> str:
        return self.contract.borrower.iin
