import io
import logging
from collections import OrderedDict
from datetime import date

import xlsxwriter
from dateutil.relativedelta import relativedelta
from django.http import HttpResponse
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from rest_framework import parsers
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    CreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    UpdateAPIView,
    DestroyAPIView, get_object_or_404,
)
from rest_framework import status, renderers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet, ModelViewSet
from drf_yasg.utils import swagger_auto_schema

from apps.core.serializers import DashboardDateSerializer
from apps.core.models import City, Branch, Bank, PrintForm
from apps.core.api.pagination import CustomPagination
from apps.credits import Decision, CreditStatus
from apps.credits.models import (
    Lead,
    CreditApplication,
    CreditHistory,
    CreditDocument,
    RejectionReason,
    DocumentType,
    FinanceReportType,
    CreditFinance,
    Guarantor,
    DocumentGroup,
    Product,
    CreditParams,
)
from apps.credits.utils import calculate_fin_report
from apps.flow.models import ExternalService
from apps.people.managers import PersonInfoFromIin
from apps.users.permissions import CreditAdminPermission
from apps.credits.api.tasks import generate_and_save_guarantor_document

from .filters import LeadListFilter, CreditListFilter, RejectionReasonFilter
from .permissions import BaseAuthPermission
from . import serializers
from .serializers import RejectionReasonDetailSerializer, ProductDetailSerializer
from ...notifications.models import OTP
from ...notifications.services import verify_otp, send_sms_find_template

logger = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class CreditStatusesListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        return Response(dict(CreditStatus.choices))


class CreditProductListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditProductSerializer
    queryset = Product.objects.order_by('name')
    pagination_class = CustomPagination

class CityListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CitySerializer
    queryset = City.objects.order_by('name')


class BranchListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.BranchSerializer
    queryset = Branch.objects.order_by('name')


class BankListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.BankSerializer
    queryset = Bank.objects.order_by('name')


class DocumentGroupsListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.DocumentGroupSerializer

    def get_queryset(self):
        return DocumentGroup.objects.filter(
            document_types__isnull=False,
            document_types__active=True,
        ).distinct().order_by('order')


class RejectionReasonListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.RejectionReasonSerializer
    queryset = RejectionReason.objects.filter(active=True).order_by('order')
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = RejectionReasonFilter

class ParseIINView(APIView):
    permission_classes = (IsAuthenticated,)

    # noinspection PyMethodMayBeStatic
    def post(self, request, **kwargs):
        try:
            result = PersonInfoFromIin(request.data.get('iin'))
            data = {
                "birthday": result.birthday,
                "age": relativedelta(date.today(), result.birthday).years,
                "gender": result.gender,
            }
            return Response(data)

        except Exception as exc:
            logger.error("ParseIINView: %s", exc)

        return Response({"message": "parse error"}, status=status.HTTP_400_BAD_REQUEST)


class LeadListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomPagination
    serializer_class = serializers.LeadListSerializer
    queryset = Lead.objects.select_related(
        'borrower', 'borrower_data', 'credit_params',
    ).order_by('-pk')
    filter_backends = [DjangoFilterBackend]
    filterset_class = LeadListFilter


class CreditListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomPagination
    serializer_class = serializers.CreditListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CreditListFilter

    def get_queryset(self):
        credit_status = self.request.GET.get('status')

        qs = CreditApplication.objects.select_related(
            'lead', 'borrower', 'borrower_data', 'requested_params',
        ).credits_by_permissions(self.request.user)

        if not credit_status:
            qs = qs.exclude(status__in=[CreditStatus.REJECTED])

        return qs.order_by('-pk')


class CreditCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditCreateSerializer
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context=dict(request=request))
        serializer.is_valid(raise_exception=True)

        lead = serializer.create(serializer.validated_data)
        message = "Создана новый лид %s" % lead.pk
        return Response({"status": "ok", "message": message})


class CreditRedirectView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditRedirectSerializer
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        credit_ids = serializer.validated_data['credit_ids']
        manager = serializer.validated_data['manager']
        queryset = CreditApplication.objects.filter(pk__in=credit_ids.split(','))
        success = queryset.update(manager=manager)
        return Response({"status": "ok" if success else "error"})


class CreditDetailView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditApplicationSerializer
    queryset = CreditApplication.objects.all()


class CreditPreviewView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditPreviewSerializer
    queryset = CreditApplication.objects.all()


class RejectCreditView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.RejectCreditSerializer
    queryset = CreditApplication.objects.all()

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data['reason']
        comment = serializer.validated_data['comment']

        instance: CreditApplication = self.get_object()
        instance.reject(reason, comment=comment)
        instance.save()

        return Response({"message": _("Статус успешно изменен")})


class CreditHistoryDetailView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditHistorySerializer

    def get_queryset(self):
        return CreditHistory.objects.filter(**self.kwargs)


