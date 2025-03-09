from apps.credits.models import CreditApplication
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import SoapFetcher
from apps.flow.integrations.serializers import Backend1cCreateClientSerializer


class CreateClient(BaseService, SoapFetcher):
    """1с МФО - создание клиента"""
    operation_name = 'CreateClient'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        serializer = Backend1cCreateClientSerializer(self.instance)
        return self.fetch(data=serializer.data)
