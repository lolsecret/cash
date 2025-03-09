from apps.credits.models import CreditApplication
from ..base import BaseService
from ..request import SoapFetcher
from ..serializers import Backend1cCreateGuarantorSerializer


class CreateGuarantor(BaseService, SoapFetcher):
    """1с МФО - создание гаранта"""
    operation_name = 'CreateGuarantor'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        serializer = Backend1cCreateGuarantorSerializer(self.instance.guarantors.first())
        return self.fetch(data=serializer.data)

    def conditions(self):
        return self.instance.has_guarantors()
