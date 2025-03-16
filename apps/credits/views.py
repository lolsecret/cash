import logging
from decimal import Decimal
from typing import Optional
import re
import pdfkit

import datetime

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.contrib.auth import get_permission_codename
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.template import Template, Context
from django.utils.translation import gettext
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import ListView, DetailView, DeleteView, FormView, UpdateView, CreateView, TemplateView
from django.forms import model_to_dict
from django.urls import reverse
from django_fsm import can_proceed, has_transition_perm
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, RetrieveAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from apps.flow.integrations.external.verigram_signing import VeragramSigning
from apps.core.models import PrintForm
from apps.people.models import Address, AdditionalContactRelation, PersonalData, Person
from apps.flow.models import StatusTrigger
from apps.flow.services import Flow
from apps.users.models import User
from . import CreditStatus, Decision, WithdrawalStatus, PaymentStatus
from .forms import (
    SimpleLeadForm,
    CreditParamsForm,
    BorrowerDataForm,
    AddressForm,
    BorrowerAdditionalForm,
    BusinessInfoForm,
    CreditApplicationDetailForm,
    LeadForm,
    CreditApplicationForm,
    AdditionalContactForm,
    AccountDetailsForm,
    RealAddressForm,
    CreditFinanceForm,
    DocumentUploadForm,
    GuarantorForm,
    RegAddressForm,
    RegAddressUpdateForm,
    RealAddressUpdateForm,
    PersonForm,
    RealAddressCreateForm,
    RegAddressCreateForm,
    CreditApplicationPreviewForm,
    GuarantorUpdateForm,
)
from .models import (
    Lead,
    CreditApplication,
    BusinessInfo,
    Product,
    CreditFinance,
    FinanceReportType,
    RejectionReason,
    CreditDecisionVote,
    CreditDocument,
    DocumentType,
    CreditDecision,
    CreditReport,
    Guarantor,
    Comment, CreditApplicationPayment, CreditWithdrawal, CreditContract,
)
from . import serializers
from .serializers import CreditSigningInitSerializer, CreditSigningStatusSerializer, \
    PaymentSerializer, PaymentCallbackSerializer, WithdrawalSerializer, WithdrawalCallbackSerializer
from .services.payment_service import PaymentService, PaymentGatewayError, WithdrawalService
from .utils import FinanceReportFactory

logger = logging.getLogger(__name__)


class CreateLeadView(FormView):
    form_class = SimpleLeadForm
    success_url = 'leads-list'

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ProductListView(ListView):
    queryset = Product.objects.order_by('pk')
    paginate_by = 10

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        return context


class LeadListView(ListView):
    queryset = Lead.objects.order_by('-pk')
    paginate_by = 10

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        if 'lead_form' not in context:
            context['lead_form'] = SimpleLeadForm(prefix='lead')
        return context


class JournalView(PermissionRequiredMixin, TemplateView):
    template_name = 'credits/journal_view.html'

    def has_permission(self):
        user: User = self.request.user
        return user.is_credit_admin

    def handle_no_permission(self):
        return redirect(reverse('root'))


class LeadDetailView(DetailView):
    model = Lead


