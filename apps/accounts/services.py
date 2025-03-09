import logging
from typing import Optional
from datetime import date
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Transport
from zeep.client import Client as SoapClient
from zeep.helpers import serialize_object

from django.conf import settings
from django.core.cache import cache

from .models import Profile
from . import serializers

logger = logging.getLogger(__name__)


class AccountService:
    def get_client(self) -> SoapClient:  # noqa
        session = Session()
        session.auth = HTTPBasicAuth(settings.ACCOUNT_INFO_1C_USERNAME, settings.ACCOUNT_INFO_1C_PASSWORD)
        return SoapClient(
            wsdl=settings.ACCOUNT_INFO_1C_WSDL,
            transport=Transport(session=session),
        )

    def get_client_info(
            self, *,
            iin: str,
            phone: str,
            date_from: Optional[date] = None,
            date_to: Optional[date] = None,
            cache_timeout: int = 3 * 60 * 60,
            force=False,
    ) -> Optional[dict]:
        """GetClientInfo
        @param iin: иин заемщика
        @param phone: моб. телефон заемщика
        @param date_from:
        @param date_to:
        @param cache_timeout: время кеша в секундах
        @param force: принудительное обновление данных
        """
        cache_key = "account_info-{}-{}".format(iin, phone)
        if date_from and date_to:
            cache_key += "-{}-{}".format(date_from, date_to)

        # Проверим в кеше данные по клиенту
        data = cache.get(cache_key)
        if data and not force:
            # Если данные устарели, выполним в фоне обновление данных
            if cache.ttl(cache_key) > 300:
                from .tasks import update_client_info
                update_client_info.delay(iin=iin, phone=phone, date_from=date_from, date_to=date_to, force=True)

            return data

        client = self.get_client()

        params = {
            "bin": iin,
            "tel_number": phone,
            "PrepaymentDate1": date_from,
            "PrepaymentDate2": date_to,
        }
        logger.info("1c call method GetClientInfo iin %s", iin, extra={"params": params})

        try:
            response = client.service.GetClientInfo(**params)

            if hasattr(response, 'Результат') and not response.Результат:
                logger.error(
                    "1c call method GetClientInfo error response %s", response.ОписаниеОшибки,
                    extra={"params": params}
                )
                return None

        except Exception as exc:
            logger.error("1c call method GetClientInfo error %s", exc, extra={"params": params})
            return None

        # Сохраним в кеш на 15 мин
        data = serialize_object(response)
        if data:
            cache.set(cache_key, data, cache_timeout)

        return data

    def info(
            self, *,
            user: Profile,
            date_from: Optional[date] = None,
            date_to: Optional[date] = None,
    ):
        """Получение информации о клиенте в 1С по иин и телефону"""
        data = None

        # Выполним запрос в 1С
        try:
            data = self.get_client_info(
                iin=user.person.iin,
                phone=user.phone.as_e164,
                date_from=date_from,
                date_to=date_to
            )

        except Exception as exc:
            logger.error("AccountService.info error %s", exc)

        serializer = serializers.AcoountInfoSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def payment_history(self, *, iin: str, phone: str):
        # Выполним запрос в 1С
        data = self.get_client_info(iin=iin, phone=phone)
        payment_history_data = data.get('PaymentHistory').get('PaymentHistoryLine')
        payment_history_data = sorted(payment_history_data, key=lambda item: item['targetDates'], reverse=True)

        serializer = serializers.PaymentHistorySerializer(data=payment_history_data, many=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data
