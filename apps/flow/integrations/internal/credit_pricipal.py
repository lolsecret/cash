from apps.credits.models import Lead, Product
from apps.flow import RejectReason
from apps.flow.integrations.base import InternalCheckRuleService
from apps.flow.integrations.exceptions import RejectRequestException


class CheckCreditPrincipal(InternalCheckRuleService):
    """Проверка допустимой суммы договора"""
    instance: Lead

    def check_rule(self, data=None):
        if self.instance.product:
            product: Product = self.instance.product

            if self.instance.credit_params.principal not in product.principal_limits:
                raise RejectRequestException(RejectReason.UNACCEPTABLE_AMOUNT)

    def run(self):
        pass
