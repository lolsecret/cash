import logging

import pdfkit
from constance import config
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import Template, Context
from django.urls import reverse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from apps.api.permissions import IsProfileAuthenticated

from apps.accounts.models import Profile
from apps.api.scoring.pipelines import lead_from_api_pipeline
from apps.core.models import NotificationText, PrintForm
from apps.credits import RepaymentMethod
from apps.credits.models import Lead, Product, Channel, CreditApplication
from apps.credits.serializers import CreditApplicationPrintSerializer
from apps.flow.services import Flow

from . import serializers

logger = logging.getLogger(__name__)


class CalculatorView(APIView):

    def get(self, request):
        data = {
            "amount_min": 200_000,
            "percentage": .37,
            "annuity": True,
        }
        return Response(data, status=status.HTTP_200_OK)


class CallMeView(APIView):
    """Обратный звонок"""
    serializer_class = serializers.CallMeSerializer
    permission_classes = (AllowAny,)

    @swagger_auto_schema(request_body=serializers.CallMeSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        num_send_message = send_mail(
            subject='Обратный звонок c сайта',
            message='Обратный звонок на номер: '
                    + str(serializer.validated_data.get("phone", "Тел. не указан. "))
                    + ' от '
                    + str(serializer.validated_data.get("name", "ФИО не указано")),
            from_email=config.EMAIL_HOST_USER,
            recipient_list=[config.SUPPORT_EMAIL],
            fail_silently=False,
            auth_user=config.EMAIL_HOST_USER,
            auth_password=settings.EMAIL_HOST_PASSWORD
        )
        content = {"num_send_message": num_send_message}
        return Response(content, status=status.HTTP_201_CREATED)


class EmailView(APIView):
    """Отправка сообщения"""
    serializer_class = serializers.EmailSerializer
    permission_classes = (AllowAny,)

    @swagger_auto_schema(request_body=serializers.EmailSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        num_send_message = send_mail(
            subject='Вопросы c сайта',
            message=serializer.validated_data.get("text", "Текст не заполнен")
                    + str(serializer.validated_data.get("phone", "Тел. не указан. "))
                    + ' от '
                    + str(serializer.validated_data.get("email", "Email не указано"))
                    + str(serializer.validated_data.get("name", "ФИО не указано")),
            from_email=config.EMAIL_HOST_USER,
            recipient_list=[config.SUPPORT_EMAIL],
            fail_silently=False,
            auth_user=config.EMAIL_HOST_USER,
            auth_password=settings.EMAIL_HOST_PASSWORD
        )
        content = {"num_send_message": num_send_message}
        return Response(content, status=status.HTTP_201_CREATED)


class CreditRequestView(APIView):
    """Создание кредитной заявки
    Поле repayment_method
    Для аннуитета 0
    Для дифференцированного метода 1
    """
    permission_classes = (AllowAny,)
    serializer_class = serializers.CreditRequestSerializer

    @swagger_auto_schema(request_body=serializers.CreditRequestSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        payload = {
            'mobile_phone': data.get('phone'),
            'iin': data.get('iin'),
            'desired_amount': data.get('amount'),
            'desired_period': data.get('month'),
            'utm_source': data.get('utm_source'),
            'repayment_method': (RepaymentMethod.EQUAL_INSTALMENTS if data.get('repayment_method')
                                 else RepaymentMethod.ANNUITY),
            'product': Product.objects.get(id=config.LANDING_PRODUCT),
            'channel': Channel.objects.first(),
            'utm': data.get('utm'),
        }
        lead: Lead = lead_from_api_pipeline(payload)
        lead.check_params()

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
                logger.error('CreditRequestView pipeline.run: %s', exc)
                logger.exception(exc)

            # TODO: не переводим заявку
            # if not lead.rejected:
            #     # Переведем статус заявки в работу
            #     credit.to_work()
            #     credit.save()

        return Response(status=status.HTTP_200_OK)


class ProductListView(ListAPIView):
    """Список продуктов для калькулятора на сайте"""
    permission_classes = (AllowAny,)
    queryset = Product.objects.all()
    serializer_class = serializers.ProductListSerializer


class NotificationTextListView(ListAPIView):
    # permission_classes = (IsAuthenticated,)
    serializer_class = serializers.NotificationTextSerializer
    queryset = NotificationText.objects.all()


class ProfilePrintFormsView(APIView):
    permission_classes = (IsProfileAuthenticated,)
    http_method_names = ('get',)

    def get(self, request, *args, **kwargs):
        credit_pk = kwargs.get('pk')
        credit = CreditApplication.objects.get(id=credit_pk)
        profile: Profile = request.user
        if credit.borrower_id != profile.person.id:
            raise ValidationError({"detail": "Текущий пользователь не имеет печатных форм"})

        data = {}
        for print_form in PrintForm.objects.filter(is_active=True, slug__isnull=False).only('slug'):
            data[print_form.slug] = reverse('profile-print-form-pdf',
                                            kwargs={'pk': credit_pk, 'form_name': print_form.slug})
        return Response(data)


class PrintFormView(APIView):
    permission_classes = [IsProfileAuthenticated]
    renderer_classes = [StaticHTMLRenderer]

    def get(self, request: Request, pk: int, form_name: str):
        profile: Profile = request.user

        print_form = get_object_or_404(PrintForm, slug=form_name)
        template = Template(print_form.template, name=print_form.name)

        credit = get_object_or_404(
            CreditApplication,
            Q(pk=pk) & (Q(borrower=profile.person) | Q(guarantors__person=profile.person))
        )
        serializer = CreditApplicationPrintSerializer(instance=credit)

        html_response = template.render(Context({"credit": serializer.data}))
        return Response(html_response)


class PrintFormPDFView(APIView):
    permission_classes = [IsProfileAuthenticated]

    def get(self, request: Request, pk: int, form_name: str):
        profile: Profile = request.user

        print_form = get_object_or_404(PrintForm, slug=form_name)
        template = Template(print_form.template, name=print_form.name)

        credit = get_object_or_404(
            CreditApplication,
            Q(pk=pk) & (Q(borrower=profile.person) | Q(guarantors__person=profile.person))
        )
        serializer = CreditApplicationPrintSerializer(instance=credit)

        html_response = template.render(Context({"credit": serializer.data}))

        options = {'enable-local-file-access': None}
        pdf = pdfkit.PDFKit(html_response, "string", options=options).to_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{form_name}-{pk}.pdf"'
        return response
