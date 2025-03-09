from apps.credits import CreditStatus
from apps.credits.models import Lead
from apps.flow.integrations.base import InternalCheckRuleService


class CreditToWork(InternalCheckRuleService):
    """Перевод кредитной заявки в работу"""
    instance: Lead

    def run(self):
        credit = self.instance.credit

        # Заявку переводим в работу
        if credit.status == CreditStatus.IN_PROGRESS:
            credit.to_work()
            credit.save()

        # Проверки по лидам завершены
        self.instance.done()
        return True
