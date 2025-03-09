import logging
from enum import IntEnum

from requests import Response

from apps.credits.models import Lead, ServiceReason, CreditReport
from apps.flow import RejectReason
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import DataLoader
from apps.flow.integrations.exceptions import RejectRequestException

from .serializers import PKBCustomScoringSerializer

logger = logging.getLogger(__name__)

NO_CREDIT_HISTORY = -2007


class PKBStatus(IntEnum):
    NOT_FOUND = 0
    FOUND = 1


class PKBCustomScoring(BaseService, DataLoader):
    """Кастомный Скоринг МФО Quantum. Модель 2"""
    instance: Lead
    save_serializer = PKBCustomScoringSerializer

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def conditions(self):
        credit_report = self.get_credit_report()
        return credit_report is not None and (
                bool(credit_report.soho_id_query) or bool(credit_report.behavior_id_query)
        )

    def run(self):
        logger.info("запрос на получение кастомного скоринга для iin %s", self.instance.borrower.iin)
        credit_report = self.get_credit_report()
        query_iq = credit_report.soho_id_query or credit_report.behavior_id_query
        return self.fetch(
            json={
                'iin': self.instance.borrower.iin,
                'qid': query_iq,
            }
        )

    def handle_400(self, response: Response):
        result = response.json()
        if 'code' in result and result['code'] == NO_CREDIT_HISTORY:
            return response.json()
        return super().handle_400(response)

    # def fetch(self, params=None, data=None, json=None, **kwargs):
    #     # Mock
    #     return {
    #         "code": -2007,
    #         "message": "Указан несуществующий или неверный ID/ИИН/БИН",
    #         "verbose": {
    #             "request": None,
    #             "response": "{\"code\":-2007,\"message\":\"Указан несуществующий или неверный ID/ИИН/БИН\"}"
    #         }
    #     }
    #     # return {'id': '920929300344', 'name': '',
    #     #         'flags': {'f1': 1, 'f2': 1, 'f3': 0, 'f4': 1, 'f5': 0, 'f6': 0, 'f7': 1},
    #     #         'timestamp': '2021-01-18T11:49:59+06:00', 'qid': 31296}

    def prepared_data(self, data: dict) -> dict:
        return {
            'custom_scoring_flags': data.get('flags')
        }

    def get_credit_report(self):
        credit_report, created = CreditReport.objects.get_or_create(lead=self.instance)
        return credit_report

    get_instance = get_credit_report

    def check_rule(self, data: dict):
        if isinstance(data, dict):
            code = data.get('code')
            if code == NO_CREDIT_HISTORY:
                """Нет кредитной истории"""
                return

            # patterns = ServiceReason.objects.by_service(self.service)
            patterns = self.instance.product.reject_reasons.filter(service=self.service, is_active=True)
            flags = data.get('flags')
            if isinstance(flags, dict):
                for category, value in data.get('flags').items():  # type: str, int
                    if category.startswith('f'):
                        reason_found = next(filter(lambda reason: reason.key == category, patterns), None)
                        if value == PKBStatus.FOUND and reason_found:
                            self.instance.credit_report.custom_scoring_reason_found.add(reason_found)

            if self.instance.credit_report.custom_scoring_reason_found.exists():
                raise RejectRequestException(RejectReason.REJECT_FOR_CUSTOM_SCORING)
