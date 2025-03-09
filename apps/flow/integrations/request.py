import inspect
from typing import Optional, Tuple, Literal, Union, Any
import logging
import time

import orjson
from lxml import etree
from requests import Session
from requests.models import Response
from requests.exceptions import ConnectionError
from zeep import Client as SoapClient, helpers, exceptions as soap_exceptions

from django.conf import settings

from apps.core.utils import generate_uid
from apps.flow.services.history import BaseHistory
from apps.logger.handlers import DBLogger
from .exceptions import (
    ServiceUnavailable,
    ServiceErrorException,
)
from .utils import SoapLoggingPlugin, create_transport

logger = logging.getLogger(__name__)

HTTP_METHODS = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']


class Fetcher(BaseHistory):
    _session: Optional[Session]
    url: str
    method: HTTP_METHODS = 'POST'
    auth: Optional[Tuple[str, str]]
    cert: Optional[Tuple[str, str]]
    verify: bool = True

    timeout = (15, 60)

    uid: Optional[str]
    log_iin: Optional[str]

    @property
    def session(self) -> Session:
        if not hasattr(self, '_session') or self._session is None:
            self._session = Session()

        self._session.hooks['response'].append(self.history)
        return self._session

    @property
    def request_verify(self) -> bool:
        return getattr(self, 'host_verify', True)

    def fetch(
            self, *,
            url: str = None,
            method: Optional[HTTP_METHODS] = None,
            params: Optional[dict] = None,
            data: Any = None,
            json: Optional[dict] = None,
            headers: Optional[dict] = None,
            verify: bool = False,
            timeout: Optional[Union[float, int]] = None,
            **kwargs
    ):
        resource_name, initiator_name, *others = [stack.function
                                                  for stack in inspect.stack(0)[0:5] if stack.function != 'request']
        method_name = f"({self.__class__.__name__}) [{initiator_name}] {resource_name}"
        extra_log = {
            'uid': self.uid or generate_uid(),
            'conversation_id': generate_uid(),
            'method': method_name,
            'iin': self.log_iin,
        }

        if url:
            self.url = url

        elif self.service.address:
            self.url = self.service.address

        if method is None:
            method = self.method

        if self.service.username and (not headers or isinstance(headers, dict) and 'Authorization' not in headers):
            self.session.auth = (self.service.username, self.service.password)

        if timeout is None:
            timeout = self.timeout

        self.history_url = self.url
        self.history_method = method
        self.last_request = ''

        start = time.perf_counter()

        if method == 'GET':
            content = orjson.dumps(params) if params else None
        else:
            content = orjson.dumps(json) if json else data

        self.logging(content, extra_log={
            **extra_log
        })

        try:
            response_raw = self.session.request(
                method=method,
                url=self.url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                timeout=timeout,
                verify=verify,
                **kwargs,
            )
            logger.info("%s.fetch: status %s", self.__class__.__name__, response_raw.status_code)
            self.logging(response_raw.text, extra_log={
                **extra_log,
                'response_status': response_raw.status_code,
            })

        except ConnectionError as exc:
            logger.error("ConnectionError error %s url %s", exc, self.url)
            self.last_response = str(exc)
            self.logging(self.last_response, extra_log={
                **extra_log,
            }, is_error=True)
            raise ServiceUnavailable(exc)

        except Exception as exc:
            logger.error("Exception error %s url %s", exc, self.url)
            self.last_response = str(exc)
            self.logging(self.last_response, extra_log={
                **extra_log,
            }, is_error=True)
            raise ServiceErrorException(response=exc)

        finally:
            self.runtime = time.perf_counter() - start

        if response_raw.status_code == 400:
            return self.handle_400(response_raw)

        elif response_raw.status_code in [401, 403]:
            return self.handle_401(response_raw)

        elif response_raw.status_code == 404:
            return self.handle_404(response_raw)

        # save history
        self.history_url = response_raw.request.url
        self.history_method = response_raw.request.method

        return self.get_response(response_raw)

    def get_response(self, response: Response):
        return response.json()

    def handle_400(self, response: Response):
        logger.error("%s.fetch: status %s %s", self.__class__.__name__, response.status_code, response.text)
        raise ServiceErrorException(response.json())

    def handle_401(self, response: Response):
        logger.error("%s.fetch: status %s %s", self.__class__.__name__, response.status_code, response.text)
        raise ServiceErrorException(response.json())

    def handle_404(self, response: Response):
        logger.error("%s.fetch: status %s %s", self.__class__.__name__, response.status_code, response.text)
        raise ServiceErrorException(response.json())

    def history(self, response: Response, *args, **kwargs):
        self.last_request = response.request.body
        self.last_response = response.text

    # noinspection PyMethodMayBeStatic
    def logging(
            self,
            content,
            extra_log: dict,
            is_error: bool = False,
    ):
        if is_error:
            DBLogger.error(content or '', **extra_log)

        else:
            DBLogger.info(content or '', **extra_log)


