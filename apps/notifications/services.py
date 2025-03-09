from typing import List, Tuple, Union, Optional
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from phonenumbers import PhoneNumber
from django.template import Template, Context

from .exceptions import InvalidOTP, RepeatAgain, GetNewOTP, ExpiredOTP
from .models import OTP, SMSMessage, SMSTemplate, SMSType
from django.db.models import Q

logger = logging.getLogger(__name__)


def send_sms(
        recipients: Union[str, List[str]],
        message: str = "",
        template_name: Union[str, Tuple[str, str]] = None,
        kwargs: dict = None,
        delta: Optional[timedelta] = None,
):
    from .tasks import send_sms_task
    if kwargs is None:
        kwargs = {}

    eta = None  # estimated time of arrival

    if not message:
        if not template_name:
            raise ValueError("Either content or template_name needs to be provided")
        name, created = SMSType.objects.filter(
            Q(pk=template_name) | Q(name=template_name)
        ).get_or_create(defaults={'id': template_name, 'name': template_name})
        message = SMSTemplate.objects.get(name=template_name).content
    message = message.format(**kwargs)

    if not isinstance(recipients, list):
        recipients = [recipients]
    recipients = ";".join(recipients)

    if delta:
        eta = timezone.now() + delta

    with transaction.atomic():
        sms = SMSMessage(recipients=recipients, content=message)
        sms.save()
        transaction.on_commit(lambda: send_sms_task.apply_async(eta=eta, args=[recipients, message, sms.uuid]))


def send_sms_find_template(
        mobile_phone: PhoneNumber,
        template_name: str,
        kwargs: dict = None,
):
    try:
        name, created = SMSType.objects.filter(
            Q(pk=template_name) | Q(name=template_name)
        ).get_or_create(defaults={'id': template_name, 'name': template_name})

        template, created = SMSTemplate.objects.get_or_create(name=name)

        if mobile_phone and template.content:
            send_sms(
                recipients=str(mobile_phone), template_name=template.name, kwargs=kwargs,
            )

    except Exception as exc:
        extra = {'template_name': template_name, 'mobile_phone': mobile_phone, **kwargs}
        logger.error("send_sms_find_template error %s", exc, extra=extra)


def send_otp(mobile_phone: PhoneNumber):
    otp = OTP.generate(mobile_phone)
    send_sms(
        recipients=str(mobile_phone), template_name="OTP", kwargs={"otp": otp},
    )


def verify_otp(code: str, mobile_phone: PhoneNumber, save=False):
    otp = OTP.objects.active().filter(
        mobile_phone=mobile_phone,
        failed_verification_attempts__lte=settings.OTP_MAX_FAILED_VERIFICATION_AMOUNTS
    ).last()
    if otp and otp.code != code:
        otp.update_failed_verification_attempts_amount()

    if otp and otp.code != code and otp.failed_verification_attempts < settings.OTP_MAX_FAILED_VERIFICATION_AMOUNTS:
        raise RepeatAgain
    elif otp and otp.code != code and otp.failed_verification_attempts == settings.OTP_MAX_FAILED_VERIFICATION_AMOUNTS:
        raise GetNewOTP
    elif otp and timezone.now() - otp.created > timedelta(minutes=settings.OTP_VALIDITY_PERIOD):
        raise ExpiredOTP
    if not otp or otp.code != code:
        raise InvalidOTP

    if save:
        otp.verified = True
        otp.save(update_fields=["verified"])

    return True
