from typing import Optional
import logging

from apps.credits.models import Lead
from apps.flow import RejectReason
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import RejectRequestException
from apps.flow.integrations.request import Fetcher

logger = logging.getLogger(__name__)


class StatGovIP(BaseService, Fetcher):
    """Проверка наличие ИП (stat.gov.kz)"""
    instance: Lead
    method = "GET"

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self) -> Optional[dict]:
        logger.info("запрос на наличие ИП заемщика iin %s", self.instance.borrower.iin)

        return self.fetch(
            params={'lang': 'ru', 'bin': self.instance.borrower.iin}
        )

    def check_rule(self, data: dict):
        if not data['success'] or not data['obj'] or not data['obj']['ip']:
            logger.info("тип заемщика %s не ИП", self.instance.borrower.iin)
            raise RejectRequestException(RejectReason.BORROWER_NOT_ENTREPRENEUR)


# {"conditions":[{"classVersionId":2153,"itemIds":[742681]},{"classVersionId":213,"itemIds":[268020]},{"classVersionId":1989,"itemIds":[39354,39355,39356]}],"cutId":773,"stringForMD5":"string"}
# {"conditions":[{"classVersionId":2153,"itemIds":[742681]},{"classVersionId":213,"itemIds":[250502]},{"classVersionId":1989,"itemIds":[39354,39355,39356]}],"cutId":773,"stringForMD5":"string"}
