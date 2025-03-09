import logging

from lxml import etree

from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import DataLoader, SoapFetcher
from apps.flow.integrations.serializers import PersonalDataSerializer, PersonSerializer
from apps.credits.models import Lead
from apps.people.utils import convert_gender_from_gbdfl

logger = logging.getLogger(__name__)

# города республиканского значения
CITIES = ('АЛМАТЫ', 'НУР-СУЛТАН', 'ШЫМКЕНТ')


class GBDFL(BaseService, DataLoader):
    """Государственная база данных «Физические лица» (ГБД ФЛ)"""
    instance: Lead
    save_serializer = PersonalDataSerializer

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        logger.info("запрос на получение данных физ лица из ГБДФЛ для iin %s", self.instance.borrower.iin)
        return self.fetch(
            json={'iin': self.instance.borrower.iin}
        )

    def get_instance(self):
        return self.instance.borrower_data

    def prepared_data(self, data: dict) -> dict:
        reg_address = data.get('reg_address', {})
        region = reg_address.get('region')
        district = reg_address.get('district')

        if district in CITIES:
            reg_address['city'] = district
            reg_address['district'] = region
            reg_address['region'] = None

        else:
            reg_address['city'] = district
            reg_address['district'] = region
            reg_address['region'] = district

        # Фактическое проживание укажем тот же адрес
        data['real_address'] = reg_address.copy()
        data['same_reg_address'] = True
        return data

    def save(self, data):
        super().save(prepared_data=self.prepared_data(data))

        person = self.get_instance().person
        person.gender = convert_gender_from_gbdfl(data.get('gender'))

        person.save(update_fields=['gender'])


class GBDFLv2(BaseService, SoapFetcher):
    """Государственная база данных «Физические лица» (ГБД ФЛ) V2"""

    operation_name = 'getFamilyInfo'
    instance: Lead
    verify = False

    def get_soap_headers(self):
        params = self.service.params
        if params.get('GBDFL_USER_ID'):
            el = etree.Element("userId")
            el.text = params.get('GBDFL_USER_ID')
            return [el]

        return None

    def run(self):
        return {
            "iin": self.instance.borrower.iin,
            "consentConfirmed": True,
        }