class DataLoader(Fetcher):
    base = settings.DATALOADER_URL
    endpoint: str

    def fetch(self, params=None, data=None, json=None, **kwargs):
        # Add logging request from dataloader
        params = {'verbose': True}
        return super().fetch(params=params, data=data, json=json, **kwargs)

    def history(self, response: Response, *args, **kwargs):
        try:
            logger.info('history code=%s size=%s', response.status_code, len(response.text))
            logger.info("content-type: %s", response.headers['content-type'])
            content_type = response.headers.get('content-type', 'html')
            if 'json' in content_type or 'html' in content_type:
                data = response.json()
                if 'verbose' in data:
                    verbose: dict = data.pop('verbose', {})
                    if verbose:
                        self.history_url = verbose.pop('url', None)
                        self.history_method = verbose.pop('method', None)
                        self.last_request = verbose.pop('request', None)
                        self.last_response = verbose.pop('response', None)

        except Exception as exc:
            logger.error("error save request history %s", exc)
            logger.exception(exc)

    def get_response(self, response: Response):
        data: dict = response.json()
        if 'verbose' in data:
            data.pop('verbose')

        return data


class SoapFetcher(BaseHistory):
    wsdl = None
    wsdl_cache: Optional[int] = None
    auth: Optional[Tuple[str, str]] = None
    cert: Optional[Tuple[str, str]] = None
    verify: bool = True
    transport_timeout = 60
    transport_operation_timeout = 60

    operation_name: Optional[str] = None

    _client: Optional[SoapClient] = None
    history = None
    runtime = 0

    uid: Optional[str]
    log_iin: Optional[str]

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
            )

        return self._client

    # noinspection PyMethodMayBeStatic
    def get_soap_headers(self):
        return None

    def fetch(self, **params):
        resource_name, initiator_name, *others = [stack.function
                                                  for stack in inspect.stack(0)[0:5] if stack.function != 'request']
        method_name = f"({self.__class__.__name__}) [{resource_name}] {self.operation_name}"

        extra_log = {
            'uid': self.uid or generate_uid(),
            'conversation_id': generate_uid(),
            'method': method_name,
            'iin': self.log_iin,
        }

        log_extra = {
            'service.address': self.service.address,
            'service.username': self.service.username,
            'operation_name': self.operation_name,
        }

        try:
            node = self.client.create_message(self.client.service, self.operation_name, **params)
            self.logging(etree.tostring(node), extra_log={
                **extra_log,
            })

            if self.get_soap_headers():
                self.client.set_default_soapheaders(self.get_soap_headers())

            start = time.perf_counter()
            response = self.client.service[self.operation_name](**params)

            self.logging(self.history.last_received, extra_log={
                **extra_log,
                'response_status': 200,
            })

            self.runtime = round(time.perf_counter() - start, 3)
            self.prepare_history()

            try:
                return helpers.serialize_object(response)
            except Exception as exc:
                logger.error("SoapFetcher.fetch: serialize_object error %s", exc, extra=log_extra)

            return response

        except soap_exceptions.Fault as exc:
            logger.error("SoapFetcher.fetch: fault %s", exc, extra=log_extra)
            self.prepare_history()
            self.logging(self.history.last_received, extra_log={
                **extra_log,
                'response_status': 400,
            }, is_error=True)
            # return exc
            raise ServiceErrorException

        except Exception as exc:
            logger.error("SoapFetcher.fetch: error %s", exc, extra=log_extra)
            self.logging(self.history.last_received, extra_log={
                **extra_log,
                'response_status': 500,
            }, is_error=True)
            raise ServiceUnavailable

    # noinspection PyMethodMayBeStatic
    def logging(
            self,
            content,
            extra_log: dict,
            is_error: bool = False,
    ):
        if is_error:
            DBLogger.error(content or '', **extra_log)

        else:
            DBLogger.info(content or '', **extra_log)

    def prepare_history(self):
        self.history_url = self.service.address
        self.history_method = self.operation_name
        self.last_request = self.history.last_sent
        self.last_response = self.history.last_received
