import importlib
import logging

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.credits.models import CreditApplication, ApplicationFaceMatchPhoto
from apps.flow.integrations import PKBBiometric, KISCBiometric, Veriface
from apps.flow.models import Pipeline, ExternalService, BiometricConfiguration

logger = logging.getLogger(__name__)


def _get_active_biometry_service() -> ExternalService:
    """Поиск нужного сервиса"""
    # TODO: нужно сделать настройки сервисов
    try:
        biometric_config = BiometricConfiguration.get_solo()

    except Pipeline.DoesNotExist:
        raise ValidationError({"detail": "PIPELINE_NOT_FOUND"})

    if not biometric_config.service:
        raise ValidationError({"detail": "ACTIVE_JOB_NOT_FOUND"})

    return biometric_config.service


def _get_biometry_min_score():
    """???"""
    service = _get_active_biometry_service()
    module_name, class_name = service.service_class.rsplit(".", 1)
    service_class = getattr(importlib.import_module(module_name), class_name)
    biometry_min_scores = {
        Veriface: settings.VERIGRAM_BIOMETRY_MIN_SCORE,
        KISCBiometric: settings.VERIGRAM_BIOMETRY_MIN_SCORE,
        PKBBiometric: settings.VERIGRAM_BIOMETRY_MIN_SCORE,
    }
    return biometry_min_scores[service_class]


def pkb_biometry_check(
        instance: CreditApplication,
        personal_record,
) -> ApplicationFaceMatchPhoto:

    # Инициализируем биометрические данные
    biometry_photos_instance = instance.init_biometry_photos()

    # Добавляем document_photo из personal_record
    if personal_record and personal_record.document_photo:
        biometry_photos_instance.document_photo = personal_record.document_photo
        biometry_photos_instance.save(update_fields=["document_photo"])

    # Запускаем внешний сервис
    service = _get_active_biometry_service()
    service.run_service(instance)

    # Обновляем объект из базы
    biometry_photos_instance.refresh_from_db()
    biometry_min_score = _get_biometry_min_score()

    # Проверяем минимальный коэффициент сходства
    logger.info("pkb_biometry_check: similarity %s", biometry_photos_instance.similarity)
    if biometry_photos_instance.similarity is None or biometry_photos_instance.similarity < biometry_min_score:
        biometry_photos_instance.attempts += 1
        biometry_photos_instance.save(update_fields=["attempts"])

        if biometry_photos_instance.attempts > settings.BIOMETRY_ATTEMPTS_COUNT:
            raise ValidationError({"detail": "Заявка отклонена", "attempts": biometry_photos_instance.attempts})
        else:
            raise ValidationError(
                {"detail": "Нет сходства. Попробуйте еще раз", "attempts": biometry_photos_instance.attempts}
            )

    return biometry_photos_instance
