import base64
import logging
from datetime import datetime
import math

from django.conf import settings

from apps.credits import PaymentStatus
from apps.credits.models import CreditApplicationPayment
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import Fetcher

logger = logging.getLogger(__name__)


class PaymentGatewayCreateForm(BaseService, Fetcher):
    """
    Integration with SmartPayments payment gateway for creating payment forms.
    """
    instance: CreditApplicationPayment
    method = "POST"

    @property
    def log_iin(self):
        """Return IIN for logging purposes."""
        person = self.instance.person or self.instance.contract.borrower
        return person.iin if person else None

    def get_headers(self):
        """Generate Basic authorization headers."""
        merchant_key = getattr(settings, "MERCHANT_KEY", "microcash")
        merchant_secret = getattr(settings, "MERCHANT_SECRET", "6YW01b36kq8uu2q41n17CPRi2RRt3xJ3")
        print(f'merchant_key: {merchant_key}')
        print(f'merchant_secret: {merchant_secret}')
        auth_string = f"{merchant_key}:{merchant_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        return {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json",
        }

    def run(self):
        """Create a payment form at the payment gateway."""
        # Convert to cents (the payment gateway requires amount in cents)
        amount_in_cents = int(math.floor(self.instance.amount * 10))

        borrower_data = self.instance.contract.credit.borrower_data
        contract = self.instance.contract

        # Prepare request data
        data = {
            "account": 'EUR-sandbox',
            "amount": amount_in_cents,
            "currency": "EUR",
            "order_id": f"credit-{contract.id}-payment-{self.instance.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "merchant_site": getattr(settings, "MERCHANT_SITE_URL", "https://microcash.kz"),
            "recurrent": False,
            "purpose": "Оплата за микрокредит",
            "customer_first_name": borrower_data.first_name or "John",
            "customer_last_name": borrower_data.last_name or "Doe",
            "customer_email": "johndoe@example.com",
            "customer_address": "10 Downing Street",
            "customer_city": "London",
            "customer_zip_code": "121165",
            "customer_country": "KZ",
            "customer_phone": borrower_data.mobile_phone.as_e164,
            "callback_url": settings.PAYMENT_CALLBACK_URL
        }
        print(f'headers: {self.get_headers()}')
        # Make the API request
        return self.fetch(
            url=getattr(settings, "CREATE_PAYMENT_FORM_URL", "https://api-gateway.smartcore.pro/initPayment"),
            headers=self.get_headers(),
            json=data,
        )

    def post_run(self):
        """Save payment form URL and order ID after successful request."""
        if hasattr(self, 'data') and isinstance(self.data, dict):
            # Check for form_url in response
            form_url = self.data.get("form_url")
            if form_url:
                self.instance._pay_link = form_url
                self.instance.order_id = self.data.get("order_id")
                self.instance.payment_response = self.data
                self.instance.save(update_fields=['_pay_link', 'order_id', 'payment_response'])
                logger.info(f"Payment form created for payment_id={self.instance.id}, url={form_url}")


class PaymentGatewayStatusCheck(BaseService, Fetcher):
    """
    Integration with SmartPayments payment gateway for checking payment status.
    """
    instance: CreditApplicationPayment
    method = "POST"

    @property
    def log_iin(self):
        """Return IIN for logging purposes."""
        person = self.instance.person or self.instance.contract.borrower
        return person.iin if person else None

    def get_headers(self):
        """Generate Basic authorization headers."""
        merchant_key = getattr(settings, "MERCHANT_KEY", "microcash")
        merchant_secret = getattr(settings, "MERCHANT_SECRET", "6YW01b36kq8uu2q41n17CPRi2RRt3xJ3")
        auth_string = f"{merchant_key}:{merchant_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        return {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json",
        }

    def conditions(self):
        """Only run if we have an order_id to check."""
        return bool(self.instance.order_id)

    def run(self):
        """Check payment status at the payment gateway."""
        data = {
            "order_id": self.instance.order_id
        }

        return self.fetch(
            url=getattr(settings, "CHECK_PAYMENT_STATUS_URL", "https://api-gateway.smartcore.pro/check"),
            headers=self.get_headers(),
            json=data,
        )

    def post_run(self):
        """Update payment status based on the gateway response."""
        if hasattr(self, 'data') and isinstance(self.data, dict):
            # Get status code from response
            status_code = self.data.get("status")
            if status_code is not None:
                # Map SmartPayments status to our status
                old_status = self.instance.status
                new_status = None

                if status_code == 2:
                    new_status = PaymentStatus.PAID
                elif status_code == 1:
                    new_status = PaymentStatus.IN_PROGRESS
                elif status_code == 0:
                    new_status = PaymentStatus.WAITING
                elif status_code == -1:
                    new_status = PaymentStatus.PAYMENT_ERROR

                if new_status and new_status != old_status:
                    self.instance.status = new_status
                    self.instance.payment_response = self.data
                    self.instance.save(update_fields=['status', 'payment_response'])

                    logger.info(
                        f"Payment {self.instance.id} status updated: {old_status} -> {new_status}"
                    )

                    # If payment is now paid, we might want to trigger additional processes
                    if new_status == PaymentStatus.PAID:
                        # Process successful payment
                        # This could emit a signal or call another service
                        pass
