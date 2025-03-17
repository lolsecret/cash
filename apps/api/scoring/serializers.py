import logging
from typing import Any, Dict

from constance import config
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.core.models import City
from apps.credits import RepaymentMethod
from apps.credits.models import Lead, Product
from apps.flow.services import Flow
from apps.notifications.services import send_otp, verify_otp
from apps.people.exceptions import InvalidIin
from apps.people.validators import IinValidator
from . import messages
from .pipelines import lead_from_api_pipeline

logger = logging.getLogger(__name__)


class CreditCreateMixinSerilizer(serializers.Serializer):
    # iin = serializers.RegexField(
    #     regex=r"^[0-9]{2}[0-9]{2}[0-9]{2}[0-9]{1}[0-9]{4}[0-9]{1}",
    #     write_only=True,
    #     min_length=12, max_length=12,
    # )
    # mobile_phone = PhoneNumberField(write_only=True)
    desired_amount = serializers.DecimalField(
        write_only=True,
        max_digits=12,
        decimal_places=2,
    )
    desired_period = serializers.IntegerField(write_only=True, default=20)
    # TODO: временно убрал, оставим для CPA
    # channel = serializers.PrimaryKeyRelatedField(
    #     queryset=Channel.objects.all(),
    #     write_only=True,
    # )

    cpa_transaction_id = serializers.CharField(
        required=False, write_only=True, allow_null=True,
    )
    wm_id = serializers.CharField(
        required=False, write_only=True, allow_null=True,
    )
    utm_source = serializers.CharField(required=False, write_only=True, allow_null=True)
    # utm = serializers.DictField(required=False, write_only=True, allow_null=True)

    def create(self, validated_data: Dict[str, Any]) -> Lead:
        validated_data["product"] = Product.objects.get(id=config.LANDING_PRODUCT)

        lead: Lead = lead_from_api_pipeline(validated_data)
        lead.check_params()

        if lead.rejected:
            raise ValidationError(detail=lead.reject_reason)

        logger.info("send otp code %s", lead.mobile_phone)
        send_otp(lead.mobile_phone)
        return lead


class CreditFastCreateAPIViewSerializer(CreditCreateMixinSerilizer):
    uuid = serializers.CharField(read_only=True)

    def create(self, validated_data: Dict[str, Any]) -> Lead:
        profile = self.context["request"].user
        validated_data["product"] = Product.objects.first()
        validated_data["iin"] = profile.person.iin
        validated_data["mobile_phone"] = profile.phone

        lead: Lead = lead_from_api_pipeline(validated_data)
        if lead.credit_params.principal not in lead.product.principal_limits:
            lead.reject(_("Указанная сумма не подходит по параметрам"))

        if lead.credit_params.period != lead.product.period:
            lead.reject(_("Указанный период не подходит по параметрам"))

        if lead.rejected:
            raise ValidationError(detail=lead.reject_reason)
        if lead.product.pipeline:
            logger.info('lead.product.pipeline: %s', lead.product.pipeline)
            credit = lead.create_credit_application()
            credit.to_check()
            credit.save()

            try:
                Flow(lead.product.pipeline, lead).run()

            except Exception as exc:
                logger.error('CreditFastCreateAPIViewSerializer pipeline.run: %s', exc)
                logger.exception(exc)

            if not lead.rejected:
                # Переведем статус заявки в работу
                credit.to_work()
                credit.save()
        return lead

    def to_representation(self, instance):
        response = super().to_representation(instance)
        if hasattr(instance, 'credit') and instance.credit:
            response['status'] = instance.credit.status
        return response


class CreditApplyAPIViewSerializer(CreditCreateMixinSerilizer):
    product = serializers.CharField(write_only=True)
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(),
        write_only=True,
        required=False,
    )
    uuid = serializers.CharField(read_only=True)

    def validate(self, attrs: dict):
        try:
            validator = IinValidator()
            validator(attrs['iin'])
        except InvalidIin as exc:
            raise ValidationError(detail={"iin": exc.default_detail})

        if not Product.objects.filter(pk=attrs['product']).exists():
            detail = ErrorDetail(messages.PROGRAM_NOT_FOUND, code="invalid_data")
            raise ValidationError(detail={"product": detail})

        return attrs


class CreditCreateViewSerializer(CreditCreateMixinSerilizer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        required=True
    )


class UUIDResponseSerializer(serializers.Serializer):
    uuid = serializers.CharField(read_only=True)


class SendOTPSerializer(UUIDResponseSerializer):
    pass


class VerifyOTPSerializer(UUIDResponseSerializer):
    uuid = serializers.CharField(read_only=True)
    otp_code = serializers.CharField(required=True, max_length=settings.OTP_LENGTH)

    def validate(self, attrs: Dict[str, Any]):
        is_verified = verify_otp(attrs["otp_code"], self.instance.mobile_phone, save=True)
        if not is_verified:
            raise ValidationError({"otp_apply": "Не верный ОТП код"})
        return attrs


class ExecuteSerializer(UUIDResponseSerializer):
    pass
