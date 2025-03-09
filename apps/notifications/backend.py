from typing import Optional, Union, Type, ClassVar
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.utils.module_loading import import_string
from django.core.mail.backends.smtp import EmailBackend
from constance import config
from lxml import etree
from requests import Session
from xmltodict import parse

from zeep import Client

logger = logging.getLogger(__name__)


class CustomEmailBackend(EmailBackend):
    """Backend возможность переопределять настройки почты"""
    def __init__(self, host=None, port=None, username=None, password=None, use_tls=None, fail_silently=False,
                 use_ssl=None, timeout=None, ssl_keyfile=None, ssl_certfile=None, **kwargs):
        if config.EMAIL_HOST: host = config.EMAIL_HOST
        if config.EMAIL_PORT: port = config.EMAIL_PORT
        if config.EMAIL_HOST_USER: username = config.EMAIL_HOST_USER
        if config.EMAIL_HOST_PASSWORD: password = config.EMAIL_HOST_PASSWORD
        if config.EMAIL_USE_TLS: use_tls = config.EMAIL_USE_TLS
        if config.EMAIL_USE_SSL: use_ssl = config.EMAIL_USE_SSL

        self.host = host or settings.EMAIL_HOST
        self.port = port or settings.EMAIL_PORT
        self.username = settings.EMAIL_HOST_USER if username is None else username
        self.password = settings.EMAIL_HOST_PASSWORD if password is None else password
        self.use_tls = settings.EMAIL_USE_TLS if use_tls is None else use_tls
        self.use_ssl = settings.EMAIL_USE_SSL if use_ssl is None else use_ssl
        super().__init__(host, port, username, password, use_tls, fail_silently, use_ssl, timeout, ssl_keyfile,
                         ssl_certfile, **kwargs)


class SmsBackendInterface:
    def send_sms(
            self,
            sender: str,
            recipient: str,
            message: str,
            client_message_id: Optional[Union[int, str]] = None,
            **kwargs
    ):
        raise NotImplementedError()

    def send_sms_batch(
            self,
            *args,
            **kwargs
    ):
        raise NotImplementedError()

    def message_info(self, *args, **kwargs):
        raise NotImplementedError()

    def bulk_message_info(self, *args, **kwargs):
        raise NotImplementedError()


class BaseSmsBackend:
    url: ClassVar[Union[str, None]] = None

    def __init__(
            self,
            username: str,
            password: str,
            message_id:
            Optional[Union[str, int]] = None
    ) -> None:
        self.username = username
        self.password = password
        self.message_id = message_id
        self.client = self._init_client()

    def _init_client(self) -> Union[Client, Session]:
        raise NotImplementedError()


class KazInfoTeh(BaseSmsBackend, SmsBackendInterface):
    url = 'http://isms.center/soap'

    def _init_client(self):
        return Client(self.url)

    def _run_service(self, service, **kwargs):
        kwargs.update({
            'login': self.username,
            'password': self.password
        })
        return self.client.service[service](**kwargs)

    def send_sms(
            self,
            sender: str,
            recipient: str,
            message: str,
            client_message_id: Optional[Union[int, str]] = None,
            msg_type: Optional[int] = 0,
            scheduled: Optional[str] = '',
            priority: Optional[int] = 1
    ):
        sms_type = self.client.get_type('ns0:SMSM')
        params = {
            'recepient': recipient,
            'senderid': sender,
            'msg': message,
            'msgtype': msg_type,
            'scheduled': scheduled,
            'UserMsgID': client_message_id,
            'prioritet': priority
        }
        result = self._run_service('SendMessage', **{'notifications': sms_type(**params)})
        if result.MsgID is not None:
            self.message_id = result.MsgID
        return result

    def send_sms_batch(self, *args, **kwargs):
        pass

    def message_info(self, client_message_id: Optional[Union[str, int]] = None):
        key = 'MsgID'
        message_id = client_message_id or self.message_id
        if client_message_id:
            key = 'UserMsgID'
        sms_type = self.client.get_type('ns0:IDSMS')
        return self._run_service('SendMessage', **{'notifications': sms_type(**{key: message_id})})

    def bulk_message_info(self, *args, **kwargs):
        pass


class SmsTraffic(BaseSmsBackend, SmsBackendInterface):
    url = "https://api.smstraffic.kz/multi.php"

    def _init_client(self) -> Union[Client, Session]:
        session = Session()
        session.headers = {"content_type": "application/x-www-form-urlencoded"}
        return session

    def send_sms(
            self,
            sender: str,
            recipient: str,
            message: str,
            client_message_id: Optional[Union[int, str]] = None,
            **kwargs
    ):
        data = {
            "login": self.username,
            "password": self.password,
            "phones": recipient,
            "message": message,
            "want_sms_ids": 1,
            'rus': 5
        }
        response = self.client.post(urljoin(self.url, "multi.php"), data=data)
        root = etree.fromstring(response.text.encode(encoding="utf-8"))
        try:
            message_infos = root.xpath("./message_infos/message_info") # noqa
            return message_infos[0].findtext("sms_id")

        except Exception as exc:
            logger.error("sms error response %s", exc, extra={'params': data, 'response': response.text})
            raise Exception(response.text)

    def message_info(self, external_id: str):
        data = {  # noqa
            "login": self.username,
            "password": self.password,
            "operation": "status",
            "sms_id": external_id
        }
        response = self.client.post(urljoin(self.url, "multi.php"), data=data)
        root = etree.fromstring(response.text.encode(encoding="utf-8"))
        sms_statuses = root.findtext("./reply/notifications")
        return parse(sms_statuses[0])

    def bulk_message_info(self, external_ids: str):
        data = {  # noqa
            "login": self.username,
            "password": self.password,
            "operation": "status",
            "sms_id": external_ids,
            'rus': 5
        }
        response = self.client.post(urljoin(self.url, "multi.php"), data=data)
        root = etree.fromstring(response.text.encode(encoding="utf-8"))
        sms_statuses = root.findtext("./reply/notifications")
        return parse(sms_statuses)


def sms_backend(*args, **kwargs) -> SmsBackendInterface:
    return import_string(
        settings.SMS_BACKEND
    )(*args, **kwargs)
