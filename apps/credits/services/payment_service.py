import logging

from django.db.models import Q

from apps.credits import PaymentStatus, WithdrawalStatus
from apps.credits.models import CreditApplicationPayment, CreditWithdrawal
from apps.flow.integrations.external.payment_gateway import (
    PaymentGatewayCreateForm,
    PaymentGatewayStatusCheck
)
from apps.flow.integrations.external.payment_withdraw import WithdrawalGatewayInitiate, \
    WithdrawalGatewayTokenizeForm
from apps.flow.models import ExternalService
from apps.flow.integrations.exceptions import ServiceErrorException, ServiceUnavailable

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
    """
    Сервис для управления процессом вывода средств.
    """

    @classmethod
    def create_tokenize_form(cls, contract_id):
        """
        Создать заявку на вывод средств и форму для токенизации карты.

        Args:
            contract_id: ID кредитного договора

        Returns:
            tuple: (CreditWithdrawal, URL формы токенизации)
        """
        from apps.credits.models import CreditContract

        # Получаем кредитный договор
        try:
            contract = CreditContract.objects.get(id=contract_id)
        except CreditContract.DoesNotExist:
            logger.error(f"Договор с ID {contract_id} не найден")
            raise ValueError(f"Договор с ID {contract_id} не найден")

        # Проверяем, что договор подписан
        if not contract.signed_at:
            logger.error(f"Договор с ID {contract_id} не подписан")
            raise ValueError(f"Нельзя создать вывод средств для неподписанного договора")

        # Проверяем, есть ли уже активный вывод средств
        active_withdrawal = CreditWithdrawal.objects.filter(
            contract=contract,
            status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]
        ).first()

        if active_withdrawal and active_withdrawal.tokenize_form_url:
            # Если уже есть активный вывод с URL формы, возвращаем его
            return active_withdrawal, active_withdrawal.tokenize_form_url

        # Создаем новый вывод средств или используем существующий
        withdrawal = active_withdrawal or CreditWithdrawal.objects.create(
            contract=contract,
            amount=contract.params.principal
        )

        # Получаем сервис токенизации
        service = ExternalService.objects.filter(
            service_class__contains='WithdrawalGatewayTokenizeForm',
            is_active=True
        ).first()

        if not service:
            # Создаем сервис по умолчанию
            service = cls._get_default_tokenize_form_service()

        # Запускаем сервис
        try:
            service_instance = WithdrawalGatewayTokenizeForm(withdrawal, service_model=service)
            service_instance.run_service()

            if not withdrawal.tokenize_form_url:
                raise ValueError("Не удалось получить URL формы токенизации")

            return withdrawal, withdrawal.tokenize_form_url

        except Exception as e:
            logger.error(f"Ошибка при создании формы токенизации: {e}", exc_info=True)
            withdrawal.fail(f"Ошибка: {str(e)}")
            raise ValueError(f"Не удалось создать форму токенизации: {str(e)}")

    @classmethod
    def initiate_withdrawal_after_contract_sign(cls, contract_id):
        """
        Инициировать вывод средств после подписания договора.

        Args:
            contract_id: ID кредитного договора

        Returns:
            bool: True при успехе, False при ошибке
        """
        # Находим активный вывод средств для договора
        withdrawals = CreditWithdrawal.objects.filter(
            contract_id=contract_id,
            status=WithdrawalStatus.PENDING
        )

        if not withdrawals.exists():
            logger.warning(f"Не найден активный вывод средств для договора {contract_id}")
            return False

        withdrawal = withdrawals.first()

        # Проверяем наличие tokenize_transaction_id
        if not withdrawal.tokenize_transaction_id:
            logger.error(f"Для вывода #{withdrawal.id} нет ID транзакции токенизации")
            return False

        # Получаем сервис инициализации вывода
        service = ExternalService.objects.filter(
            service_class__contains='WithdrawalGatewayInitiate',
            is_active=True
        ).first()

        if not service:
            service = cls._get_default_initiate_service()

        # Запускаем сервис
        try:
            service_instance = WithdrawalGatewayInitiate(withdrawal, service_model=service)
            service_instance.run_service()

            # Проверяем статус после запуска
            return withdrawal.status == WithdrawalStatus.PROCESSING

        except Exception as e:
            logger.error(f"Ошибка при инициировании вывода средств {withdrawal.id}: {e}", exc_info=True)
            withdrawal.fail(f"Ошибка: {str(e)}")
            return False

    @classmethod
    def process_callback(cls, order_id, status, data):
        """
        Обработать колбэк от платежной системы.

        Args:
            order_id: ID заказа
            status: Статус операции
            data: Все данные колбэка

        Returns:
            bool: True при успешной обработке
        """
        try:
            withdrawal = CreditWithdrawal.objects.get(order_id=order_id)
        except CreditWithdrawal.DoesNotExist:
            logger.error(f"Вывод средств с order_id={order_id} не найден")
            return False

        # Сохраняем данные колбэка
        withdrawal.withdrawal_response = {
            **(withdrawal.withdrawal_response or {}),
            "callback_data": data
        }

        # Обновляем статус
        if status == 2:  # Успешно завершен
            withdrawal.complete()
            logger.info(f"Вывод средств #{withdrawal.id} успешно завершен")
        elif status == -1:  # Ошибка
            error_message = data.get("err") or "Ошибка при обработке вывода средств"
            withdrawal.fail(error_message)
            logger.error(f"Ошибка вывода средств #{withdrawal.id}: {error_message}")
        else:
            # Оставляем в процессе обработки
            logger.info(f"Вывод средств #{withdrawal.id} в процессе, статус {status}")

        withdrawal.save(update_fields=['withdrawal_response'])
        return True

    # Вспомогательные методы

    @classmethod
    def _get_default_tokenize_form_service(cls):
        """Создать конфигурацию сервиса по умолчанию для формы токенизации."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Withdrawal Tokenize Form Service",
            service_class="apps.flow.integrations.external.withdrawal_gateway.WithdrawalGatewayTokenizeForm",
            defaults={
                "address": "https://api-gateway.smartcore.pro/withdrawal/tokenize-form",
                "is_active": True
            }
        )
        return service

    @classmethod
    def _get_default_initiate_service(cls):
        """Создать конфигурацию сервиса по умолчанию для инициирования вывода."""
        service, created = ExternalService.objects.get_or_create(
            name="Default Withdrawal Initiate Service",
            service_class="apps.flow.integrations.external.withdrawal_gateway.WithdrawalGatewayInitiate",
            defaults={
                "address": "https://chd-api.smartcore.pro/withdrawal/init",
                "is_active": True
            }
        )
        return service
