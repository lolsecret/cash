from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import SoapFetcher
from zeep import Settings
from zeep import Client as SoapClient

from apps.flow.integrations.serializers import BackendPaymentPayRequestSerializer
from apps.flow.integrations.utils import create_transport, SoapLoggingPlugin


class PaymentPayRequestService(BaseService, SoapFetcher):
    """1с - Сервис по обработке платежей"""
    operation_name = 'payment'
    instance: 'CreditApplicationPayment'
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def client(self) -> SoapClient:
        if not self._client:
            self.history = SoapLoggingPlugin()

            if self.service.username and self.service.password:
                self.auth = (self.service.username, self.service.password)

            transport = create_transport(
                auth=self.auth,
                cert=self.cert,
                verify=self.verify,
                cache=self.wsdl_cache,
                transport_timeout=self.transport_timeout,
                transport_operation_timeout=self.transport_operation_timeout,
            )
            self._client = SoapClient(
                wsdl=self.service.address,
                transport=transport,
                plugins=[self.history],
                settings=Settings(strict=False, xml_huge_tree=True)
            )

        return self._client

    @property
    def log_iin(self):
        return self.instance.contract.borrower.iin

    def run(self):
        serializer = BackendPaymentPayRequestSerializer(self.instance.contract, context={'payment': self.instance})
        return self.fetch(Data=serializer.data)
