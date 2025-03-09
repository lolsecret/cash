import logging

from apps.credits.models import CreditApplication
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import SoapFetcher

logger = logging.getLogger(__name__)


class GetClientInfo1C(BaseService, SoapFetcher):
    """1с МФО - получение данных клиента"""
    operation_name = 'GetClientInfo'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        iin = self.instance.borrower.iin
        phone = self.instance.lead.mobile_phone.as_e164
        date_from = None
        date_to = None

        return self.fetch(
            bin=iin,
            tel_number=phone,
            PrepaymentDate1=date_from,
            PrepaymentDate2=date_to,
        )
