import logging
import random

from django.conf import settings
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404, GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.utils import raise_notification_error
from apps.credits import CreditStatus
from apps.credits.models import CreditApplication, Guarantor
from apps.credits.views import print_forms_view
from apps.flow.integrations import PKBGBDFL
from apps.flow.models import ExternalService
from apps.notifications.services import send_otp, verify_otp, send_sms_find_template
from apps.accounts.authentication import generate_access_token
from apps.accounts.models import Profile, ProfilePersonalRecord

from apps.api.permissions import IsProfile, IsProfileAuthenticated
from apps.people.models import Person, PersonalData

from . import serializers
from .services import VerifyPersonService

logger = logging.getLogger(__name__)

token_response_schema = openapi.Response("Token response", serializers.TokenResponseSerializer)

CREDIT_APPROVED_STATUSES = [
    CreditStatus.APPROVED,
    CreditStatus.ISSUED,
    CreditStatus.ISSUANCE,
    CreditStatus.TO_SIGNING,
]


class LogInView(APIView):
    """Авторизация"""
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)

    @swagger_auto_schema(
        request_body=serializers.LogInSerializer,
        responses={'200': serializers.LoginResponseSerializer()}
    )
    def post(self, request):
        serializer = serializers.LogInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = Profile.objects.filter(phone=serializer.validated_data['phone']).first()
        if not profile or not profile.check_password(serializer.validated_data['password']):
            raise_notification_error(settings.INVALID_PASS)

        token = generate_access_token(profile)
        profile.last_login = timezone.now()
        profile.save(update_fields=["last_login"])

        serializer_response = serializers.LoginResponseSerializer({
            "state": "active",
            "token": token,
            "user": profile
        })
        return Response(serializer_response.data)


class SendOTPView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        request_body=serializers.SendOTPSerializer,
        responses={'200': serializers.ResponseSerializer()}
    )
    def post(self, request):
        serializer = serializers.SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_otp(serializer.validated_data['phone'])
        return Response({"status": "OK", "data": serializer.data})

class VerifyOTPView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        request_body=serializers.VerifyOtpSerializer,
        responses={'200': serializers.ResponseSerializer()}
    )
    def post(self, request):
        serializer = serializers.VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verify_otp(serializer.validated_data['otp'], serializer.validated_data['phone'])
        return Response({"status": "OK", "data": serializer.data})


class SignUpView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        request_body=serializers.SignUpSerializer,
        responses={'201': serializers.TokenResponseSerializer()}
    )
    def post(self, request):
        serializer = serializers.SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data.get('phone')
        iin = serializer.validated_data.get('iin')
        person, _ = Person.objects.get_or_create(iin=iin)
        profile, created = Profile.objects.get_or_create(
            person=person,
            defaults=dict(phone=phone),
        )
        if created:
            logger.info("Зарегистрирован новый пользователь %s", person.iin)
        send_otp(phone)
        print(f'profile: {profile}')
        token = generate_access_token(profile)
        return Response({"status": "OK", "token": token})


class UserPasswordChangeAPI(APIView):
    permission_classes = (IsProfileAuthenticated,)
    serializer_class = serializers.ChangePasswordSerializer

    def post(self, request):
        profile: Profile = request.user
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not profile.check_password(serializer.validated_data.get('old_password')):
            return Response({'message': 'Неверный текущий пароль'}, status=status.HTTP_400_BAD_REQUEST)

        profile.set_password(serializer.validated_data.get('new_password'))
        profile.save(update_fields=['password'])

        return Response({})


class ResetPasswordView(APIView):
    """ Сброс пароля от личного кабинета"""
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        request_body=serializers.ResetPasswordSerializer,
        responses={'200': serializers.TokenResponseSerializer()}
    )
    def post(self, request):
        serializer = serializers.ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data.pop('code')

        verify_otp(otp, serializer.validated_data['phone'])

        profile = get_object_or_404(Profile, phone=serializer.validated_data['phone'])
        profile.set_password(serializer.validated_data['new_password'])
        profile.save(update_fields=["password"])

        return Response({"status": "OK", "data": serializer.data})


