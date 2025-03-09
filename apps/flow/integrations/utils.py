from typing import Optional, Tuple
from lxml import etree
from requests import Session
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from zeep.cache import SqliteCache
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport

from django.conf import settings


def create_transport(
        auth: Optional[Tuple[str, str]] = None,
        cert: Optional[Tuple[str, str]] = None,
        verify: bool = True,
        cache: int = 0,
        transport_timeout: int = None,
        transport_operation_timeout: int = None,
):
    session = Session()
    session.verify = verify
    wsdl_cache = None

    if auth and len(auth) == 2:
        session.auth = HTTPBasicAuth(*auth)

    if cert and len(cert) == 2:
        session.cert = cert

    if isinstance(cache, int) and cache > 0:
        wsdl_cache = SqliteCache(path=settings.SOAP_CACHE_PATH, timeout=cache)

    return Transport(
        session=session,
        cache=wsdl_cache,
        timeout=transport_timeout,
        operation_timeout=transport_operation_timeout,
    )


class SoapLoggingPlugin(HistoryPlugin):
    @staticmethod
    def get_envelope(payload):
        return etree.tostring(payload["envelope"], encoding="unicode")

    @property
    def last_sent(self):
        return SoapLoggingPlugin.get_envelope(super().last_sent)

    @property
    def last_received(self):
        return SoapLoggingPlugin.get_envelope(super().last_received)
