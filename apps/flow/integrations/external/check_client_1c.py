from typing import Optional, TypedDict
import logging

from apps.credits.models import Lead
from apps.flow import RejectReason
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import RejectRequestException
from apps.flow.integrations.request import SoapFetcher
from apps.flow.integrations.serializers import Backend1cCreateClientSerializer

logger = logging.getLogger(__name__)


class ResponseData(TypedDict):
    ClientName: Optional[str]
    LoanAmount: Optional[int]


class CheckClient(BaseService, SoapFetcher):
    """1с МФО - проверка клиента"""
    operation_name = 'CheckClient'
    instance: Lead
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    def conditions(self):
        return bool(self.instance.product.max_loan_amount)

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        return self.fetch(bin=self.instance.borrower.iin)

    def check_rule(self, data: ResponseData):
        loan_amount: Optional[str] = data.get('LoanAmount')

        if loan_amount and loan_amount.isdigit():
            if float(loan_amount) >= self.instance.product.max_loan_amount:
                raise RejectRequestException(RejectReason.UNACCEPTABLE_AMOUNT)
