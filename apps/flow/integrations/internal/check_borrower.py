from apps.credits.models import Lead, Product
from apps.people import Gender

from apps.flow import RejectReason
from apps.flow.integrations.base import InternalCheckRuleService
from apps.flow.integrations.exceptions import RejectRequestException


class CheckBorrower(InternalCheckRuleService):
    """Проверки возвраста по иин"""
    instance: Lead

    def check_rule(self, data=None):
        if self.instance.product:
            product: Product = self.instance.product

            if (
                self.instance.borrower == Gender.MALE and
                product.age_limits_male
            ) and self.instance.borrower.age not in product.age_limits_male:
                raise RejectRequestException(RejectReason.AGE_RESTRICTION_FOR_MEN)

            elif product.age_limits_female and self.instance.borrower.age not in product.age_limits_female:
                raise RejectRequestException(RejectReason.AGE_RESTRICTION_FOR_WOMEN)

    def run(self):
        pass
