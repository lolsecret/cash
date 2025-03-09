import logging
from uuid import uuid4

from constance import config
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Profile
from apps.credits.models import CreditApplication
from apps.flow.api.services import pkb_biometry_check
from apps.flow.integrations.external.pkb_fcbid import PKBFCBIdOTPService, PKBFCBIdDocService
from apps.flow.models import ExternalService
from apps.flow.api.tasks import convert_pdf_to_image

logger = logging.getLogger(__name__)


class VerifyPersonService:
    """Сервис проверки биометрии заемщика при регистрации в ЛК"""

    def __init__(self, *, credit: CreditApplication, account: Profile) -> None:
        self.credit = credit
        self.account = account

    @staticmethod
    def send_code(credit: CreditApplication):
        logger.info("Egov send_code process start credit %s", credit.pk)

        try:
            try:
                service_pkb_fcbid_otp = ExternalService.by_class(PKBFCBIdOTPService)

            except Exception as exc:
                logger.error("Service PKBFCBIdOTPService does not exist credit %s error %s", credit.pk, exc)
                raise ValidationError({"detail": "service not found"})

            if config.TEST_EGOV_CODE:
                logger.info("VerifyPersonService.send_code test egov sms code %s", config.TEST_EGOV_CODE)
                return

            # Запрос на отправку egov кода заемщику
            service_pkb_fcbid_otp.run_service(credit)

        except Exception as exc:
            logger.error("VerifyPersonService.send_code error %s", exc, extra={'credit': credit.pk})
            raise exc

    def get_document_from_pkb_fcb(self, *, code_egov: str):
        """Метод получение цифровых документов PKB
        Для получение необходим 6-ти значный код полученный через смс от eGov 1414.
        """
        logger.info("Service PKBFcbIdDoc process start credit %s", self.credit.pk)

        try:
            try:
                service_pkb_fcbid_doc = ExternalService.by_class(PKBFCBIdDocService)

            except Exception as exc:
                logger.error("Service PKBFCBIdDocService does not exist credit %s error %s", self.credit.pk, exc)
                raise ValidationError({"detail": "service not found"})

            if config.TEST_EGOV_CODE and bool(self.account.personal_record.id_document_pdf):
                if config.TEST_EGOV_CODE != code_egov:
                    raise Exception("invalid sms code")

                logger.info("VerifyPersonService.run test get borrower document %s", config.TEST_EGOV_CODE)
                self.credit.biometry_photos.document_photo = self.account.personal_record.id_document_pdf
                self.credit.biometry_photos.save(update_fields=['document_photo'])
                return

            # Получение удл заемщика
            service_pkb_fcbid_doc.run_service(
                self.credit,
                kwargs=dict(code_egov=code_egov),
            )
            convert_pdf_to_image(self.credit.init_biometry_photos().pk)

        except Exception as exc:
            logger.error("Service PKBFCBIdDocService credit %s error %s", self.credit.pk, exc)
            raise ValidationError({"detail": "service error"})

    @staticmethod
    def run(
            *,
            credit: CreditApplication,
            account: Profile,
            selfie_account: bytes,
            code_egov: str,
            new_password: str,
    ):
        logger.info("VerifyPersonService run credit %s account %s", credit, account.phone)

        personal_record = account.personal_record
        # Сохраним последнее селфи заемщика при регистрации
        personal_record.save_selfie(selfie_account)

        service = VerifyPersonService(credit=credit, account=account)

        biometry_data = credit.init_biometry_photos()
        biometry_data.borrower_photo.save(f"borrower_photo-{uuid4()}.jpg", selfie_account)

        # Пытаемся получить цифровые удл сохраним в credit.biometry_photos.document_photo
        service.get_document_from_pkb_fcb(code_egov=code_egov)

        # Check biometry
        # TODO: нужно отправить фейковые данные для теста
        pkb_biometry_check(credit)

        # Если прошли биометрию успешно, тогда регистрируем пользователя и сохраним новый пароль
        account.register_completed()
        account.set_password(new_password)
        account.save(update_fields=["password", "last_login"])
