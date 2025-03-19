import base64
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import Fetcher
from apps.credits.models import CreditWithdrawal, CreditContract
from apps.credits import WithdrawalStatus
from apps.accounts.models import BankCard, BankAccount
from apps.flow.models import ExternalService
from apps.flow.integrations.exceptions import ServiceErrorException, ServiceUnavailable

logger = logging.getLogger(__name__)


class WithdrawalBalanceCheck(BaseService, Fetcher):
    """Сервис проверки доступного баланса для вывода средств"""

    def __init__(self, instance, service_model, **kwargs):
        super().__init__(instance, service_model, **kwargs)
        # Для работы с кешем
        self._reference = "balance_check"

    def find_cached_data(self):
        """
        Переопределяем метод для обхода проблемы с get_reference()
        """
        from apps.flow.models import ServiceHistory
        if self.service.cache_lifetime:
            history = ServiceHistory.objects.find_cached_data(
                service=self.service,
                reference=self._reference
            ).first()
            if history:
                logger.info("data from cache %s", history)
            self.cached_data = history.data if history else None

    def get_reference(self):
        """
        Переопределяем метод get_reference() для совместимости с базовым классом
        """
        return self._reference

    def get_headers(self):
        """Генерация заголовков с Basic Auth"""
        merchant_key = settings.MERCHANT_KEY
        merchant_secret = settings.MERCHANT_SECRET

        auth_string = f"{merchant_key}:{merchant_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        return {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json",
        }

    def run(self):
        """Проверка доступного баланса в платежной системе"""
        account = self.service.params.get("withdrawal_account", "EUR-sandbox")

        return self.fetch(
            method="POST",
            json={"account": account},
            headers=self.get_headers()
        )


class DirectWithdrawalService(BaseService, Fetcher):
    """Сервис для прямого вывода средств на карту или счет"""
    instance: CreditWithdrawal

    def __init__(self, instance, service_model, payment_method=None, **kwargs):
        super().__init__(instance, service_model, **kwargs)
        self.payment_method = payment_method

    def get_headers(self):
        """Генерация заголовков с Basic Auth"""
        merchant_key = settings.MERCHANT_KEY
        merchant_secret = settings.MERCHANT_SECRET

        auth_string = f"{merchant_key}:{merchant_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        return {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json",
        }

    def run(self):
        """Инициирует вывод средств напрямую на карту или счет"""
        # Генерация order_id если еще не установлен
        if not self.instance.order_id:
            self.instance.generate_order_id()

        # Формирование данных запроса
        withdrawal_account = self.service.params.get("withdrawal_account", "EUR-sandbox")

        data = {
            "account": withdrawal_account,
            "order_id": self.instance.order_id,
            "amount": int(self.instance.amount * 100),  # Перевод в центы
            "merchant_site": self.service.params.get("merchant_site", "https://dev.microcash.kz"),
            # callback_url убран
        }

        # Добавление данных заемщика
        borrower_data = self.instance.contract.credit.borrower_data
        if borrower_data:
            data.update({
                "customer_first_name": borrower_data.first_name or "",
                "customer_last_name": borrower_data.last_name or "",
                "customer_middle_name": borrower_data.middle_name or "",
                "customer_phone": str(self.instance.contract.credit.lead.mobile_phone),
                "customer_birthdate": borrower_data.person.birthday,
                "customer_zip_code": "121165",
            })

        # Добавление данных метода оплаты
        if isinstance(self.payment_method, BankCard):
            data["payment_method"] = "card"
            data["customer_card_number"] = self.payment_method.card_number
            if hasattr(self.payment_method, 'expiration_date') and self.payment_method.expiration_date:
                data["customer_card_exp_month"] = str(self.payment_method.expiration_date.month).zfill(2)
                data["customer_card_exp_year"] = str(self.payment_method.expiration_date.year)[-2:]

        elif isinstance(self.payment_method, BankAccount):
            data["payment_method"] = "account"
            data["account_withdrawal"] = self.payment_method.iban
            data["account_withdrawal_holder"] = borrower_data.full_name if borrower_data else ""

        # Выполнение API-запроса
        logger.info(f"Инициирование вывода средств: order_id={self.instance.order_id}, сумма={self.instance.amount}")
        response = self.fetch(
            method="POST",
            json=data,
            headers=self.get_headers()
        )

        # Обновление статуса вывода на основе ответа
        self.instance.withdrawal_response = response

        status_code = response.get('status')

        # Если статус 2 - сразу помечаем как выданный (ISSUED или COMPLETED)
        if status_code == 2:
            self.instance.status = WithdrawalStatus.COMPLETED
            self.instance.completed_at = timezone.now()
            credit = self.instance.contract.credit
            credit.issued()
            credit.save()

            logger.info(f"Вывод средств {self.instance.id} успешно выполнен и помечен как выданный")
        elif status_code == 1:  # В обработке
            self.instance.status = WithdrawalStatus.PROCESSING
            logger.info(f"Вывод средств {self.instance.id} в обработке")
        else:  # Ошибка или другой статус
            self.instance.status = WithdrawalStatus.FAILED
            self.instance.error_message = response.get('err') or "Неизвестная ошибка"
            logger.error(f"Ошибка вывода средств {self.instance.id}: {self.instance.error_message}")

        self.instance.save()
        return response
