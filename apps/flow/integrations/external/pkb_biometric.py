from apps.credits.models import CreditApplication
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.external.serializers import PKBBiometricSerializer
from apps.flow.integrations.request import SoapFetcher


class PKBBiometric(BaseService, SoapFetcher):
    """PKB compare photos"""
    operation_name = 'ComparePhoto2'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    def run(self):
        serializer = PKBBiometricSerializer(self.instance)
        return self.fetch(data=serializer.data)

    def save(self, prepared_data):
        biometry_photos_instance = self.instance.init_biometry_photos()
        biometry_photos_instance.similarity = prepared_data["Similarity"]
        biometry_photos_instance.save(update_fields=["similarity"])
