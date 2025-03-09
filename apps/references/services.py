import logging
import os
import warnings
from typing import Optional
import time
from datetime import date
from urllib.parse import urljoin

from django.conf import settings
from requests import Session, JSONDecodeError

from .models import BlackListMember, Region
from .tasks import load_from_excel_ips
from .utils import extract_excel_ips, get_filename_zip

with warnings.catch_warnings(record=True):
    warnings.simplefilter("always")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

logger = logging.getLogger(__name__)


def person_in_blacklist(
        iin: str,
        birthday: date = None,
        first_name: str = None,
        last_name: str = None,
        middle_name: str = None,
):
    if BlackListMember.objects.filter(iin=iin).exists():
        return True
    if first_name:
        return BlackListMember.objects.filter(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            birthday=birthday,
        ).exists()
    return False


class ExceededLimitException(Exception):
    """Exceeded the limit of 1 requests per minute"""


class SyncIPService:
    BASE_URL = "https://old.stat.gov.kz"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "referer": "https://old.stat.gov.kz/jur-search/filter",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "authority": "old.stat.gov.kz",
        "sec-ch-ua": "\"Chromium\";v=\"118\", \"Google Chrome\";v=\"118\", \"Not=A?Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Linux\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin"
    }

    def __init__(self) -> None:
        self.session = Session()
        self.session.headers.update(self.HEADERS)

    def url(self, path: str):
        return urljoin(self.BASE_URL, path)

    def get_kato(self):
        logger.info("SyncIPService.sync start region code list")

        response = self.session.get(self.url("/api/klazz/213/741880/ru"))

        if not response.ok:
            logger.error("SyncIPService.get_kato: response.text: %s", response.text)
            raise Exception("get_kato request error %s" % response.status_code)

        data = response.json()
        if 'success' in data and data['success']:
            for item in data['list']:
                Region.objects.create(
                    name=item['name'],
                    code=item['code'],
                    region_id=item['itemId'],
                    is_active=True,
                )
        logger.info("SyncIPService.sync ended region code list")

    def request_kato(self, region: Region):
        """Создаем запрос на получение отчета по выбранному региону"""
        logger.info("SyncIPService.request_kato start region %s", region.name)

        request_data = {"conditions": [{"classVersionId": 2153, "itemIds": [742681]},
                                       {"classVersionId": 213, "itemIds": [region.region_id]},
                                       {"classVersionId": 1989, "itemIds": [39354, 39355, 39356]}],
                        "cutId": 773,
                        "stringForMD5": "string"}

        response = self.session.post(self.url("/api/sbr/request/?gov"), json=request_data)

        try:
            response_data = response.json()

        except JSONDecodeError:
            if 'Exceeded the limit of' in response.text:
                raise ExceededLimitException

            raise

        except Exception as exc:
            raise exc

        if response_data['success']:
            repeat = 0

            # Раз в 5 сек проверяем готовность отчета, макс попыток 5
            while True:
                result: Optional[dict] = self.check_file(response_data)
                if result or repeat > 5:
                    logger.info("SyncIPService.check_file: result %s repeat %s", result, repeat)
                    break

                repeat += 1
                time.sleep(5)

            if result:
                self.parse_file(region, result)

        logger.info("SyncIPService.request_kato ended region %s", region.name)

    def check_file(self, data: dict):
        # {"success":true,"obj":"4402bf78-8827-4c96-b603-eb00794dda5c","description":null}
        # https://old.stat.gov.kz/api/sbr/requestResult/8c5b17f8-1da8-4ea7-9b0e-84571908a2fc/ru
        url = self.url("/api/sbr/requestResult/{}/ru".format(data['obj']))
        response = self.session.get(url)

        data = response.json()

        if data['success'] and data['description'] == 'Обработан':
            return data['obj']

    def parse_file(self, region: Region, data: dict):
        # https://old.stat.gov.kz/api/sbr/download?bucket=SBR_UREQUEST&guid=6543253ded47ae00013f4ac4
        url = self.url("/api/sbr/download?bucket={bucket}&guid={fileGuid}".format(**data))
        zip_filename = self.download_file(url)
        logger.info("SyncIPService.download_file: download success %s", zip_filename)

        # Распакуем архив
        excel_ips_filename = extract_excel_ips(zip_filename)
        logger.info("SyncIPService.extract_excel_ips: success %s", excel_ips_filename)

        load_from_excel_ips(excel_ips_filename, region_id=region.id)
        logger.info("SyncIPService.parse_file: ended %s", excel_ips_filename)

    def download_file(self, url):
        with self.session.get(url, stream=True, verify=False) as response:
            response.raise_for_status()

            filename = get_filename_zip(response.headers.get('content-disposition'))
            local_filename = os.path.join(settings.MEDIA_ROOT, filename)

            with open(local_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return local_filename

    @staticmethod
    def sync():
        from .tasks import ip_sync_from_site
        regions = Region.objects.filter(is_active=True)
        for idx, region in enumerate(regions):
            ip_sync_from_site.apply_async(args=(region.id,), countdown=idx * 90)
