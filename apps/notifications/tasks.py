from django.conf import settings
from requests.exceptions import ConnectionError, HTTPError, Timeout

from config import celery_app
from .backend import sms_backend

from .models import OTP, SMSMessage


@celery_app.task(
    autoretry_for=(ConnectionError, HTTPError, Timeout),
    default_retry_delay=2,
    retry_kwargs={"max_retries": 5},
    ignore_result=True,
)
def send_sms_task(recipients: str, message: str, message_id: str):
    sms_message = SMSMessage.objects.get(uuid=message_id)
    auth = (settings.SMS_LOGIN, settings.SMS_PASSWORD)

    # params = {"from": settings.INFOBIP_SMS_FROM, "to": recipients, "text": message}

    if settings.SMS_ENABLE:
        sms = sms_backend(*auth)

        try:
            sms_message.external_id = sms.send_sms(
                sender=settings.SMS_SENDER,
                recipient=recipients,
                message=message
            )
            sms_message.save(update_fields=["external_id"])

        except Exception as exc:
            sms_message.error_description = str(exc)
            sms_message.save(update_fields=['error_description'])

        # if "error" in data:
        #     instance: SMSMessage = SMSMessage.objects.get(uuid=message_id)
        #     instance.error_description = data["error"]
        #     instance.error_code = data.get("error_code")
        #     instance.save(update_fields=["error_description", "error_code"])

        return sms_message.external_id


@celery_app.task(ignore_result=True)
def delete_expired_otps():
    return OTP.objects.expired().delete()
