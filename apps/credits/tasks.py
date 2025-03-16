import logging

from celery import shared_task
from celery.exceptions import Ignore
from constance import config
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mass_mail
from django.template import Context, Template

from apps.credits.models import CreditApplication, DocumentType, CreditDocument, CreditApplicationPayment, \
    CreditContract
from apps.credits.models.notifications import EmailNotification
from apps.credits.services.payment_service import PaymentService
from apps.credits.services.soap_payment_service import SoapPaymentService
from apps.credits.views import print_forms_pdf_view
from apps.users.models import User
from config import celery_app

logger = logging.getLogger(__name__)


@shared_task
def send_email_notification(credit_id: int, status: str) -> None:
    credit = CreditApplication.objects.get(id=credit_id)
    messages = []
    email_notifications = EmailNotification.objects.filter(status=status)

    if email_notifications.exists():
        for notification in email_notifications:
            template = Template(notification.text).render(Context({'credit': credit}))
            messages.append((
                notification.subject,
                template,
                config.EMAIL_HOST_USER,
                list(User.objects.filter(is_active=True, role=notification.role).values_list("email", flat=True))
            ))

        try:
            send_mass_mail(tuple(messages), fail_silently=False)

        except Exception as exc:
            logger.error(
                "tasks.send_email_notification error %s", exc,
                extra={'credit_id': credit_id, 'status': credit.status}
            )


@celery_app.task()
def generate_and_save_credit_documents(credit_id: int) -> None:
    credit = CreditApplication.objects.get(id=credit_id)
    template_names = {
        "credit-contract": "CREDIT_AGREEMENT",
        "schedule-payments": "CREDIT_AGREEMENT",
        "credit-application": "STATEMENT",
        "committee-protocol": "CREDIT_COMMITTEE_DECISION"
    }
    for template in template_names:
        document_type, _ = DocumentType.objects.get_or_create(code=template_names[template])

        print_form = print_forms_pdf_view(
            request=None,
            pk=credit.pk,
            form_name=template,
        )
        document_file = ContentFile(print_form.getvalue(), name=f"{template}-{credit.pk}.pdf")

        CreditDocument.objects.create(
            credit=credit,
            document_type=document_type,
            document=document_file,
        )


@celery_app.task
def check_payments_status():
    """
    Periodic task to check payment statuses and update them in the database.

    This task should be scheduled to run at regular intervals (e.g., every 5 minutes)
    to keep payment statuses up to date.
    """
    logger.info("Starting periodic payment status check")
    try:
        PaymentService.check_payment_status_and_send_callback()
        logger.info("Payment status check completed successfully")
    except Exception as e:
        logger.error(f"Error during payment status check: {e}", exc_info=True)
