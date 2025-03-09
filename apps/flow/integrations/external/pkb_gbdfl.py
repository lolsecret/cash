import logging

from apps.accounts.models import Profile, ProfilePersonalRecord
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import DataLoader
from apps.flow.integrations.serializers import PersonalDataSerializer, ProfilePersonalRecordSerializer
from apps.credits.models import Lead
from apps.people.utils import convert_gender_from_gbdfl

logger = logging.getLogger(__name__)

# города республиканского значения
CITIES = ('АЛМАТЫ', 'НУР-СУЛТАН', 'ШЫМКЕНТ')


class PKBGBDFL(BaseService, DataLoader):
    """ПКБ ГБД ФЛ"""
    instance: [ProfilePersonalRecord, Lead]
    timeout = 300

    def run(self):
        iin = self.instance.profile.person.iin if isinstance(self.instance,
                                                             ProfilePersonalRecord) else self.instance.borrower.iin

        return self.fetch(
            json={'iin': iin},
            headers=dict()
        )

    def find_cached_data(self):
        self.save_serializer = ProfilePersonalRecordSerializer if isinstance(
            self.instance, ProfilePersonalRecord) else PersonalDataSerializer
        super().find_cached_data()
        if self.cached_data:
            if isinstance(self.instance, Lead):
                if self.instance.borrower_data.document_number is not None:
                    super().save(prepared_data=self.cached_data)

    def get_instance(self):
        if isinstance(self.instance, ProfilePersonalRecord):
            return self.instance
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
            reg_address['district'] = district
            reg_address['region'] = region

        # Фактическое проживание укажем тот же адрес
        data['real_address'] = reg_address.copy()
        data['same_reg_address'] = True
        if isinstance(self.instance, ProfilePersonalRecord):
            data['profile'] = self.instance.profile.id
        return data

    def save(self, data):
        super().save(prepared_data=self.prepared_data(data))

        person = self.instance.profile.person if isinstance(
            self.instance, ProfilePersonalRecord) else self.instance.borrower
        person.gender = convert_gender_from_gbdfl(data.get('gender'))

        if isinstance(self.instance, ProfilePersonalRecord):
            profile = self.instance.profile
            profile.first_name = self.instance.first_name
            profile.last_name = self.instance.last_name

            profile.save(update_fields=['first_name', 'last_name'])
        person.save(update_fields=['gender'])
