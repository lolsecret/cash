from hashlib import md5
from typing import Optional
from io import BytesIO
import logging
from uuid import uuid4
from urllib.parse import urljoin

import requests
from django.core.cache import cache
from django.core.files.base import ContentFile
from requests import Response

from apps.credits.models import CreditApplication
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.request import Fetcher

logger = logging.getLogger(__name__)


# noinspection PyAbstractClass
class PKBFcbIdFetcher(Fetcher):
    PREFIX_CACHE_KEY = "fcb-id-service:"
    TOKEN_CACHE_KEY = PREFIX_CACHE_KEY + "token:"

    HEADERS = {
        "Content-Type": "application/json; charset=utf-8",
    }

    service_login_url = "/fcbid-otp/api/v1/login"

    instance: CreditApplication

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    @property
    def token(self) -> Optional[str]:
        token = cache.get(self.TOKEN_CACHE_KEY + "access")
        if not token:
            token_data = self.login()

            access_token = token_data['access']
            refresh_token = token_data['refresh']

            # save in cache
            self.save_token("access", access_token['hash'], ttl=access_token['ttl'])
            self.save_token("refresh", refresh_token['hash'], ttl=refresh_token['ttl'])

            token = access_token['hash']
            logger.info("get new token %s", md5(token.encode()).hexdigest())

        return token

    def save_token(self, key, token: str, ttl: int = 3600):
        """Вычислим время хранения токена в кеше"""
        logger.info("%s token setter", self.__class__.__name__)
        cache.set(self.TOKEN_CACHE_KEY + key, token, ttl)

    @property
    def token_hash(self) -> str:
        return md5(self.token.encode()).hexdigest()

    def login(self) -> dict:
        logger.info("%s.login: request access token", self.__class__.__name__, extra=self.extra_log)

        try:
            response = requests.get(
                url=urljoin(self.service.address, self.service_login_url),
                auth=(self.service.username, self.service.password),
                headers={"Content-Type": "application/json; charset=utf-8"},
                verify=False,
            )
            return response.json()

        except Exception as exc:
            logger.error("%s.login: request error %s", self.__class__.__name__, exc, extra=self.extra_log)
            raise exc

    @property
    def extra_log(self) -> dict:
        return {
            "iin": self.instance.borrower.iin,
            "uid": self.request_id,
        }

    def new_request_id(self):
        cache_key = self.PREFIX_CACHE_KEY + f"request_id:{self.instance.borrower.iin}"
        request_id = str(uuid4())
        cache.set(cache_key, request_id, 60 * 15)  # 15 minutes
        return request_id

    def get_request_id(self):
        cache_key = self.PREFIX_CACHE_KEY + f"request_id:{self.instance.borrower.iin}"
        if request_id := cache.get(cache_key):
            return request_id

        logger.error("%s.get_request_id: error request_id expired time", self.__class__.__name__)
        raise ValueError("request_id not found")


class PKBFCBIdOTPService(PKBFcbIdFetcher, BaseService):
    """Запрос на отправку кода от 1414."""
    service_url = "/fcbid-otp/api/v1/send-code"

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            'RequestID': self.new_request_id(),
        }

    def run(self):
        logger.info(
            "PKBFCBIdOTPService.run: запрос на отправку egov otp для iin %s",
            self.instance.borrower.iin, extra=self.extra_log
        )

        headers = self.headers

        data = {
            "iin": self.instance.borrower.iin,
            "phone": self.instance.lead.mobile_phone.as_e164[1:]
        }

        try:
            return self.fetch(
                url=urljoin(self.service.address, self.service_url),
                headers=headers,
                json=data,
            )

        except Exception as exc:
            extra = {**self.extra_log, "headers": headers, "data": data, "token": self.token_hash}
            logger.error(
                "PKBFCBIdOTPService.run: ошибка запроса egov otp для iin %s",
                self.instance.borrower.iin, extra=extra
            )
            raise exc


class PKBFCBIdDocService(PKBFcbIdFetcher, BaseService):
    """ПКБ цифровые документы получение фото удл"""
    service_url = "/fcbid-otp/api/v1/get-pdf-document"

    def __init__(self, *, code_egov=None, **kwargs):
        super().__init__(**kwargs)
        self.code = code_egov

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            'RequestID': self.get_request_id(),
        }

    def run(self) -> Optional[dict]:
        logger.info(
            "PKBFCBIdDocService.run: запрос на получение удл для заемщика %s",
            self.instance.borrower.iin, extra=self.extra_log
        )

        borrower_data = self.instance.borrower_data

        last_name = (borrower_data.last_name or '').lower().capitalize()
        first_name = (borrower_data.first_name or '').lower().capitalize()
        middle_name = (borrower_data.middle_name or '').lower().capitalize()

        headers = self.headers

        data = {
            "code": self.code,
            "ciin": self.instance.borrower.iin,  # noqa
            "first_name": first_name,
            "last_name": last_name,
            "middle_name": middle_name,
        }

        try:
            return self.fetch(
                url=urljoin(self.service.address, self.service_url),
                headers=headers,
                json=data,
            )

        except Exception as exc:
            extra = {**self.extra_log, "headers": headers, "data": data, "token": self.token_hash}
            logger.error(
                "PKBFCBIdDocService.run: ошибка запроса на получение удл для заемщика %s",
                self.instance.borrower.iin, extra=extra
            )
            raise exc

    def get_response(self, response: Response) -> BytesIO:
        if response.headers.get('content-type') == 'application/pdf':
            return BytesIO(response.content)

        return response.json()

    def history(self, response: Response, *args, **kwargs):
        self.last_request = response.request.body

        if response.headers.get('content-type') == 'application/json':
            self.last_response = response.text

    def save(self, document_data: BytesIO):
        try:
            iin = self.instance.borrower.iin

            biometry_photo = self.instance.init_biometry_photos()
            logger.info("biometry_photo: save data %s", biometry_photo.pk)

            document_file = ContentFile(document_data.getvalue(), f"id-doc-{iin}.pdf")

            biometry_photo.document_file = document_file
            biometry_photo.save(update_fields=["document_file"])

        except Exception as exc:
            logger.error("PKBFCBIdDocService.save: error %s", exc, extra=self.extra_log)
