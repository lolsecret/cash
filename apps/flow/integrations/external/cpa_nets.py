from django.conf import settings

from apps.credits.models import CreditApplication, CreditStatus
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import Fetcher


class LeadSUConversion(BaseService, Fetcher):
    STATUSES = {
        CreditStatus.REJECTED: "rejected",
        CreditStatus.APPROVED: "approved",
        CreditStatus.IN_WORK: "pending"
    }
    instance: CreditApplication

    def run(self):
        return self.fetch(data={
            "token": settings.CPA_TOKEN,
            "goal_id": settings.CPA_GOALID,
            "transaction_id": self.instance.lead.cpa_transaction_id,
            "adv_sub": self.instance.lead_id,
            "status": self.STATUSES.get(self.instance.status, "pending"),
            "comment": ""
        })


class AdimatedConversion(BaseService, Fetcher):
    instance: CreditApplication

    def run(self):
        return self.fetch(data={
            "uid": self.instance.lead.cpa_transaction_id,
            "order_id": self.instance.lead_id,
            "payment_type": "lead",
            "campaign_code": settings.CPA_CAMPAIGN_CODE,
            "action_code": settings.CPA_ACTION_CODE,
            "tariff_code": settings.CPA_TARIFF_CODE,
            "postback": settings.CPA_POSTBACK_CODE,
            "postback_key": settings.CPA_POSTBACK_KEY
        })