class CreditReportView(RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ReportSerializer
    queryset = CreditApplication.objects.all()


class CreditFinanceUpdateView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditFinanceSerializer
    queryset = CreditApplication.objects.all()

    def get_object(self):
        instance: CreditApplication = super().get_object()
        if hasattr(instance, 'credit_finance'):
            credit_finance = instance.credit_finance

        else:
            credit_finance = CreditFinance.objects.create(credit=instance)

        if not credit_finance.finance_report:
            credit_finance.finance_report_init()

        return credit_finance

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CreditDocumentsView(ViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditDocumentsSerializer


class CreditChangeStatusView(UpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditChangeStatusSerializer
    queryset = CreditApplication.objects.all()
    http_method_names = ('patch',)


class Callback1cChangeStatusView(UpdateAPIView):
    permission_classes = [BaseAuthPermission]
    authentication_classes = []
    serializer_class = serializers.Callback1cChangeStatusSerializer
    queryset = CreditApplication.objects.all()
    http_method_names = ('patch',)


class CreditVoteView(RetrieveAPIView, APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditVoteSerializer
    queryset = CreditApplication.objects.all()
    http_method_names = ('post', 'get')

    def post(self, request, *args, **kwargs):  # noqa
        serializer = serializers.CreditVoteSerializer(data=request.data)

        if not serializer.is_valid():
            logger.error("CreditVoteSerializer.errors")
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        instance: CreditApplication = self.get_object()

        if instance.decision.is_already_voted(user=request.user):
            logger.error("Вы уже голосовали credit=%s", instance)
            return Response({"message": "Вы уже голосовали"}, status=HTTP_400_BAD_REQUEST)

        # Создаем запись голосования для каждого члена КК
        decision = serializer.validated_data.get('decision')
        comment = serializer.validated_data.get('comment')
        has_guarantor = serializer.validated_data.get('has_guarantor', False)
        params = serializer.validated_data.get("params")
        additional = serializer.validated_data.get("additional")

        guarantor_comment = " С гарантом" if has_guarantor else " Без гаранта"
        formatted_principal = f"{params.get('principal'):,}".replace(',', '.')
        additional_comment = (
            f" (ИЗМЕНЕНИЕ УСЛОВИЙ НА: "
            f"Сумма - {formatted_principal} тенге, "
            f"Срок - {params.get('period')} мес., "
            f"Ставка - {params.get('interest_rate')} %)"
        )
        comment = comment if additional == "without-changes" else comment + additional_comment

        instance.decision.vote(manager=request.user, status=decision, comment=comment + guarantor_comment)

        approved_params = CreditParams.objects.get(id=instance.approved_params.id)
        approved_params.__dict__.update(**params)
        approved_params.save()

        if request.user.is_chairman:
            guarantor_query = Guarantor.objects.filter(credit=instance)
            if has_guarantor and guarantor_query.exists() or not has_guarantor:
                voting_results = instance.decision.voting_results()
                logger.info('voting_results: %s', voting_results)

                if all([vote != decision for vote in voting_results]) or decision == Decision.AGAINST:
                    logger.info('Отказана КК')
                    reason, created = RejectionReason.objects.get_or_create(status='Отказ КК', defaults={'active': False})
                    instance.reject(reason=reason)
                else:
                    instance.to_approve()
        elif instance.decision.members_quorum():
            instance.to_decision_chairperson()
        instance.save()

        logger.info('CreditVoteView validated data: %s', serializer.validated_data)
        return Response(status=HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        instance: CreditApplication = self.get_object()
        params_serializer = serializers.CreditParamsSerializer(instance.approved_params)
        votes_serializer = serializers.CreditDecisionVoteSerializer(instance.decision.votes.all(), many=True)

        data = {"params_data": params_serializer.data, "votes_data": votes_serializer.data}

        return Response(data, status=HTTP_200_OK)


class CreditUploadFilesView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CreditUploadFilesSerializer
    queryset = CreditApplication.objects.all()

    def post(self, request, *args, **kwargs):  # noqa
        instance = CreditApplication.objects.get(pk=kwargs.get('pk'))
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        # serializer.save()
        document_type, _ = DocumentType.objects.get_or_create(code='UPLOADS', name='Данные по кредиту')
        credit_document = CreditDocument.objects.create(
            credit=instance,
            document_type=document_type,
            document=serializer.validated_data.get('file'),
        )
        return Response(serializers.CreditDocumentsSerializer(credit_document).data, status=HTTP_200_OK)


class CreditDocumentViewSet(ModelViewSet):
    permission_classes = (IsAuthenticated,)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)
    serializer_class = serializers.CreditDocumentsSerializer
    queryset = CreditDocument.objects.order_by('pk')
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        return super().get_queryset().filter(credit_id=self.kwargs.get('credit_id'))

    def perform_create(self, serializer):
        serializer.save(credit_id=self.kwargs.get('credit_id'))


class FinanceReportCalcView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.FinanceReportCalcSerializer
    queryset = CreditApplication.objects.all()
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        """Калькулятор таблицы Отчет о прибылях и убытках"""
        instance: CreditApplication = CreditApplication.objects.get(pk=kwargs.get('pk'))
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            monthly_payment = instance.recommended_params.monthly_payment
            current_loan_installment = instance.credit_finance.get_monthly_payment_from_credit_history()

            finance_reports = serializer.validated_data['finance_reports']
            # if isinstance(finance_reports, list):
            #     for report in finance_reports:
            #         if isinstance(report, dict) and report['const_name'] == ReportType.CURRENT_LOAN_INSTALLMENT:
            #             for index, value in enumerate(report['data']):
            #                 report['data'][index] = current_loan_installment
            #
            #         if isinstance(report, dict) and report['const_name'] == ReportType.ESTIMATED_LOAN_INSTALLMENT:
            #             for index, value in enumerate(report['data']):
            #                 report['data'][index] = monthly_payment

            calculate_fin_report(
                finance_reports,
                finance_report_month_count=instance.product.finance_report_month_count
            )
        except Exception as exc:
            logger.error("FinanceReportCalcView exception %s", exc)

        return Response(serializer.validated_data)


class FinanceReportTypeView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.FinanceReportTypeSerializer

    def get_queryset(self):
        return FinanceReportType.objects.filter(is_expense=True) \
            .only('name', 'const_name') \
            .order_by('position')



class PrintFormsView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ('get',)

    def get(self, request, *args, **kwargs):
        credit_pk = kwargs.get('pk')
        data = {}
        for print_form in PrintForm.objects.filter(is_active=True, slug__isnull=False).only('slug'):
            data[print_form.slug] = reverse('credit-print-form-pdf',
                                            kwargs={'pk': credit_pk, 'form_name': print_form.slug})
        return Response(data)


class StatisticView(APIView):
    permission_classes = (IsAuthenticated,)
    renderer_classes = [renderers.JSONRenderer]
    request_serializer = DashboardDateSerializer

    @method_decorator(
        swagger_auto_schema(
            query_serializer=DashboardDateSerializer(),
            name='list'
        )
    )
    def get(self, request, *args, **kwargs):
        from apps.credits.reports.dashboard import DashboardReport

        serializer = self.request_serializer(data={**request.GET.dict()})
        serializer.is_valid(raise_exception=True)

        report = DashboardReport(
            start_date=serializer.validated_data.get('start_date'),
            end_date=serializer.validated_data.get('end_date'),
            sales_channel=serializer.validated_data.get('channel'),
        )
        return Response(report.get())


class BaseExportView(ListAPIView):
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        # Create an in-memory output file for the new workbook.
        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        for col_num, cell_data in enumerate(self.serializer_class.Meta.fields):
            worksheet.write(0, col_num, cell_data)

        for row_num, columns in enumerate(serializer.data, start=1):  # type: int, OrderedDict
            for col_num, (cell_name, cell_data) in enumerate(columns.items()):
                worksheet.write(row_num, col_num, cell_data)

        # Close the workbook before sending the data.
        workbook.close()

        # Rewind the buffer.
        output.seek(0)

        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename="export.xlsx"'},
        )
        return response


# noinspection DuplicatedCode
class CreditApplicationsExportView(BaseExportView):
    serializer_class = serializers.CreditApplicationExportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CreditListFilter

    def get_queryset(self):
        credit_status = self.request.GET.get('status')

        qs = CreditApplication.objects.select_related(
            'lead', 'borrower', 'borrower_data', 'requested_params',
        )

        if not credit_status:
            qs = qs.exclude(status__in=[CreditStatus.REJECTED])

        return qs


# noinspection DuplicatedCode
class LeadsExportView(BaseExportView):
    serializer_class = serializers.LeadExportSerializer
    queryset = Lead.objects.select_related(
        'borrower', 'borrower_data', 'credit_params',
    )
    filter_backends = [DjangoFilterBackend]
    filterset_class = LeadListFilter


class RegistrationJournalView(ListAPIView):
    permission_classes = (IsAuthenticated & CreditAdminPermission,)
    pagination_class = CustomPagination
    serializer_class = serializers.RegistrationJournalListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CreditListFilter

    def get_queryset(self):
        qs = CreditApplication.objects.filter(
            status=CreditStatus.ISSUED,
        ).select_related(
            'lead',
            'borrower',
            'borrower_data',
            'business_info',
        )
        return qs


class RegistrationJournalsExportView(BaseExportView):
    permission_classes = (IsAuthenticated & CreditAdminPermission,)
    serializer_class = serializers.RegistrationJournalListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CreditListFilter

    def get_queryset(self):
        qs = CreditApplication.objects.filter(status=CreditStatus.ISSUED).select_related(
            'lead', 'borrower', 'borrower_data', "business_info"
        )

        return qs


class ProductDetailView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProductDetailSerializer
    queryset = Product.objects.all()


class RejectionReasonDetailView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = RejectionReasonDetailSerializer
    queryset = RejectionReason.objects.all()
