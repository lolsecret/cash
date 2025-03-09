import hashlib
import hmac
from datetime import datetime
import requests
from django.conf import settings

from apps.credits.models import CreditApplication
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import Fetcher


class VerigramBiometric(BaseService, Fetcher):  # noqa
    """Verigram compare photos"""
    operation_name = 'ComparePhoto2'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def get_headers(self, token): # noqa
        return {
            "X-Verigram-Access-Token": token.get('access_token'),
            "X-Verigram-Person-Id": token.get('person_id'),
            "X-Verigram-Api-Version": "1.1"
        }

    def run(self):
        biometric_images = self.instance.init_biometry_photos()
        token = get_verigram_access_token(self.instance.lead.uuid).json()
        headers = self.get_headers(token)

        files = {
            "photo": open(biometric_images.borrower_photo.path, 'rb'),
            "doc": open(biometric_images.document_photo.path, 'rb'),
        }
        return self.fetch(headers=headers, files=files)

    def save(self, prepared_data):
        biometry_photos_instance = self.instance.init_biometry_photos()
        biometry_photos_instance.similarity = prepared_data["Similarity"]
        biometry_photos_instance.save(update_fields=["similarity"])


class Veriface(BaseService, Fetcher):  # noqa
    """Verigram veriface service"""
    operation_name = 'Veriface'
    instance: CreditApplication
    wsdl_cache = 3600 * 72
    transport_timeout = 300

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def get_headers(self, token): # noqa
        return {
            "X-Verigram-Access-Token": token.get('access_token'),
            "X-Verigram-Person-Id": token.get('person_id'),
        }

    def run(self):
        biometric_images = self.instance.init_biometry_photos()
        token = get_verigram_access_token(self.instance.get_reference()).json()
        headers = self.get_headers(token)

        files = {
            "verif": open(biometric_images.borrower_photo.path, 'rb'),
            "enroll": open(biometric_images.document_photo.path, 'rb'),
        }
        return self.fetch(headers=headers, files=files)

    def save(self, prepared_data):
        biometry_photos_instance = self.instance.init_biometry_photos()
        biometry_photos_instance.similarity = prepared_data["score"]
        biometry_photos_instance.save(update_fields=["similarity"])



def get_verigram_access_token(id): # noqa
    api_key = settings.API_KEY
    api_secret = settings.API_SECRET

    ts = int(datetime.now().timestamp())
    path = f"/resources/access-token?person_id={id}"
    signable_str = f"{ts}{path}"

    hmac_digest = hmac.new(api_secret.encode("utf-8"),
                           msg=signable_str.encode("utf-8"),
                           digestmod=hashlib.sha256).hexdigest()
    headers = {
        "X-Verigram-Api-Version": "1.1",
        "X-Verigram-Api-Key": api_key,
        "X-Verigram-Hmac-SHA256": hmac_digest,
        "X-Verigram-Ts": str(ts)
    }

    url = settings.VERIGRAM_TOKEN_URL + path
    response = requests.get(url=url, headers=headers)
    return response
