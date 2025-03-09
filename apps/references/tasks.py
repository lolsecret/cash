import os
import random
import time
import logging
from itertools import islice

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout

from django.conf import settings
from django.db import transaction

from config import celery_app
from .models import IndividualProprietorList, Region

from .utils import import_blacklist_from_xml, ReadExcelIPs, ips_download_file, extract_excel_ips

logger = logging.getLogger(__name__)


@celery_app.task(
    name="references.load_from_egov",
    autoretry_for=(ConnectionError, HTTPError, Timeout),
    retry_backoff=20,
    retry_kwargs={"max_retries": 10},
    ignore_result=True,
)
def load_blacklist_from_egov():
    response = requests.get(settings.EGOV_BLACKLIST_XML_URL, verify=False)
    if response.status_code != requests.codes.ok:
        raise HTTPError(response.text)
    return import_blacklist_from_xml(response.text)


@celery_app.task(bind=True, max_retry=5, soft_time_limit=300)
def ip_sync_from_site(self, region_id: int):
    from .services import SyncIPService, ExceededLimitException
    region = Region.objects.get(pk=region_id)
    service = SyncIPService()
    try:
        service.request_kato(region=region)

    except ExceededLimitException as exc:
        countdown = random.randint(90, 300)
        logger.info("ip_sync_from_site region %s retry %s", region.name, countdown)
        self.retry(countdown=countdown, exc=exc)


@celery_app.task()
def download_ips_from_url_task(url):
    # Скачиваем zip архив
    zip_filename = ips_download_file(url)
    logger.info("ips_download_file: download success %s", zip_filename)

    # Распакуем архив
    excel_ips_filename = extract_excel_ips(zip_filename)
    logger.info("extract_excel_ips: success %s", excel_ips_filename)

    # Парсим excel файл
    load_from_excel_ips.delay(excel_ips_filename)


@celery_app.task()
def load_from_excel_ips(file_path, region_id: int):
    region = Region.objects.get(pk=region_id)

    if not os.path.isfile(file_path):
        logger.error("load_from_excel_ips: file not found %s", file_path)
        raise Exception("file not found")

    with ReadExcelIPs(file=file_path) as parser:
        parser.parse()

        length_results = len(parser.results)
        if not length_results:
            logger.info("load_from_excel_ips: not results")
            return "not results"

        with transaction.atomic():
            start_time = time.time()

            # IndividualProprietorList.truncate()
            item_deleted, _ = IndividualProprietorList.objects.filter(region_id=region_id).delete()
            logger.info("IndividualProprietorList region %s item_deleted %s", region.name, item_deleted)

            batch_size = 10000
            objs = (IndividualProprietorList(region_id=region_id, **item) for item in parser.results)

            while True:
                batch = list(islice(objs, batch_size))
                if not batch: break  # noqa

                IndividualProprietorList.objects.bulk_create(batch, batch_size)

            # Удаляем скачанный файл
            os.remove(file_path)

            logger.info(
                "load_from_excel_ips: length %s finished... %s",
                length_results, round(time.time() - start_time, 3)
            )
