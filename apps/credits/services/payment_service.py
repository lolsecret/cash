import logging
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import BankCard, BankAccount
from apps.credits import PaymentStatus, WithdrawalStatus
from apps.credits.models import CreditApplicationPayment, CreditWithdrawal, CreditContract
from apps.flow.integrations.external.payment_gateway import (
    PaymentGatewayCreateForm,
    PaymentGatewayStatusCheck
)
from apps.flow.integrations.external.payment_withdraw import WithdrawalBalanceCheck, DirectWithdrawalService
from apps.flow.models import ExternalService
from apps.flow.integrations.exceptions import ServiceErrorException, ServiceUnavailable
from config import settings

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Exception for payment gateway errors."""
    pass


class PaymentService:
    """
    Service for payment operations, leveraging the flow and ExternalService framework.
    """

    @classmethod
    def create_payment_link(cls, payment: CreditApplicationPayment) -> str:
        """
        Create a payment link for a payment using the ExternalService framework.

        Args:
            payment: The payment object to create a link for

        Returns:
            The payment form URL

        Raises:
            PaymentGatewayError: If the service fails
        """
        try:
            # Get the configured external service
            service = ExternalService.objects.filter(
                service_class__contains='PaymentGatewayCreateForm',
                is_active=True
            ).first()

            if not service:
                # Log and use default
                logger.warning("No active PaymentGatewayCreateForm service found. Using default.")
                service = cls._get_default_create_form_service()

            # Create and run the service
            service_instance = PaymentGatewayCreateForm(payment, service_model=service)
            service_instance.run_service()

            # Return the payment link
            if not payment._pay_link:
                raise PaymentGatewayError("Payment link not generated")

            return payment._pay_link

        except (ServiceErrorException, ServiceUnavailable) as e:
            logger.error(f"Payment gateway error for payment_id={payment.id}: {e}")
            raise PaymentGatewayError(f"Error calling payment gateway: {e}")

    @classmethod
    def check_payment_status(cls, payment: CreditApplicationPayment) -> str:
        """
        Check payment status using the ExternalService framework.

        Args:
            payment: The payment object to check

        Returns:
            The current payment status

        Raises:
            PaymentGatewayError: If the service fails
        """
        if not payment.order_id:
            logger.error(f"Cannot check payment status - no order_id for payment_id={payment.id}")
            return payment.status

        try:
            # Get the configured external service
            service = ExternalService.objects.filter(
                service_class__contains='PaymentGatewayStatusCheck',
                is_active=True
            ).first()

            if not service:
                # Log and use default
                logger.warning("No active PaymentGatewayStatusCheck service found. Using default.")
                service = cls._get_default_status_check_service()

            # Create and run the service
            service_instance = PaymentGatewayStatusCheck(payment, service_model=service)
            service_instance.run_service()

            return payment.status

        except (ServiceErrorException, ServiceUnavailable) as e:
            logger.error(f"Error checking payment status for payment_id={payment.id}: {e}")
            raise PaymentGatewayError(f"Error checking payment status: {e}")

    @classmethod
    def check_payment_status_and_send_callback(cls):
        """
        Periodic task to check all pending payments and update their status.
        Uses the ExternalService framework to check each payment.
        """
        pending_payments = CreditApplicationPayment.objects.filter(
            Q(status=PaymentStatus.NOT_PAID) |
            Q(status=PaymentStatus.IN_PROGRESS) |
            Q(status=PaymentStatus.WAITING)
        ).exclude(order_id__isnull=True)

        logger.info(f"Checking status for {pending_payments.count()} pending payments")

        # Get the configured external service once to reuse
        service = ExternalService.objects.filter(
            service_class__contains='PaymentGatewayStatusCheck',
            is_active=True
        ).first()

        if not service:
            # Log and use default
            logger.warning("No active PaymentGatewayStatusCheck service found. Using default.")
            service = cls._get_default_status_check_service()

        for payment in pending_payments:
            try:
                # Create and run the service for each payment
                service_instance = PaymentGatewayStatusCheck(payment, service_model=service)
                service_instance.run_service()

                # Payment status is updated in post_run() method of the service
            except Exception as e:
                logger.error(f"Error processing payment {payment.id}: {e}")

    @classmethod
    def _get_default_create_form_service(cls):
        """Create a default service configuration for payment form creation."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Payment Gateway Create Form",
            service_class="apps.flow.integrations.external.payment_gateway.PaymentGatewayCreateForm",
            defaults={
                "address": "https://api-gateway.smartcore.pro/initPayment",
                "is_active": True
            }
        )
        return service

    @classmethod
    def _get_default_status_check_service(cls):
        """Create a default service configuration for payment status check."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Payment Gateway Status Check",
            service_class="apps.flow.integrations.external.payment_gateway.PaymentGatewayStatusCheck",
            defaults={
                "address": "https://api-gateway.smartcore.pro/check",
                "is_active": True
            }
        )
        return service


class WithdrawalService:
    """Сервис для управления выводом средств"""

    @classmethod
    def validate_card_with_statement(cls, personal_record, card):
        """
        Проверяет соответствие карты данным из банковской выписки.

        Args:
            personal_record: Личные данные пользователя с информацией из выписки
            card: Банковская карта для вывода средств

        Raises:
            ValueError: Если проверка не прошла
        """
        # Пропускаем проверку, если в выписке нет информации о карте
        if not personal_record.bank_statement_card_number:
            logger.warning("Пропуск проверки карты - отсутствует информация о карте в выписке")
            return True

        # Проверяем соответствие последних 4 цифр
        card_last_digits = card.card_number[-4:]
        if card_last_digits != personal_record.bank_statement_card_number:
            logger.error(
                f"Несоответствие последних 4 цифр карты: в выписке {personal_record.bank_statement_card_number}, на карте {card_last_digits}")
            raise ValueError(
                f"Последние 4 цифры карты ({card_last_digits}) не совпадают с данными в банковской выписке ({personal_record.bank_statement_card_number})"
            )

        return True

    @classmethod
    def create_and_initiate_withdrawal(cls, contract_id, payment_method_id, personal_record=None):
        """
        Создает и инициирует вывод средств для указанного контракта.

        Args:
            contract_id: ID кредитного контракта
            payment_method_id: ID платежного метода (карты)
            personal_record: Личные данные пользователя (опционально)

        Returns:
            CreditWithdrawal: Созданная запись вывода средств

        Raises:
            ValueError: Если контракт не найден, не подписан или есть другие ошибки валидации
            ServiceErrorException: Если произошла ошибка при обращении к платежной системе
        """
        # Получаем контракт
        try:
            contract = CreditContract.objects.get(id=contract_id)
        except CreditContract.DoesNotExist:
            raise ValueError(f"Контракт с ID {contract_id} не найден")

        # Проверяем, что контракт подписан
        if not contract.signed_at:
            raise ValueError("Нельзя создать вывод средств для неподписанного контракта")

        # Проверяем наличие активного вывода средств
        active_withdrawal = CreditWithdrawal.objects.filter(
            contract=contract,
            status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]
        ).first()

        # if active_withdrawal:
        #     raise ValueError("Для контракта уже существует активный запрос на вывод средств")

        # Получаем платежный метод (карту)
        try:
            payment_method = BankCard.objects.get(id=payment_method_id)

            # Проверяем соответствие карты данным из выписки, если передан personal_record
            if personal_record:
                cls.validate_card_with_statement(personal_record, payment_method)

        except BankCard.DoesNotExist:
            raise ValueError(f"Банковская карта с ID {payment_method_id} не найдена")

        # Проверяем баланс перед созданием вывода средств
        if not cls._check_sufficient_balance(contract.params.principal):
            raise ValueError("Недостаточно средств для вывода")

        # Создаем новую запись вывода средств
        withdrawal = CreditWithdrawal.objects.create(
            contract=contract,
            amount=contract.params.principal,
            status=WithdrawalStatus.PENDING
        )

        # Инициируем вывод средств через сервис DirectWithdrawalService
        try:
            service = ExternalService.objects.filter(
                service_class__contains='DirectWithdrawalService',
                is_active=True
            ).first()

            if not service:
                service = cls._get_default_withdrawal_service()

            # Генерируем order_id для вывода средств, если он еще не создан
            if not withdrawal.order_id:
                withdrawal.generate_order_id()
                withdrawal.save(update_fields=['order_id'])

            withdrawal_service = DirectWithdrawalService(
                withdrawal,
                service_model=service,
                payment_method=payment_method
            )
            withdrawal_service.run_service()

            # Обновляем запись из базы данных
            withdrawal.refresh_from_db()
            return withdrawal

        except Exception as e:
            logger.error(f"Ошибка при инициировании вывода средств: {e}", exc_info=True)
            withdrawal.status = WithdrawalStatus.FAILED
            withdrawal.error_message = str(e)
            withdrawal.save(update_fields=['status', 'error_message'])
            raise

    @classmethod
    def _check_sufficient_balance(cls, amount):
        """
        Проверяет, достаточно ли средств для вывода указанной суммы.

        Args:
            amount: Сумма для вывода

        Returns:
            bool: True если достаточно средств, иначе False
        """
        service = ExternalService.objects.filter(
            service_class__contains='WithdrawalBalanceCheck',
            is_active=True
        ).first()

        if not service:
            service = cls._get_default_balance_service()

        try:
            # Создаем экземпляр сервиса для проверки баланса
            balance_check = WithdrawalBalanceCheck(None, service_model=service)
            result = balance_check.run_service()

            # Баланс в центах, переводим в Decimal
            available_balance = Decimal(result.get('balance', 0)) / 100

            logger.info(f"Проверка баланса: доступно {available_balance}, требуется {amount}")

            return available_balance >= amount

        except Exception as e:
            logger.error(f"Ошибка при проверке баланса: {e}", exc_info=True)
            # В случае ошибки считаем, что баланс недостаточен
            return False

    @classmethod
    def _get_default_balance_service(cls):
        """Создает конфигурацию сервиса по умолчанию для проверки баланса."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Withdrawal Balance Service",
            service_class="apps.flow.integrations.external.withdrawal_gateway.WithdrawalBalanceCheck",
            defaults={
                "address": "https://api-gateway.smartcore.pro/withdrawal/balance/get",
                "is_active": True,
                "params": {
                    "withdrawal_account": getattr(settings, "WITHDRAWAL_ACCOUNT", "EUR-sandbox")
                }
            }
        )
        return service

    @classmethod
    def _get_default_withdrawal_service(cls):
        """Создает конфигурацию сервиса по умолчанию для вывода средств."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Direct Withdrawal Service",
            service_class="apps.flow.integrations.external.withdrawal_gateway.DirectWithdrawalService",
            defaults={
                "address": "https://chd-api.smartcore.pro/withdrawal/init",
                "is_active": True,
                "params": {
                    "withdrawal_account": getattr(settings, "WITHDRAWAL_ACCOUNT", "EUR-sandbox"),
                    "merchant_site": getattr(settings, "MERCHANT_SITE_URL", "https://merchant.site")
                }
            }
        )
        return service