class CreditsRedirectView(View):
    def post(self, request, *args, **kwargs):
        credit_ids = request.POST.get('credit_ids')
        manager = get_object_or_404(User, pk=request.POST.get('manager'))
        if not credit_ids or not manager:
            return JsonResponse({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        credit_queryset = CreditApplication.objects.filter(pk__in=credit_ids.split(','))
        success = credit_queryset.update(manager=manager)
        return JsonResponse({"status": "success" if success else "error"})


class CreditApplicationListView(ListView):
    queryset = CreditApplication.objects.order_by('-pk')
    paginate_by = 10  # if pagination is desired
    object_list = None

    filter = {}

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        lead_form = SimpleLeadForm(data=request.POST, prefix='lead')
        if not lead_form.is_valid():
            logger.error(lead_form.errors)
            self.object_list = self.get_queryset()
            return self.render_to_response(self.get_context_data(lead_form=lead_form))

        lead = lead_form.create()

        if lead.product.pipeline:
            logger.info('lead.product.pipeline: %s', lead.product.pipeline)
            credit = lead.create_credit_application(manager=request.user)
            credit.to_check()
            credit.save()

            logger.info("Api.views: flow run pipeline for lead %s", lead.pk)
            transaction.on_commit(lambda: Flow(lead.product.pipeline, lead).run())

            # if lead.rejected:
            #     messages.error(request, lead.reject_reason)
            #     return JsonResponse({"status": "error", "message": lead.reject_reason})

            # Создаем кредитную заявку
            # credit.to_work()
            credit.save()

        return JsonResponse({"status": "success", "msg": gettext("Credit application created.")})

    def get(self, request, *args, **kwargs):
        self.filter['product'] = kwargs.get('product', None) or self.request.GET.get('product')
        self.filter['created_gte'] = self.request.GET.get('created_gte', None)
        self.filter['created_lte'] = self.request.GET.get('created_lte', None)
        self.filter['product_name'] = None
        self.filter['search'] = self.request.GET.get('search', '')
        self.filter['status'] = self.request.GET.get('status', '')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().credits_by_permissions(self.request.user)
        # queryset = super().get_queryset()

        created_gte = self.filter.get('created_gte')
        created_lte = self.filter.get('created_lte')
        if created_gte:
            created_gte = datetime.datetime.strptime(created_gte, '%Y-%m-%d')
            queryset = queryset.filter(created__gte=created_gte)

        if created_lte:
            created_lte = datetime.datetime.strptime(created_lte, '%Y-%m-%d')
            queryset = queryset.filter(created__lte=created_lte)

        if self.filter.get('product'):
            product = Product.objects.filter(pk=self.filter.get('product')).first()
            if product:
                queryset = queryset.filter(product=product)
                self.filter['product_name'] = product.name

        search = self.filter.get('search', '')
        if search:
            query = Q()
            if re.match(r"\d", search):
                query.add(Q(pk=search), Q.OR)

            query.add(Q(lead__mobile_phone__contains=search), Q.OR)
            query.add(Q(borrower__iin__startswith=search), Q.OR)
            query.add(Q(borrower_data__last_name__icontains=search), Q.OR)
            queryset = queryset.filter(query)

        filter_status = self.filter.get('status')
        if filter_status and filter_status in CreditStatus:
            queryset = queryset.filter(status=filter_status)
        else:
            queryset = queryset.exclude(status=CreditStatus.REJECTED)

        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['statuses'] = CreditStatus.choices
        context['products'] = Product.objects.all()
        context['created_gte'] = self.filter.get('created_gte')
        context['created_lte'] = self.filter.get('created_lte')
        if 'lead_form' not in context:
            context['lead_form'] = SimpleLeadForm(prefix='lead')

        context['product_default'] = self.kwargs.get('product')
        context['filter'] = self.filter
        context['rejection_reasons'] = RejectionReason.objects.filter(active=True)
        context['managers_for_redirect'] = User.objects.managers().exclude(pk=self.request.user.pk)
        return context


class GuarantorCreateView(CreateView):
    model = PersonalData
    form_class = GuarantorForm
    template_name = 'credits/guarantor_form.html'

    def post(self, request, *args, **kwargs):
        credit_pk = kwargs.get('credit_pk')
        credit: CreditApplication = CreditApplication.objects.get(pk=credit_pk)

        # person_form = PersonForm(
        #     data=request.POST,
        #     prefix='person',
        # )
        # if not person_form.is_valid():
        #     print('person_form.errors:', person_form.errors)
        # person: Person = person_form.save()

        reg_address_form = RegAddressUpdateForm(
            data=request.POST,
            prefix='guarantor-reg-address',
        )

        real_address_form = RealAddressUpdateForm(
            data=request.POST,
            prefix='guarantor-real-address',
        )

        additional_contact_form = AdditionalContactForm(
            data=request.POST,
            prefix='guarantor-additional-contact'
        )
        if not additional_contact_form.is_valid():
            return self.form_invalid(additional_contact_form)

        form = self.get_form()
        if not all([
            form.is_valid(),
            reg_address_form.is_valid(),
            real_address_form.is_valid(),
        ]):
            logger.error("GuarantorCreateView form is not valid %s", form.errors)
            return self.form_invalid(form)

        same_reg_address = real_address_form.cleaned_data.pop('same_reg_address')
        if same_reg_address:
            real_address_form.update_data_with_same_address(reg_address_form.cleaned_data)

        reg_address = reg_address_form.save()
        real_address = real_address_form.save()

        person_record: PersonalData = form.save(commit=False)
        person_record.reg_address = reg_address
        person_record.real_address = real_address
        person_record.save()

        additional_contact_form.save(person_record)

        return JsonResponse({'status': 'success'})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['credit_pk'] = self.kwargs.get('credit_pk')

        context['person_form'] = PersonForm(
            initial=model_to_dict(Person()),
            prefix='guarantor-person',
        )
        context['reg_address_form'] = RegAddressForm(
            initial=model_to_dict(Address()),
            prefix='guarantor-reg-address',
        )
        context['real_address_form'] = RealAddressCreateForm(
            initial=model_to_dict(Address()),
            prefix='guarantor-real-address',
        )

        context['additional_contact_form'] = AdditionalContactForm(
            initial={'first_name': None, 'mobile_phone': None, 'relationship': None},
            prefix='guarantor-additional-contact'
        )
        return context


class GuarantorView(FormView, DetailView):
    model = PersonalData
    form_class = GuarantorUpdateForm
    template_name = 'credits/modals/guarantor_modal.html'

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = GuarantorUpdateForm(
            instance=PersonalData(),
            data=request.POST,
        )
        if not form.is_valid():
            return self.form_invalid(form)

        return JsonResponse({"status": "success"})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guarantee_data: PersonalData = PersonalData()

        context['reg_address_form'] = RegAddressUpdateForm(
            instance=Address(),
            prefix='reg-address',
        )

        context['real_address_form'] = RealAddressForm(
            initial=model_to_dict(Address()),
            prefix='real-address',
        )
        return context


class GuarantorUpdateView(UpdateView):
    model = PersonalData
    form_class = GuarantorUpdateForm
    template_name = 'credits/guarantor_edit_form.html'
    object: Optional[PersonalData] = None

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        guarantor: PersonalData = self.get_object()

        reg_address_form = RegAddressUpdateForm(
            instance=guarantor.reg_address,
            data=request.POST,
            prefix='guarantor-reg-address',
        )
        real_address_form = RealAddressUpdateForm(
            instance=guarantor.real_address,
            data=request.POST,
            prefix='guarantor-real-address',
        )

        form = GuarantorUpdateForm(
            instance=guarantor,
            data=request.POST,
        )

        if not all([
            form.is_valid(),
            reg_address_form.is_valid(),
            real_address_form.is_valid(),
        ]):
            return self.render_to_response(self.get_context_data(
                form=form,
                reg_address_form=reg_address_form,
                real_address_form=real_address_form,
            ))

        same_reg_address = real_address_form.cleaned_data.pop('same_reg_address')
        if same_reg_address:
            real_address_form.update_data_with_same_address(reg_address_form.cleaned_data)

        reg_address = reg_address_form.save()
        real_address = real_address_form.save()

        self.object = form.save(commit=False)
        self.object.reg_address = reg_address
        self.object.real_address = real_address
        self.object.save()

        return JsonResponse({"status": "success"})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guarantor: PersonalData = self.object
        context['credit_pk'] = self.kwargs.get('credit_pk')

        if 'reg_address_form' not in context:
            context['reg_address_form'] = RegAddressUpdateForm(
                instance=guarantor.reg_address,
                prefix='guarantor-reg-address',
            )

        if 'real_address_form' not in context:
            context['real_address_form'] = RealAddressUpdateForm(
                instance=guarantor.real_address,
                prefix='guarantor-real-address',
            )
        return context


class GuarantorDeleteView(DeleteView):
    model = Guarantor
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # noqa
        self.object.delete()
        return JsonResponse({'status': 'success'})


class CreditApplicationPreviewView(FormView, DetailView):
    model = CreditApplication
    form_class = CreditApplicationPreviewForm
    template_name = 'credits/creditapplication_preview_ajax.html'
    object: CreditApplication

    def post(self, request, *args, **kwargs):
        self.object: CreditApplication = self.get_object()
        self.update_data(request)
        form = CreditApplicationPreviewForm(data=request.POST)
        if not form.is_valid():
            return self.form_invalid(form)

        repayment_method = form.cleaned_data.pop('repayment_method')
        status_reason = form.cleaned_data.pop('status_reason')
        next_status = form.cleaned_data.pop('status')  # noqa
        comment = form.cleaned_data.pop('comment')
        if not next_status:  # если нет смены статуса просто сохраним изменения
            if comment:
                Comment.objects.create(credit=self.object, author=request.user, content=comment)
                self.object.status_reason = comment

            self.object.save()
            return JsonResponse({'status': 'success'})

        try:
            transition_method = self.object.get_transition_by_status(next_status)
            with transaction.atomic():
                self.object.recommended_params.repayment_method = repayment_method
                self.object.recommended_params.save()
                transition_method()

                if comment:
                    Comment.objects.create(
                        credit=self.object,
                        author=request.user,
                        content=comment,
                    )
                    self.object.status_reason = comment
                if status_reason:
                    self.object.status_reason = f'{comment}, {str(status_reason)}' if comment else str(status_reason)

                self.object.save()

                return JsonResponse({'status': 'success'})

        except Exception as exc:
            logger.error("CreditApplicationPreviewView error", exc)

        return JsonResponse({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

    def update_data(self, request):
        recommended_params_form = CreditParamsForm(
            data=request.POST,
            prefix='recommended-params',
        )
        if recommended_params_form.is_valid():
            recommended_params_form.save(self.object.recommended_params)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance: CreditApplication = context['object']
        form = CreditApplicationPreviewForm(
            initial=dict(
                principal=int(instance.recommended_params.principal),
                period=instance.recommended_params.period,
                repayment_method=instance.recommended_params.repayment_method,
                status=instance.status,
                status_reason=instance.status_reason
            )
        )

        status_choices = [(None, '-- Статус заявки --')] + instance.available_status_transitions()  # noqa
        rejection_reasons = list(RejectionReason.objects.filter(active=True).values_list('pk', "status"))
        if instance.status in [CreditStatus.IN_WORK, CreditStatus.FIN_ANALYSIS]:
            approved_statuses = [CreditStatus.CALLBACK, CreditStatus.REJECTED, None]
            status_choices = list(filter(lambda x: x[0] in approved_statuses, status_choices))

        form.fields['status'].choices = status_choices
        form.fields['principal'].initial = instance.recommended_params.principal
        form.fields['period'].initial = instance.recommended_params.period
        form.fields['status_reason'].choices = [(None, '-- Выберите причину --')] + rejection_reasons

        context['form'] = form
        context['credit_report'] = instance.lead.get_credit_report()
        return context


class CreditApplicationView(FormView, DetailView):
    model = CreditApplication
    form_class = CreditApplicationDetailForm
    object: CreditApplication
    template_name = 'credits/creditapplication_form.html'

    def get_success_url(self):
        return reverse('credit-edit', kwargs={'pk': self.object.pk})

    def get_queryset(self):
        return super().get_queryset().credits_by_permissions(self.request.user)
        # return super().get_queryset()

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)

        except Http404:
            return redirect(reverse('credits-list'))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        self.update_data(request)

        return super().post(request, *args, **kwargs)

    def update_data(self, request):
        borrower_data = self.object.borrower_data
        product = self.object.product
        period_choices = []
        if product and product.period_limits:
            period_choices = list((str(x), x) for x in range(product.period_limits.lower, product.period_limits.upper))

        lead_form = LeadForm(
            instance=self.object.lead,
            data=request.POST,
            prefix='lead-form',
        )
        if lead_form.is_valid():
            lead_form.save()

        borrower_add_form = BorrowerAdditionalForm(
            instance=borrower_data,
            data=request.POST,
            prefix='borrower-additional',
        )
        if borrower_add_form.is_valid():
            borrower_add_form.save()

        real_address_form = RealAddressForm(
            data=request.POST,
            prefix='real-address',
        )
        if real_address_form.is_valid():
            real_address_form.save(borrower_data)

        additional_contact_form = AdditionalContactForm(
            data=request.POST,
            prefix='additional-contact'
        )
        if additional_contact_form.is_valid():
            additional_contact_form.save(borrower_data)

        business_info_form = BusinessInfoForm(
            data=request.POST,
            instance=self.object.business_info,
            prefix='business-info',
        )
        if business_info_form.is_valid():
            business_info_form.save()

        recommended_params_form = CreditParamsForm(
            data=request.POST,
            prefix='recommended-params',
        )
        if recommended_params_form.is_valid():
            recommended_params_form.save(self.object.recommended_params)

        approved_params_form = CreditParamsForm(
            data=request.POST,
            prefix='approved-params',
        )
        approved_params_form.fields['period'].choices = period_choices

        if approved_params_form.is_valid():
            approved_params_form.save(self.object.approved_params)

        credit_finance_form = CreditFinanceForm(
            data=request.POST,
            instance=self.object.credit_finance,
            prefix='credit-finance',
        )
        if credit_finance_form.is_valid():
            credit_finance_form.save()
        else:
            logger.error("credit_finance_form.errors: %s", credit_finance_form.errors)

        finance_report = FinanceReportFactory(
            data=request.POST,
            initial=self.object.credit_finance.finance_report,
        )

        if finance_report.is_valid():
            finance_report.save(self.object.credit_finance)

        credit_form = CreditApplicationForm(
            instance=self.object,
            data=request.POST,
            prefix='credit-form',
        )
        if credit_form.is_valid():
            credit_form.save()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance: CreditApplication = context['object']
        borrower_data = instance.borrower_data
        product = instance.product

        context['lead_form'] = LeadForm(instance=instance.lead, prefix='lead-form')
        context['credit_form'] = CreditApplicationForm(instance=instance, prefix='credit-form')

        additional_contact_data = {'first_name': None, 'mobile_phone': None, 'relationship': None}
        additional_contact: Optional[AdditionalContactRelation] = borrower_data.additional_contact_relation.first()
        if additional_contact:
            additional_contact_data['first_name'] = additional_contact.contact.first_name
            additional_contact_data['mobile_phone'] = additional_contact.contact.mobile_phone.__str__()
            additional_contact_data['relationship'] = additional_contact.relationship

        context['borrower_add_form'] = BorrowerAdditionalForm(
            instance=borrower_data,
            prefix='borrower-additional'
        )

        context['additional_contact_form'] = AdditionalContactForm(
            initial=additional_contact_data,
            prefix='additional-contact'
        )

        period_choices = ()
        if product and product.period_limits:
            period_choices = list((str(x), x) for x in range(product.period_limits.lower, product.period_limits.upper))

        if not instance.recommended_params or not instance.approved_params:
            instance.init_credit_params()

        recommended_params_form = CreditParamsForm(
            initial=model_to_dict(instance.recommended_params),
            prefix='recommended-params',
        )

        recommended_params_form.fields['period'].choices = period_choices
        recommended_params_form.fields['period'].disabled = True
        recommended_params_form.fields['principal'].disabled = True
        recommended_params_form.fields['interest_rate'].disabled = True
        recommended_params_form.fields['repayment_method'].disabled = True
        context['recommended_params_form'] = recommended_params_form

        context['approved_params_form'] = CreditParamsForm(
            initial=model_to_dict(instance.approved_params),
            prefix='approved-params',
        )
        context['approved_params_form'].fields['period'].choices = period_choices

        business_info, created = BusinessInfo.objects.get_or_create(credit=instance)
        context['business_info_form'] = BusinessInfoForm(instance=business_info, prefix='business-info')

        context['reg_address_form'] = RegAddressForm(
            initial=model_to_dict(borrower_data.reg_address),
            prefix='reg-address',
        )

        if not borrower_data.real_address:
            borrower_data.real_address = Address.objects.create()
            borrower_data.save(update_fields=['real_address'])

        context['real_address_form'] = RealAddressForm(
            initial=model_to_dict(borrower_data.real_address),
            prefix='real-address',
        )

        if not hasattr(instance, 'credit_finance'):
            CreditFinance.objects.create(credit=instance)

        context['credit_finance_form'] = CreditFinanceForm(instance=instance.credit_finance, prefix='credit-finance')

        finance_report = FinanceReportFactory(
            initial={
                'begin': instance.credit_finance.begin_date,
                'end': instance.credit_finance.end_date,
                'fields': instance.credit_finance.finance_report,
                'comment': instance.credit_finance.report_comment,
            }
        )
        context['finance_report'] = finance_report.initial
        context['credit_finance_net_balance_percentage'] = instance.credit_finance.net_balance_percentage
        context['credit_finance_equity_div_debit'] = instance.credit_finance.equity_div_debit

        expense_types = FinanceReportType.objects.filter(is_expense=True) \
            .only('name', 'const_name') \
            .order_by('position')

        context['CreditStatus'] = CreditStatus
        context['finance_report_expenses'] = [model_to_dict(expense) for expense in expense_types]
        context['document_types'] = DocumentType.objects.all()
        context['allowed_vote'] = bool(
            self.request.user.has_perm("credits.add_creditdecisionvote")  # noqa
            and instance.status in (CreditStatus.DECISION, CreditStatus.DECISION_CHAIRPERSON)
            and instance.decision.allowed_vote(self.request.user)
        )

        opts = instance._meta  # noqa
        codename = get_permission_codename('change', opts)
        context['has_change_perm'] = instance.has_status_permission(
            self.request.user, "%s.%s" % (opts.app_label, codename)
        )
        context['back_url'] = self.request.META.get('HTTP_REFERER', '/')
        return context


class CreditApplicationV2View(FormView, DetailView):
    model = CreditApplication
    form_class = CreditApplicationDetailForm
    object: CreditApplication
    template_name = 'credits/creditapplication_form_v2.html'

    def get_success_url(self):
        return reverse('credit-edit', kwargs={'pk': self.object.pk})


class CreditChangeStatusView(UpdateView):
    model = CreditApplication

    def post(self, request, *args, **kwargs):
        status_str = request.POST.get('status', None)
        if not status_str or status_str not in CreditStatus:
            return JsonResponse({"message": "Неверный статус"}, status=400)

        credit_status = CreditStatus(status_str)  # noqa
        credit: CreditApplication = self.get_object()

        old_status = credit.status

        logger.info('credit %s try change status: %s -> %s', credit, old_status, status)

        try:
            transition_method = credit.get_transition_by_status(credit_status)

            if can_proceed(transition_method) and has_transition_perm(transition_method, credit.manager):
                transition_method()
                credit.save()

                logger.info('credit %s change status success: %s -> %s', credit, old_status, status)
                StatusTrigger.run(status=credit_status, credit=credit)

            serializer = serializers.CreditApplicationShortSerializer(credit)
            return JsonResponse(serializer.data)

        except Exception as exc:
            logger.error("Ошибка смены статуса %s", exc)
            return JsonResponse({"message": "Ошибка смены статуса"}, status=400)

    def create_new_decision(self, credit: CreditApplication):  # noqa
        CreditDecision.objects.create(credit=credit)


class CreditApplicationRejectView(DeleteView):
    model = CreditApplication

    def delete(self, request, *args, **kwargs):
        reason_id = request.POST.get('reject-reason', None)
        comment = request.POST.get('reject-comment', '')

        reason = RejectionReason.objects.filter(pk=reason_id).first()
        if not reason:
            return JsonResponse("Неверный статус", status=400)

        instance: CreditApplication = self.get_object()
        instance.reject(reason, comment=comment)
        instance.save()

        serializer = serializers.CreditApplicationShortSerializer(instance)
        return JsonResponse(serializer.data)


class FinanceReportView(View):
    template_name = 'credits/forms/finance_report.html'

    def post(self, request, pk: int):
        finance_report = FinanceReportFactory(
            data=request.POST,
        )
        if finance_report.is_valid():
            context = {
                'finance_report': finance_report.initial
            }
            return render(request, self.template_name, context)

        return render(request, self.template_name)


class CreditUploadFilesView(UpdateView):
    queryset = CreditApplication.objects.all()
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        self.object: CreditApplication = self.get_object()  # noqa

        form = DocumentUploadForm(request.POST, files=request.FILES)
        if not form.is_valid():
            return JsonResponse(form.errors, status=400)

        document = form.save(credit=self.object)
        serializer = serializers.CreditDocumentSerializer(document)
        return JsonResponse(serializer.data)


class CreditRemoveFileView(View):
    http_method_names = ('post',)

    def post(self, request, **kwargs):
        document_id = request.POST.get('document_id')
        document = get_object_or_404(CreditDocument, pk=document_id)
        document.delete()
        return JsonResponse({'status': 'success'})


class CreditVoteView(UpdateView):
    model = CreditApplication

    def post(self, request, **kwargs):
        instance: CreditApplication = self.get_object()

        decision_status = request.POST.get('decision-status', None)
        comment = request.POST.get('decision-comment', None)

        without_changes = request.POST.get('without-changes', None)
        with_adjustments = request.POST.get('with-adjustments', None)

        if not decision_status or decision_status not in Decision or not comment:
            return JsonResponse({"message": "Ошибка голосования"}, status=400)

        status = Decision(decision_status)  # noqa

        if instance.decision.is_already_voted(user=request.user):
            return JsonResponse({"message": "Вы уже голосовали"}, status=400)

        # Создаем запись голосования для каждого члена КК
        instance.decision.vote(manager=request.user, status=status, comment=comment)

        if request.user.is_chairman:
            voting_results = instance.decision.voting_results()
            logger.info('voting_results: %s', voting_results)
            is_against_vote = instance.decision.votes.filter(
                status=Decision.AGAINST).exclude(manager=request.user).count() > 1

            if (Decision.AGAINST not in voting_results) or (status == Decision.FOR and not is_against_vote):
                instance.to_approve()
            else:
                logger.info('Отказана КК')
                reason, created = RejectionReason.objects.get_or_create(status='Отказ КК', defaults={'active': False})
                instance.reject(reason=reason)

        elif instance.decision.members_quorum():
            instance.to_decision_chairperson()

        # Commit status
        instance.save()

        serializer = serializers.CreditApplicationShortSerializer(instance)
        return JsonResponse(serializer.data)


@xframe_options_exempt
def print_forms_view(request, pk, form_name):
    print_form = get_object_or_404(PrintForm, slug=form_name)
    template = Template(print_form.template, name=print_form.name)
    credit: CreditApplication = get_object_or_404(CreditApplication, pk=pk)
    serializer = serializers.CreditApplicationPrintSerializer(instance=credit)

    return HttpResponse(template.render(Context({"credit": serializer.data})))


@xframe_options_exempt
def print_forms_pdf_view(request, pk, form_name):
    print_form = get_object_or_404(PrintForm, slug=form_name)
    template = Template(print_form.template, name=print_form.name)
    credit: CreditApplication = get_object_or_404(CreditApplication, pk=pk)
    serializer = serializers.CreditApplicationPrintSerializer(instance=credit)

    options = {'enable-local-file-access': None}
    pdf = pdfkit.PDFKit(template.render(Context({"credit": serializer.data})), "string", options=options).to_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{form_name}-{pk}.pdf"'
    return response


class CreditSigningViewSet(GenericViewSet):
    """ViewSet для подписания кредитной заявки через Verigram Flow"""

    @swagger_auto_schema(
        method='post',
        responses={200: openapi.Response("Signing initiated")}
    )
    @action(detail=True, methods=['post'])
    def init_signing(self, request, pk=None):
        """Инициализация процесса подписания кредитной заявки"""

        credit = get_object_or_404(CreditApplication, pk=pk)

        try:
            # Находим активный сервис Verigram
            service = VeragramSigning.find_active_service()

            # Инициируем процесс подписания
            verigram_service = VeragramSigning(instance=credit, service_model=service)
            result = verigram_service.run()

            # Если статус заявки позволяет, переводим её в статус "На подписании"
            if credit.status == CreditStatus.APPROVED:
                credit.to_signing()
                credit.save()

            # Возвращаем URL для Flow
            return Response({
                "flow_id": credit.verigram_flow_id,
                "vlink": credit.verigram_flow_url,
                "status": "success"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error initializing signing flow: {str(e)}")
            return Response(
                {"error": "Произошла ошибка при инициализации процесса подписания"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        request_body=CreditSigningStatusSerializer,
        responses={200: openapi.Response("Signing initiated")}
    )
    @action(detail=False, methods=['post'])
    def check_signing_status(self, request):
        """Проверка статуса подписания кредитной заявки"""
        serializer = CreditSigningStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        flow_id = serializer.validated_data['flow_id']

        try:
            # Находим кредитную заявку по flow_id
            credit = get_object_or_404(CreditApplication, verigram_flow_id=flow_id)
            service = VeragramSigning.find_active_service()
            service_instance = VeragramSigning(instance=credit, service_model=service)

            result = service_instance.get_flow_result(flow_id)

            # Если Flow успешно завершен, обрабатываем подписанный документ
            if result.get('flow_status') == 'pass' and result.get('end_cause') == 'completed':
                VeragramSigning.process_signed_document(credit, flow_id)

            return Response({
                "flow_status": result.get('flow_status'),
                "end_cause": result.get('end_cause'),
                "credit_status": credit.status,
                "is_signed": credit.is_signed
            })

        except Exception as e:
            logger.exception(f"Error checking signing status: {str(e)}")
            return Response(
                {"error": "Произошла ошибка при проверке статуса подписания"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def callback(self, request, pk=None):
        """Обработчик вебхуков от Verigram Flow"""
        try:
            credit = get_object_or_404(CreditApplication, pk=pk)
            flow_id = credit.verigram_flow_id

            if not flow_id:
                return Response(
                    {"error": "Не найден Flow ID для данной кредитной заявки"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Обрабатываем подписанный документ
            success = VeragramSigning.process_signed_document(credit, flow_id)

            if success:
                return Response({"status": "success"})
            else:
                return Response(
                    {"error": "Ошибка при обработке подписанного документа"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.exception(f"Error processing callback: {str(e)}")
            return Response(
                {"error": "Произошла ошибка при обработке обратного вызова"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreatePaymentView(CreateAPIView):
    """Create a payment for a credit application."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Handle the payment creation request.

        Creates a payment for the specified credit application using
        the approved principal amount.
        """
        # Get the credit application ID from the URL
        credit_application_id = kwargs.get('pk')

        # Fetch the credit application or return 404
        credit_application = get_object_or_404(
            CreditApplication,
            pk=credit_application_id
        )

        # Validate that the user has permission to make a payment on this application
        user = request.user
        if hasattr(user, 'person') and credit_application.borrower != user.person:
            return Response(
                {"detail": "You do not have permission to make payments for this credit application."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Use approved_params.principal as the payment amount
        amount = Decimal(credit_application.approved_params.principal)

        # Create the payment
        try:
            # Create payment object
            payment = CreditApplicationPayment.objects.create(
                contract=credit_application.contract,
                amount=amount,
                person=user.person if hasattr(user, 'person') else None
            )

            # Generate payment link
            PaymentService.create_payment_link(payment)

            # Return the created payment with payment link
            return Response(
                self.get_serializer(payment).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Failed to create payment for credit application {credit_application_id}: {e}")

            # Return appropriate error response
            if isinstance(e, PaymentGatewayError):
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY
                )
            else:
                return Response(
                    {"detail": "An error occurred while creating the payment."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class PaymentDetailView(RetrieveAPIView):
    """Get payment details including current status."""
    queryset = CreditApplicationPayment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        """Retrieve payment details, updating the status if needed."""
        payment = self.get_object()

        # Check if the payment belongs to the current user
        if payment.person and payment.person != request.user.person:
            return Response(
                {"detail": "You do not have permission to view this payment."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update payment status from payment gateway
        try:
            PaymentService.check_payment_status(payment)
        except PaymentGatewayError as e:
            logger.warning(f"Could not update payment status: {e}")
            # Continue anyway, we'll just return the current status

        # Return updated payment data
        serializer = self.get_serializer(payment)
        return Response(serializer.data)


class UserPaymentsListView(ListAPIView):
    """List all payments for the current user."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only payments related to the current user."""
        user = self.request.user
        if hasattr(user, 'person'):
            return CreditApplicationPayment.objects.filter(
                person=user.person
            ).select_related('contract').order_by('-created')
        return CreditApplicationPayment.objects.none()


class PaymentCallbackView(APIView):
    """Webhook для обработки колбэков от платежной системы."""
    permission_classes = [AllowAny]  # Нет необходимости в аутентификации для вебхука

    def post(self, request, *args, **kwargs):
        """Обработка колбэка от платежной системы."""
        logger.info(f"Получен колбэк от платежной системы: {request.data}")

        serializer = PaymentCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Некорректные данные колбэка: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Извлекаем проверенные данные
        order_id = serializer.validated_data.get('orderId')  # Изменено с order_id на orderId
        gateway_status = serializer.validated_data.get('status')

        # Находим платеж по order_id
        try:
            payment = CreditApplicationPayment.objects.get(order_id=order_id)
        except CreditApplicationPayment.DoesNotExist:
            logger.error(f"Платеж с order_id={order_id} не найден")
            return Response(
                {"detail": "Платеж не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обновляем статус платежа
        try:
            # Сохраняем необработанные данные колбэка
            payment.payment_response = serializer.validated_data
            payment.save(update_fields=['payment_response'])

            # Мапинг статусов платежной системы на наши статусы
            status_mapping = {
                2: PaymentStatus.PAID,  # Success -> Оплачено
                1: PaymentStatus.IN_PROGRESS,  # Processing -> В процессе
                0: PaymentStatus.WAITING,  # Waiting for redirect -> В ожидании
                -1: PaymentStatus.PAYMENT_ERROR  # Fail -> Ошибка оплаты
            }

            # Если статус содержится в нашем маппинге, обновляем статус платежа
            if gateway_status in status_mapping:
                new_status = status_mapping[gateway_status]
                old_status = payment.status

                if new_status != old_status:
                    payment.status = new_status
                    payment.save(update_fields=['status'])

                    logger.info(
                        f"Статус платежа {payment.id} обновлен: {old_status} -> {new_status}"
                    )

                    # Если платеж теперь оплачен, можем запустить доп. действия
                    if new_status == PaymentStatus.PAID:
                        # Обработка успешного платежа
                        # Например, обновление статуса контракта и т.д.
                        pass
            else:
                logger.warning(f"Неизвестный статус платежа: {gateway_status}")

            # Логируем колбэк
            logger.info(
                f"Колбэк обработан для order_id={order_id}, "
                f"статус={gateway_status}, payment_id={payment.id}"
            )

            return Response({"status": "success"})

        except Exception as e:
            logger.error(f"Ошибка обработки колбэка платежа: {e}", exc_info=True)
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CreateWithdrawalView(APIView):
    """
    API для создания вывода средств и получения URL для токенизации карты.

    Создает запись о выводе средств для указанного кредитного договора
    и возвращает URL формы для токенизации карты.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, contract_id):
        """
        Создать запрос на вывод средств и вернуть URL формы токенизации.
        """
        # Проверяем, что кредитный договор принадлежит текущему пользователю
        contract = get_object_or_404(CreditContract, id=contract_id)

        if contract.borrower != request.user.person:
            return Response(
                {"detail": "У вас нет прав для создания вывода средств по этому договору."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Создаем запрос на вывод средств и получаем URL формы
            withdrawal, tokenize_url = WithdrawalService.create_tokenize_form(contract_id)

            # Формируем ответ
            response_data = {
                "id": withdrawal.id,
                "status": withdrawal.status,
                "amount": str(withdrawal.amount),
                "tokenize_form_url": tokenize_url
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Ошибка при создании вывода средств: {e}", exc_info=True)
            return Response(
                {"detail": "Произошла ошибка при создании запроса на вывод средств."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WithdrawalStatusView(APIView):
    """
    API для проверки статуса вывода средств.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, withdrawal_id):
        """
        Получить текущий статус вывода средств.
        """
        withdrawal = get_object_or_404(CreditWithdrawal, id=withdrawal_id)

        # Проверяем права доступа
        if withdrawal.contract.borrower != request.user.person:
            return Response(
                {"detail": "У вас нет прав для просмотра этого вывода средств."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Возвращаем статус
        return Response({
            "id": withdrawal.id,
            "status": withdrawal.status,
            "status_display": withdrawal.get_status_display(),
            "amount": str(withdrawal.amount),
            "error_message": withdrawal.error_message,
            "completed_at": withdrawal.completed_at
        })


class WithdrawalCallbackView(APIView):
    """
    Обработка колбэков от платежной системы по выводу средств.
    """
    permission_classes = []  # Колбэк не требует аутентификации

    def post(self, request):
        """
        Обработать колбэк от платежной системы.
        """
        serializer = WithdrawalCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Извлекаем данные
        order_id = serializer.validated_data.get('order_id')
        status_code = serializer.validated_data.get('status')

        # Обрабатываем колбэк
        try:
            success = WithdrawalService.process_callback(
                order_id=order_id,
                status=status_code,
                data=serializer.validated_data
            )

            if success:
                return Response({"status": "success"})
            else:
                return Response(
                    {"detail": "Ошибка обработки колбэка"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Ошибка обработки колбэка: {e}", exc_info=True)
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
