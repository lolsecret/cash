from apps.credits.models import Lead, CreditApplication, BusinessInfo
from apps.flow.integrations.base import InternalCheckRuleService


class CreateCreditFromLead(InternalCheckRuleService):
    """Создать кредит из лида"""
    instance: Lead

    def run(self):
        credit: CreditApplication = CreditApplication.objects.create_from_lead(self.instance)

        # Заявку переводим в работу
        credit.to_work()
        credit.save()


        self.instance.done()
        return True
