import logging
from enum import IntEnum

from apps.credits.models import Lead
from apps.flow import RejectReason
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import RejectRequestException
from apps.flow.integrations.request import DataLoader

logger = logging.getLogger(__name__)


class PKBStatus(IntEnum):
    FOUND = 1
    NOT_FOUND = 2
    UNKNOWN = 3


class PKBAdditional(BaseService, DataLoader):
    """ПКБ Доп. источники"""
    endpoint = "pkb_additional"
    instance: Lead

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self) -> dict:
        logger.info("запрос на получение данных их пкб доп. источников для iin %s", self.instance.borrower.iin)
        return self.fetch(
            json={'iin': self.instance.borrower.iin, 'full_name': self.instance.borrower_data.full_name}
        )

    def check_rule(self, data: dict):
        credit_report = self.instance.get_credit_report()
        product = self.instance.product
        patterns = product.reject_reasons.filter(service=self.service)
        for item in data['data']['sources']:
            if isinstance(item, list):
                item = item[0]

            reason_found = next(filter(lambda reason: reason.key == item.get('code'), patterns), None)
            status = item.get('status')
            if reason_found and status == PKBStatus.FOUND:
                credit_report.pkb_additional_reason_found.add(reason_found)

        if credit_report.pkb_additional_reason_found.exists():
            result = credit_report.pkb_additional_reason_found.all()
            logger.warning("Объект %s найден в ПКБ доп источниках %s", self.instance, result)
            raise RejectRequestException(RejectReason.REJECT_ADDITIONAL_SOURCES)

