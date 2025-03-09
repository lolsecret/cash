from apps.credits.models import Lead, CreditApplication
from apps.flow import RejectReason
from apps.flow.integrations.base import InternalCheckRuleService
from apps.flow.integrations.exceptions import RejectRequestException


class ActiveCreditApplications(InternalCheckRuleService):
    """Проверка на наличие активных заявок"""
    instance: Lead

    def run(self) -> dict:
        return {}

    def check_rule(self, data=None):
        active_credits_qs = CreditApplication.objects.for_borrower(self.instance.borrower).active()

        if hasattr(self.instance, 'credit'):
            # Если у лида уже присутствует кредит, исключим из проверки
            if active_credits_qs.exclude(pk=self.instance.credit.pk).exists():
                raise RejectRequestException(RejectReason.DUPLICATE_IN_CRM)

        elif active_credits_qs.exists():
            raise RejectRequestException(RejectReason.DUPLICATE_IN_CRM)
