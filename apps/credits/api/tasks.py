import logging

from django.core.files.base import ContentFile

from apps.credits.models import CreditApplication, DocumentType, CreditDocument
from apps.credits.views import print_forms_pdf_view
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task()
def generate_and_save_guarantor_document(credit_id: int, template_name: str, template_code: str) -> None:
    try:
        credit = CreditApplication.objects.get(id=credit_id)
        document_type, _ = DocumentType.objects.get_or_create(code=template_code)

        print_form = print_forms_pdf_view(
            request=None,
            pk=credit.pk,
            form_name=template_name,
        )

        document_file = ContentFile(print_form.getvalue(), name=f"{template_name}-{credit.pk}.pdf")

        CreditDocument.objects.create(
            credit=credit,
            document_type=document_type,
            document=document_file,
        )

        logger.info("Generated and saved document for credit_id=%s, template_name=%s, template_code=%s",
                    credit_id, template_name, template_code)

    except Exception as exc:
        logger.error("Error generating and saving document: %s", exc, exc_info=True)
