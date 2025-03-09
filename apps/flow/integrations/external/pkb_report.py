import logging

from django.core.files.base import ContentFile
from django.db.models import Model

from apps.credits.models import CreditApplication, Guarantor
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import DataLoader
from .serializers import CreditReportSerializer, CreditReportGuarantorSerializer

logger = logging.getLogger(__name__)


class PKBReport(BaseService, DataLoader):
    """ПКБ Кредитный отчет"""

    instance: CreditApplication
    save_serializer = CreditReportSerializer

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        logger.info("запрос на пкб отчет заемщика iin %s", self.instance.borrower.iin)
        return self.fetch(
            json={"iin": self.instance.borrower.iin},
        )

    def post_run(self):
        try:
            url = self.service.address + '/pdf'
            session = self.session
            # Удалим сохранение запроса в лог
            self._session.hooks['response'] = []

            response = session.get(url, params={'iin': self.instance.borrower.iin})
            if response.status_code == 200:
                self.instance.credit_report.pkb_credit_report.save('report.pdf', content=ContentFile(response.content))

        except Exception as exc:
            logger.error('download pkb_credit_report error %s', exc)
            logger.exception(exc)
