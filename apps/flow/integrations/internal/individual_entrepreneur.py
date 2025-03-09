from apps.credits.models import Lead
from apps.flow import RejectReason
from apps.flow.integrations.base import InternalCheckRuleService
from apps.flow.integrations.exceptions import RejectRequestException
from apps.references.models import IndividualProprietorList


class CheckIndividualEntrepreneur(InternalCheckRuleService):
    """Проверка наличие ИП (внутренний список)"""
    instance: Lead

    def run(self):
        pass

    def check_rule(self, data=None):
        if not IndividualProprietorList.objects.filter(iin=self.instance.borrower.iin).exists():
            raise RejectRequestException(RejectReason.BORROWER_NOT_ENTREPRENEUR)