class ProfileView(APIView):
    permission_classes = (IsProfile,)

    @swagger_auto_schema(
        responses={'200': serializers.ProfilePersonalRecordSerializer()}
    )
    def get(self, request):
        profile: Profile = request.user

        serializer = serializers.ProfilePersonalRecordSerializer(profile.personal_record)
        return Response({"status": "OK", "data": serializer.data})

    @swagger_auto_schema(
        request_body=serializers.ProfilePersonalRecordSerializer,
        responses={'201': serializers.ResponseSerializer()}
    )
    def post(self, request):
        profile: Profile = request.user

        serializer = serializers.ProfilePersonalRecordSerializer(data={**request.data, 'profile_id': profile.pk})

        if hasattr(profile, 'personal_record'):
            serializer = serializers.ProfilePersonalRecordSerializer(profile.personal_record, data=request.data)

        serializer.is_valid(raise_exception=True)
        personal_record = serializer.save()

        # Обработка банковской выписки, если она предоставлена
        self._handle_bank_statement(request, personal_record)

        # Update profile name
        profile.last_name = personal_record.last_name
        profile.first_name = personal_record.first_name
        profile.save(update_fields=['last_name', 'first_name'])

        return Response({"status": "OK"})

    @swagger_auto_schema(
        request_body=serializers.ProfilePersonalRecordSerializer,
        responses={'200': serializers.ResponseSerializer()}
    )
    def put(self, request):
        profile: Profile = request.user

        if not hasattr(profile, 'personal_record'):
            return Response(
                {"status": "ERROR", "message": "Personal record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        personal_record = profile.personal_record

        serializer = serializers.ProfilePersonalRecordSerializer(personal_record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Обработка банковской выписки, если она предоставлена
        self._handle_bank_statement(request, personal_record)

        # profile.last_name = personal_record.last_name
        # profile.first_name = personal_record.first_name
        # profile.save()
        profile.register_completed()
        return Response({"status": "OK"}, status=status.HTTP_200_OK)

    def _handle_bank_statement(self, request, personal_record):
        """
        Обработка загруженного файла банковской выписки.
        Сохраняет файл и запускает асинхронную задачу для его обработки.

        Args:
            request: Request объект с файлом выписки
            personal_record: Объект ProfilePersonalRecord для сохранения результатов
        """
        bank_statement = request.FILES.get('bank_statement')
        if not bank_statement:
            return

        try:
            from apps.accounts.tasks import process_bank_statement
            # Сохраняем файл в модели
            personal_record.bank_statement = bank_statement
            personal_record.save(update_fields=['bank_statement'])

            # Запускаем асинхронную задачу
            process_bank_statement.delay(
                personal_record_id=personal_record.id,
                file_path=personal_record.bank_statement.path
            )

        except Exception as e:
            print(f"Ошибка при запуске обработки выписки: {e}")


class SendCodeBiometryView(GenericAPIView):
    """
    Отправка запроса на получение 6 значного кода от 1414
    """
    permission_classes = (IsProfile,)

    @swagger_auto_schema(
        responses={'200': serializers.ResponseSerializer()}
    )
    def get(self, request, *args, **kwargs):
        profile: Profile = request.user

        # TODO: нужно отправить смс через egov
        credit = CreditApplication.objects.filter(
            borrower=profile.person,
            status__in=CREDIT_APPROVED_STATUSES,
        ).order_by('-pk').first()

        if not credit:
            guarantor_qs = Guarantor.objects.filter(
                person=profile.person,
                credit__status=CreditStatus.GUARANTOR_SIGNING,
            )
            if guarantor_qs.exists():
                credit = guarantor_qs.first().credit

        try:
            VerifyPersonService.send_code(credit)
            return Response({"status": "OK"})

        except Exception as exc:
            logger.error("SendCodeBiometryView error %s", exc)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)


class SetPasswordView(GenericAPIView):
    """
    Установка пароля от личного кабинета
    """
    permission_classes = (IsProfile,)
    serializer_class = serializers.SetPasswordSerializer

    @swagger_auto_schema(
        request_body=serializers.SetPasswordSerializer,
        responses={'200': serializers.ResponseSerializer()}
    )
    def post(self, request, *args, **kwargs):
        profile: Profile = request.user

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if profile.is_registered:
            logger.error("profile=%s, ИИН=%s уже зарегистрирован", profile, profile.person.iin)
            raise_notification_error(settings.IS_REGISTETED)
        new_password = str(random.randint(100000, 999999))
        otp = serializer.validated_data.pop('otp')
        verify_otp(otp, profile.phone)

        # profile.register_completed()
        profile.set_password(new_password)
        profile.save(update_fields=["password"])
        send_sms_find_template(profile.phone, "PASSWORD", {"password": new_password})

        profile_record, created = ProfilePersonalRecord.objects.update_or_create(
            profile=profile,
        )
        # TODO: доработать и проверить
        gbdl_service = ExternalService.by_class(PKBGBDFL)
        gbdl_service.run_in_background(profile_record)
        return Response({"status": "OK"})
