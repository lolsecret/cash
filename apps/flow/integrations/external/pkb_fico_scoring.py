import logging
from typing import Optional

from requests import Response

from apps.credits.models import Lead, CreditReport
from apps.flow import RejectReason
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import RejectRequestException
from apps.flow.integrations.request import DataLoader
from .serializers import PKBSohoScoringSerializer

logger = logging.getLogger(__name__)


class PKBFicoScoring(BaseService, DataLoader):
    """ПКБ FICO Scoring"""
    instance: Lead
    save_serializer = PKBSohoScoringSerializer

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self) -> Optional[dict]:
        logger.info("запрос на получение fico балл для заемщика iin %s", self.instance.borrower.iin)
        response = self.fetch(
            json={'iin': self.instance.borrower.iin}
        )
        return response

    def handle_400(self, response: Response):
        logger.error("PKBFicoScoring.handle_400: response error %s", response.text)
        return super().handle_400(response)

    # def fetch(self, params=None, data=None, json=None, **kwargs):
    #     # Mock
    #     return {
    #         "verbose": None,
    #         "iin": "580101414351",
    #         "last_name": "Жапишева",
    #         "first_name": "Бакытжамал",
    #         "middle_name": "Семейхановна",
    #         "risk_class": "I_9",
    #         "bad_rate": "49.2%",
    #         "default_rate": "41.0% - 100.0%",
    #         "ball": 496,
    #         "timestamp": "2021-07-05T08:40:23Z",
    #         "query_date": "2021-07-05T08:40:20Z",
    #         "qid": 164778
    #     }

    def get_instance(self):
        credit_report, created = CreditReport.objects.get_or_create(lead=self.instance)
        return credit_report

    def prepared_data(self, data) -> dict:
        print(f'data: {data}')
        return {
            'soho_id_query': data.get('qid', None),
            'soho_score': data.get('ball'),
        }

    # def check_rule(self, data):
    #     """
    #     Проверяем на минимальный бал SohoScoring
    #     """
    #     if isinstance(data, dict) and data.get('ball', 0) <= self.instance.product.pkb_soho_min_score:
    #         raise RejectRequestException(RejectReason.REJECT_PKB_SOHO)
    #
    #     # self.application.set_recommend_amount(pkb_scoring=data['ball'])

