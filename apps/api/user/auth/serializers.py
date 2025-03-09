import logging
from string import ascii_letters, digits

from django.conf import settings
from drf_writable_nested import NestedUpdateMixin

from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from apps.accounts.models import Profile, ProfilePersonalRecord
from apps.core.utils import raise_notification_error
from apps.credits.api.serializers import AdditionalContactRelationSerializer, PersonContactSerializer
from apps.people.models import PersonalData, AdditionalContactRelation, Address
from apps.people.validators import IinValidator

logger = logging.getLogger(__name__)


# noinspection PyAbstractClass
class ResponseSerializer(serializers.Serializer):
    status = serializers.CharField(min_length=2)


# noinspection PyAbstractClass
class TokenResponseSerializer(ResponseSerializer):
    token = serializers.CharField()


# noinspection PyAbstractClass
class LogInSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    password = serializers.CharField()


class UserInfoSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(default=False)

    class Meta:
        model = Profile
        fields = ('id', 'phone', 'first_name', 'last_name', 'is_admin')


class ChangePasswordSerializer(serializers.Serializer):  # noqa
    old_password = serializers.CharField(error_messages={'required': 'Введите старый пароль'})
    new_password = serializers.CharField(min_length=8, error_messages={'required': 'Введите новый пароль'})
    re_new_password = serializers.CharField(min_length=8, error_messages={'required': 'Введите повторно пароль'})

    def validate(self, attrs: dict):
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        re_new_password = attrs.get('re_new_password')

        if old_password == new_password:
            raise serializers.ValidationError({'new_password': 'Вы ввели действующий пароль. Придумайте новый пароль'})

        if new_password != re_new_password:
            raise serializers.ValidationError('Оба новых пароля должны совпадать')

        return attrs


class LoginResponseSerializer(serializers.Serializer):  # noqa
    state = serializers.CharField()
    token = serializers.CharField()
    user = UserInfoSerializer()


# noinspection PyAbstractClass
class SendOTPSerializer(serializers.Serializer):
    phone = PhoneNumberField()


# noinspection PyAbstractClass
class SignUpSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    iin = serializers.CharField(validators=[IinValidator], min_length=12, max_length=12)

    def validate_phone(self, value):
        # Проверяем, существует ли уже профиль с таким номером
        if Profile.objects.filter(phone=value).exists():
            logger.error("phone=%s уже используется", value)
            raise serializers.ValidationError("Пользователь с таким номером телефона уже существует.")
        return value

    def validate_iin(self, value):
        if Profile.objects.filter(person__iin=value).exists():
            logger.error("iin=%s уже зарегистрирован", value)
            raise serializers.ValidationError("Пользователь с таким ИИН уже существует.")
        return value

    def validate(self, attrs: dict):
        return attrs

# noinspection PyAbstractClass
# noinspection DuplicatedCode
class ResetPasswordSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    new_password = serializers.CharField(min_length=8)
    re_new_password = serializers.CharField(min_length=8)
    code = serializers.CharField(write_only=True, label="OTP code")

    def validate(self, attrs: dict):
        new_password = attrs.get('new_password')
        re_new_password = attrs.get('re_new_password')

        if new_password != re_new_password:
            raise serializers.ValidationError('Оба новых пароля должны совпадать')

        if not any(map(str.isupper, new_password)):
            raise serializers.ValidationError({'password': 'Пароль должен иметь заглавную букву!'})

        elif not any(map(str.isdigit, new_password)):
            raise serializers.ValidationError({'password': 'Пароль должен иметь цифры!'})

        elif not set(new_password).difference(ascii_letters + digits):
            raise serializers.ValidationError({'password': 'Пароль должен иметь специальные символы!'})

        return attrs


class AddressProfileSerializer(NestedUpdateMixin, serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class ProfilePersonalRecordSerializer(serializers.ModelSerializer):
    document_exp_date = serializers.DateField(format="%d.%m.%Y", required=False)
    real_address = AddressProfileSerializer(required=False)
    additional_contact_relation = AdditionalContactRelationSerializer(
        many=True, required=False
    )
    is_registered = serializers.BooleanField(source="profile.is_registered", read_only=True)
    bank_statement = serializers.FileField(required=False)
    income_calculated_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)

    class Meta:
        model = ProfilePersonalRecord
        fields = (
            "first_name",
            "last_name",
            "middle_name",
            "dependants_child",
            "document_number",
            "document_exp_date",
            "document_issue_org",
            "organization",
            "position",
            "additional_income",
            "has_overdue_loans",
            "job_experience",
            "total_job_experience",
            "real_address",
            "additional_contact_relation",
            "is_registered",
            "bank_statement",
            "average_monthly_income",
            "income_calculated_at",
        )
        extra_kwargs = {
            "first_name": {"read_only": True},
            "last_name": {"read_only": True},
            "document_number": {"read_only": True},
            "document_exp_date": {"read_only": True},
            "document_issue_org": {"read_only": True},
            "average_monthly_income": {"read_only": True},
        }

    def create(self, validated_data):
        # Извлекаем данные для связанных контактов
        additional_contacts_data = validated_data.pop("additional_contact_relation", [])

        # Создаем запись PersonalData
        personal_data = super().create(validated_data)

        # Создаем связанные записи одним вызовом bulk_create
        additional_contacts = [
            AdditionalContactRelation(
                record=personal_data,
                contact=PersonContactSerializer(data=contact_data["contact"]).create(
                    contact_data["contact"]
                ),
                relationship=contact_data.get("relationship"),
            )
            for contact_data in additional_contacts_data
        ]
        AdditionalContactRelation.objects.bulk_create(additional_contacts)

        return personal_data

    def update(self, instance, validated_data):
        # Извлекаем данные для связанных контактов и адреса
        additional_contacts_data = validated_data.pop("additional_contact_relation", [])
        real_address_data = validated_data.pop("real_address", None)

        # Обновляем основную запись PersonalData
        instance = super().update(instance, validated_data)

        # Обновление адреса (если передан)
        if real_address_data:
            if instance.real_address:
                # Если адрес уже существует, обновляем его
                address_serializer = AddressProfileSerializer(
                    instance=instance.real_address, data=real_address_data
                )
                address_serializer.is_valid(raise_exception=True)
                address_serializer.save()
            else:
                # Если адреса нет, создаём новый
                address_serializer = AddressProfileSerializer(data=real_address_data)
                address_serializer.is_valid(raise_exception=True)
                instance.real_address = address_serializer.save()
                instance.save()

        # Обновление дополнительных контактов
        if additional_contacts_data:
            # Удаляем старые контакты
            AdditionalContactRelation.objects.filter(profile_record=instance).delete()

            # Создаём новые контакты
            new_contacts = []
            for contact_data in additional_contacts_data:
                contact_serializer = PersonContactSerializer(data=contact_data["contact"])
                contact_serializer.is_valid(raise_exception=True)
                contact = contact_serializer.save()
                new_contacts.append(
                    AdditionalContactRelation(
                        profile_record=instance,
                        contact=contact,
                        relationship=contact_data["relationship"],
                    )
                )
            AdditionalContactRelation.objects.bulk_create(new_contacts)

        return instance



# noinspection DuplicatedCode
class SetPasswordSerializer(serializers.Serializer):  # noqa
    otp = serializers.CharField(min_length=6)


class VerifyOtpSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    otp = serializers.CharField(min_length=6)
