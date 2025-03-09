from typing import Optional, Tuple
import logging
from urllib.parse import urljoin

from constance import config

from apps.credits.models import CreditApplication
from apps.flow import ServiceStatus
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import ServiceErrorException
from apps.flow.integrations.request import Fetcher

logger = logging.getLogger(__name__)


class KISCBiometric(Fetcher, BaseService):
    """Сервис КЦМР для версии 1.1.0"""

    instance: CreditApplication

    VERSION = '/identity/1.1.0'

    @property
    def cert(self) -> Optional[Tuple[str, str]]:
        params = self.service.params
        return params.get('cert'), params.get('key')

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def run(self):
        extra_log = {'iin': self.instance.borrower.iin, 'vendor': config.KISC_IDENTITY_VENDOR}
        logger.info("Kisc identity request started", extra=extra_log)

        headers = {
            "x-idempotency-key": self.request_id,
            "Content-Type": "image/png",
        }

        try:
            params = {
                "iin": self.instance.borrower.iin,
                "vendor": config.KISC_IDENTITY_VENDOR,
            }

            biometry_photo = self.instance.init_biometry_photos()
            logger.info("borrower_photo: credit %s borrower_photo %s", self.instance, biometry_photo)

            return self.fetch(
                url=urljoin(self.service.address, f'{self.VERSION}/verify'),
                params=params,
                data=biometry_photo.borrower_photo.read(),
                headers=headers,
                cert=self.cert,
                verify=False,
            )

        except Exception as exc:
            logger.error("Kisc identity error request %s", exc, extra=extra_log)
            raise ServiceErrorException(exc)

    def save(self, prepared_data: dict):
        logger.info("kisc.save result %s", prepared_data)

        if isinstance(prepared_data, dict):
            biometry_photo = self.instance.biometry_photos.latest('pk')
            biometry_photo.similarity = round(prepared_data.get('result', 0), 3)
            biometry_photo.vendor = f"KISC({prepared_data.get('vendor')})"
            biometry_photo.query_id = prepared_data.get('x_idempotency_key')
            biometry_photo.save(update_fields=['similarity', 'vendor', 'query_id'])

    def get_vendors(self):
        """
        Пример запроса на получение списка вендеров get_vendors()
            service = ExternalService.by_class(KISCBiometric)
            kisc_service = KISCBiometric(credit, service_model=service)
            kisc_service.get_vendors()
        """
        self.data = self.fetch(
            url=urljoin(self.service.address, f'{self.VERSION}/vendors'),
            method='GET',
            cert=self.cert,
            verify=False,
            timeout=5,
        )
        logger.info("KISCBiometric.get_vendors:", self.data)

        # save history
        self.status = ServiceStatus.WAS_REQUEST
        self.log_save()

        return self.data
