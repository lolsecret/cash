import base64
import json
import logging
import typing
from abc import ABC, abstractmethod
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils import timezone

from apps.credits import PaymentStatus
from apps.credits.services.soap_payment_service import SoapPaymentService
from apps.flow.integrations import PaymentPayRequestService
from apps.flow.models import ExternalService

if typing.TYPE_CHECKING:
    from apps.credits.models import CreditApplicationPayment

logger = logging.getLogger(__name__)


class PaymentIntegration:
    def __get__(self, instance, owner):
        payment_class = SmartBilling(instance)
        return payment_class


class BaseBilling(ABC):
    url: str

    def __init__(
            self,
            payment: "CreditApplicationPayment",
    ):
        self.payment = payment

    def fetch_data(self) -> typing.Dict[str, typing.Any]:
        return {}

    @property
    def session(self, prepared_data: dict = None) -> requests.Session:
        _session = requests.Session()
        return _session

    @abstractmethod
    def create_payment(self):
        """Метод для геренации ссылки оплаты"""

    @abstractmethod
    def check_status(self):
        """Проверка статуса оплаты"""

    @abstractmethod
    def refund(self):
        """Возврат платежа"""

    @abstractmethod
    def cancel(self):
        """Отмена платежа"""


class SmartBilling(BaseBilling):
    url = ""

    def __init__(self, payment: "CreditApplicationPayment"):
        super(SmartBilling, self).__init__(payment)
        self._pay_link = None

    @property
    def pay_link(self):
        if self._pay_link is None:
            raise ValueError("Значение атрибута `_pay_link` не долен быть пустым")
        return self._pay_link

    @pay_link.setter
    def pay_link(self, value: str) -> None:
        self._pay_link = value

    @property
    def fetch_data(self) -> typing.Dict[str, typing.Any]:
        return {
            # "acquirer_id": settings.SMART_BILLING_ACQUIRER,
            # "terminal_id": settings.SMART_BILLING_TERMINAL,
            "new_payment_type": True,
            "order_id": str(self.payment.order_id),
            "amount": str(self.payment.amount),
            "currency": "KZT",
            "description": f"По Договору №  {self.payment.contract_number}",
            "redirect": False,
            "back_url": settings.PAYMENT_BACK_URL
        }

    def session(self, prepared_data: dict = None) -> requests.Session:
        from nacl.bindings import crypto_sign
        _session = super(SmartBilling, self).session
        data = json.dumps(prepared_data).encode("utf-8")
        k = base64.b64decode(settings.SMART_BILLING_PRIVK)
        check_sum = base64.b64encode(crypto_sign(data, k).rstrip(data))
        _session.headers = {
            "auth-identifier": settings.SMART_BILLING_API_KEY,
            "x-auth-checksum": check_sum.decode("utf-8"),
        }
        _session.verify = settings.DEBUG

        return _session

    def create_payment(self):
        url = urljoin(self.url, "payments")
        session = self.session(self.fetch_data)
        resp = session.post(url, json=self.fetch_data)
        logger.info(
            'SmartBilling create_payment: headers: %s, body: %s, content: %s',
            resp.request.headers, resp.request.body, resp.content
        )
        logger.info(
            f'SmartBilling create_payment: request: %s, %s, %s',
            resp.request.headers, resp.request.body, resp.content
        )

        resp.raise_for_status()
        response_data = resp.json()
        logger.info('SmartBilling create_payment: response_data: %s', response_data)
        self.payment._pay_link = response_data["url"]
        self.payment.hash = response_data["payment"]["hash"]
        self.payment.save(update_fields=["_pay_link", "hash"])
        return resp

    def refund(self):
        pass

    def cancel(self):
        pass

    def check_status(self):
        url = urljoin(self.url, "payments/status")
        data = dict(hash=self.payment.hash)
        session = self.session(data)
        resp = session.patch(url, json=data)
        logger.info(
            'SmartBilling check_status: request: %s, %s, %s',
            resp.request.headers, resp.request.body, resp.content
        )
        # resp.raise_for_status()
        response_data = resp.json()
        logger.info('SmartBilling check_status: response_data: %s', response_data)
        return response_data


class PaymentService:
    @staticmethod
    def check_payment_status_and_send_callback():
        from apps.credits.models import CreditApplicationPayment

        try:
            payments_query = CreditApplicationPayment.objects.filter(
                status=PaymentStatus.NOT_PAID,
                contract_number__isnull=False,
                created__gte=timezone.now() - timezone.timedelta(minutes=60)
            )
            for payment in payments_query:
                response_data = payment.payment_class.check_status()
                logger.info(
                    'check_payment_status_and_send_callback: '
                    'Payment № %s check_status response: %s;',
                    payment.id, response_data
                )

                if response_data.get('payment'):
                    status = response_data['payment']['status']
                    contract = payment.contract
                    soap_service = SoapPaymentService(contract)
                    contract_data = dict(
                        contract_number=payment.contract_number,
                        contract_date=payment.contract_date,
                        payment_amount=payment.amount,
                        iin=payment.person.iin,
                        payment_hash=payment.hash,
                    )
                    if status == 'completed':
                        try:
                            service = ExternalService.by_class(PaymentPayRequestService)
                            response = service.run_service(payment)
                            response_code, comment = int(response.get('result')), response.get('comment')
                            if response.get('result') == 0:
                                payment.status = PaymentStatus.PAID
                                payment.save(update_fields=['status'])

                            logger.info(
                                'check_payment_status_and_send_callback: '
                                'Payment № %s send_pay_request data: %s;'
                                'response: code %s, comment %s',
                                payment.id, contract_data, response_code, comment
                            )
                        except Exception as e_send:
                            logger.error(
                                'Error in send_pay_request for Payment № %s: %s',
                                payment.id, str(e_send),
                                extra={'error_source': 'send_pay_request'}
                            )
                    elif status == 'canceled':
                        payment.status = PaymentStatus.CANCELED
                        payment.save(update_fields=['status'])

        except Exception as e_main:
            logger.error(
                'Error in check_payment_status_and_send_callback: %s',
                str(e_main),
                extra={'error_source': 'check_payment_status_and_send_callback'}
            )
