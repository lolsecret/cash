import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.credits.models import CreditApplication, Lead
from apps.flow import ServiceStatus
from apps.flow.integrations.base import BaseService
from apps.flow.integrations.exceptions import ServiceErrorException
from apps.flow.integrations.request import Fetcher

logger = logging.getLogger(__name__)


class VeragramSigning(Fetcher, BaseService):
    """Сервис подписания документов через Verigram FLOW"""
    instance: CreditApplication
    save_response = True
    timeout = (15, 300)  # Увеличенный таймаут для операций подписания

    @property
    def log_iin(self):
        return self.instance.borrower.iin

    def _generate_headers(self, path: str) -> Dict[str, str]:
        """Генерация заголовков с HMAC подписью"""
        timestamp = int(datetime.now().timestamp())
        signable_str = f"{timestamp}{path}"
        hmac_digest = hmac.new(
            settings.API_SECRET.encode("utf-8"),
            msg=signable_str.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        return {
            "X-Verigram-Api-Version": "2.0.0",
            "X-Verigram-Api-Key": settings.API_KEY,
            "X-Verigram-Hmac-SHA256": hmac_digest,
            "X-Verigram-Ts": str(timestamp),
            "Content-Type": "application/json",
        }

    def upload_file(self, file_content, filename: str) -> Dict[str, Any]:
        """Загрузка файла в хранилище Verigram"""
        path = "/resources/storage"
        url = f"{self.service.address}{path}"
        headers = self._generate_headers(path)
        # Удаляем Content-Type из заголовков, так как будем использовать multipart/form-data
        headers.pop("Content-Type", None)

        files = {
            "upload_file": (filename, file_content),
        }

        data = {
            "label": "unspecified",
            "person_id": self.instance.borrower.iin,
        }

        # Используем self.fetch вместо прямого вызова requests
        response = self.fetch(
            url=url,
            method="POST",
            headers=headers,
            files=files,
            data=data
        )

        return response

    def mock_kisc(self) -> bool:
        """
        Создает мок KISC для тестирования Flow без реального соединения с ЦОИД

        Использует Verigram mockery API для создания заглушки KISC сервиса,
        следуя точно такому же подходу, как в примере Verigram
        """
        try:
            path = "/mockery/result"
            url = f"{self.service.address}{path}"
            headers = self._generate_headers(path)

            # Пути к файлам
            base_dir = Path.cwd()
            assets_dir = base_dir / "assets"

            kisc_result_path = assets_dir / "kisc_result.json"
            kisc_pii_path = assets_dir / "kisc_pii.txt"

            logger.info(f"Using result file: {kisc_result_path}")
            logger.info(f"Using PII file: {kisc_pii_path}")

            # Проверяем наличие файлов
            if not kisc_result_path.exists():
                # Создаем файл kisc_result.json с нужным форматом
                logger.info(f'IIN type: {type(self.instance.borrower.iin)}')
                mock_result = {
                    "person_id": self.instance.borrower.iin,
                    "result": {
                        "service_name": "kisc",
                        "service_status": "success",
                        "face_match": True,
                        "similarity": 99.0,
                        "vendor": "verigram"
                    },
                    "files": {
                        "kisc_pii": "@kisc_pii.txt",
                        "kisc_face_image": ""
                    }
                }
                with open(kisc_result_path, 'w') as f:
                    json.dump(mock_result, f, indent=2)
                    logger.info(f"Created kisc_result.json file")

            # Загружаем данные из файла kisc_result.json
            with open(kisc_result_path, "r") as f:
                data = json.load(f)

                # Устанавливаем правильный person_id
                data["person_id"] = self.instance.borrower.iin

                # Обрабатываем файлы, указанные в data['files']
                for key, value in data['files'].items():
                    if isinstance(value, str) and value.startswith("@"):
                        # Получаем путь к файлу
                        file_path = value[1:]  # Убираем @ из начала

                        # Если это относительный путь, преобразуем в абсолютный
                        if not Path(file_path).is_absolute():
                            file_path = assets_dir / file_path

                        logger.info(f"Processing file: {file_path}")

                        if Path(file_path).exists():
                            # Кодируем файл в base64
                            with open(file_path, "rb") as file:
                                file_content = file.read()
                                data['files'][key] = base64.b64encode(file_content).decode("utf-8")
                                logger.info(f"Encoded file {file_path}, length: {len(data['files'][key])}")
                        else:
                            logger.warning(f"File not found: {file_path}")

            # Отправляем запрос с использованием self.fetch
            logger.info(f"Sending KISC mock request for IIN: {self.instance.borrower.iin}")

            response = self.fetch(
                url=url,
                method="POST",
                headers=headers,
                json=data
            )

            # Проверяем статус ответа
            logger.info(f"KISC mock response status: {response.get('status_code', 'unknown')}")

            # Проверяем, успешно ли выполнен запрос
            # Предполагаем, что ответ успешный, если не было исключения
            logger.info("KISC mock created successfully")
            return True

        except Exception as e:
            logger.error(f"Error mocking KISC: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def create_flow(self, callback_url: str, files: Dict[str, Any]) -> Dict[str, Any]:
        """Создание Flow для подписания документа"""
        path = "/flow"
        url = f"{self.service.address}{path}"
        headers = self._generate_headers(path)

        input_data = {
            "iin": self.instance.borrower.iin,
            "phone_number": str(self.instance.lead.mobile_phone),
            "files": files,
        }
        pipeline = [
            {"service_name": "consent"},
            {"service_name": "verilive", "native": False, "max_retries": 3, "timeout": 300},
            {"service_name": "kisc"},  # KISC для получения данных из ЦОИД
            {"service_name": "client-card"},  # Создание карточки клиента
            {"service_name": "doc-preview", "files": ["input_files", "client-card"]},
            {
                "service_name": "esign",
                "action": "issue",
                "skip_exists": True
            },
            {
                "service_name": "esign",
                "action": "sign",
                "files": ["input_files", "client-card"],
                "forgot_password_option": True
            }
        ]

        data = {
            "person_id": self.instance.borrower.iin,
            "callback_url": callback_url,
            "locale": "ru",
            "input_data": input_data,
            "template": {
                "pipeline": pipeline,
                "ui": {
                    "logo_url": settings.COMPANY_LOGO_URL if hasattr(settings, 'COMPANY_LOGO_URL') else "",
                }
            }
        }

        logger.info(f"Creating flow for IIN: {self.instance.borrower.iin}")

        # Используем self.fetch вместо requests.post
        response = self.fetch(
            url=url,
            method="POST",
            headers=headers,
            json=data
        )

        return response

    def get_flow_result(self, flow_id: str) -> Dict[str, Any]:
        """Получение результата Flow"""
        path = f"/flow/{flow_id}/result"
        url = f"{self.service.address}{path}"
        headers = self._generate_headers(path)

        # Используем self.fetch вместо requests.get
        response = self.fetch(
            url=url,
            method="GET",
            headers=headers
        )

        return response

    def get_signed_file(self, flow_id: str) -> bytes:
        """Получение подписанного файла"""
        # Включаем параметры прямо в путь для правильной генерации подписи
        path = f"/resources/file?label=signed_doc&flow_id={flow_id}"
        url = f"{self.service.address}{path}"
        print(f'urll: {url}')
        # Генерируем заголовки с учетом полного пути, включая параметры запроса
        headers = self._generate_headers(path)
        print(f'headers: {headers}')
        # Используем self.fetch без отдельных params
        response = self.fetch(
            url=url,
            method="GET",
            headers=headers
        )

        if isinstance(response, dict) and response.get('error_code'):
            logger.error(f"Error getting signed file: {response}")
            raise ServiceErrorException(f"Error getting signed file: {response}")

        # Возвращаем содержимое (возможно, потребуется дополнительная обработка)
        return response

    def get_response(self, response):
        """
        Переопределяем метод из Fetcher для правильной обработки ответов
        """
        if response.headers.get('content-type') == 'application/pdf':
            return response.content  # Возвращаем бинарные данные
        try:
            return response.json()  # Пробуем вернуть JSON
        except ValueError:
            return response.text  # Если не JSON, возвращаем текст

    def run(self) -> Dict[str, Any]:
        """Основной метод для запуска процесса подписания"""
        try:
            # Получаем договор для подписания
            from apps.credits.views import print_forms_pdf_view
            contract_pdf = print_forms_pdf_view(None, self.instance.pk, "credit-contract")

            # Загружаем договор в Verigram
            filename = f"contract-{self.instance.id}.pdf"
            upload_result = self.upload_file(contract_pdf.getvalue(), filename)
            file_id = upload_result.get("session_id")

            # Формируем данные о файлах для Flow
            files = {
                "doc_preview": [{"filename": "Договор займа", "file_id": file_id}],
                "esign": [{"filename": "Договор займа", "file_id": file_id}]
            }

            # Создаем мок для KISC перед созданием Flow
            mock_result = self.mock_kisc()
            logger.info(f"KISC mock created: {mock_result}")

            # Создаем Flow для подписания
            callback_url = f"{settings.BASE_URL}/credits/api/signing/callback/{self.instance.pk}/"
            flow_result = self.create_flow(callback_url, files)

            # Сохраняем ссылку на Flow и Flow ID
            self.instance.verigram_flow_id = flow_result.get('flow_id')
            self.instance.verigram_flow_url = flow_result.get('vlink')
            self.instance.save(update_fields=['verigram_flow_id', 'verigram_flow_url'])

            # Устанавливаем Flow как успешно запущенный
            self.status = ServiceStatus.WAS_REQUEST

            # Вызываем log_save чтобы сохранить историю
            self.log_save()

            return flow_result

        except Exception as exc:
            logger.error(f"Error initiating signing flow: {str(exc)}")
            self.status = ServiceStatus.REQUEST_ERROR
            # Всё равно пытаемся сохранить историю с ошибкой
            self.log_save()
            raise ServiceErrorException(exc)

    @staticmethod
    def process_signed_document(credit: CreditApplication, flow_id: str) -> bool:
        """Обработка подписанного документа"""
        try:
            # Получаем активный сервис
            service = VeragramSigning.find_active_service()

            # Создаем экземпляр сервиса для кредитной заявки
            service_instance = VeragramSigning(instance=credit, service_model=service)

            # Получаем информацию о Flow
            flow_result = service_instance.get_flow_result(flow_id)
            print(f'flow_result: {flow_result}')
            # Проверяем статус Flow
            if flow_result.get('flow_status') != 'pass' or flow_result.get('end_cause') != 'completed':
                logger.error(f"Flow completed with errors: {flow_result}")
                return False

            # Получаем подписанный документ
            signed_content = service_instance.get_signed_file(flow_id)

            # Сохраняем подписанный документ в кредитную заявку
            from apps.credits.models import DocumentType, CreditDocument
            document_type = DocumentType.objects.get(code='SIGNED_AGREEMENT')

            # Создаем запись о документе
            credit_doc = CreditDocument.objects.create(
                credit=credit,
                document_type=document_type
            )

            # Сохраняем файл
            document_file = ContentFile(signed_content)
            print(f'document_file: {document_file}')
            credit_doc.document.save(f"signed_contract_{credit.pk}.pdf", document_file)
            # Обновляем статус кредитной заявки
            # credit.sign_with_otp(otp="verigram")
            # credit.to_issuance(signed_at=timezone.now().date(), otp="verigram")
            # credit.save()

            return True

        except Exception as exc:
            logger.error(f"Error processing signed document: {str(exc)}")
            return False

    @classmethod
    def find_active_service(cls):
        """Находит активный сервис для подписания Verigram"""
        from apps.flow.models import ExternalService
        return ExternalService.by_class(cls)

    @classmethod
    def _generate_instance(cls, credit: CreditApplication):
        """Создает экземпляр сервиса для указанной кредитной заявки"""
        service = cls.find_active_service()
        return cls(instance=credit, service_model=service)
