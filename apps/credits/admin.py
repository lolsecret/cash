import logging

from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.shortcuts import redirect
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from adminsortable2.admin import SortableAdminMixin, SortableInlineAdminMixin
from django.db.models import Model

from apps.core.admin import ReadOnlyMixin
from apps.flow.models import ServiceHistory, StatusTrigger
from apps.credits.models import Guarantor, CreditApplicationPayment
from . import CreditStatus
from .forms import CreditApplicationAdminForm
from .models import (
    Channel,
    Product,
    Partner,
    RejectionReason,
    Lead,
    CreditApplication,
    CreditContract,
    FinancingType,
    FundingPurpose,
    FinanceReportType,
    DocumentGroup,
    DocumentType,
    CreditDocument,
    CreditReport,
    EmailNotification,
    ApplicationFaceMatchPhoto,
)

logger = logging.getLogger(__name__)


class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    list_display_links = ('id',)


class CreditApplicationPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'amount')
    list_display_links = ('id',)


class CreditReportAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = (
        'id',
        "link_relation_object",
        "behavior_score",
        "behavior_default_prob",
        "behavior_risk_grade",
    )
    search_fields = ("credit__id",)

    def link_relation_object(self, instance: CreditReport):
        if instance.credit:
            obj = instance.credit

        elif instance.lead:
            obj = instance.lead

        elif instance.guarantor:
            obj = instance.guarantor

        else:
            return

        model_class = obj._meta  # noqa
        change_url = reverse(
            'admin:%s_%s_change' % (
                model_class.app_label,
                model_class.object_name.lower()
            ),
            args=(obj.id,)
        )
        return mark_safe(f"<a href='{change_url}'>{f'{model_class.verbose_name.capitalize()}: {obj.id}'}</a>")

    link_relation_object.allow_tags = True
    link_relation_object.short_description = 'Связанный объект'


class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'principal_limits', 'period', 'is_active')
    list_display_links = ('name',)

    filter_horizontal = ('reject_reasons',)
    fieldsets_old = (
        (
            None,
            {
                'fields': (
                    ('name', 'id'),
                    ('financing_purpose', 'financing_type'),
                )
            },
        ),
        ("Ограничения по кредиту", {
            "fields": (
                'interest_rate',
                'principal_limits',
                'period_limits',
                'minimum_income',
                'maximum_loan_amount_with_minimum_income',
            )
        },),
        ("Проверки", {
            "fields": (
                'pipeline',
                'reject_reasons',
            )
        },),
    )


class HistoryInline(ReadOnlyMixin, GenericTabularInline):
    model = ServiceHistory
    fields = ["service", "status", "runtime", "created_at", "show"]
    readonly_fields = ["created_at", "show"]
    can_delete = False
    extra = 0

    def show(self, obj):
        url = reverse("admin:flow_servicehistory_change", args=(obj.pk,))
        return mark_safe(f"<a href='{url}'>Посмотреть</a>")

    show.short_description = "Лог сервиса"  # noqa


class RejectionReasonAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ('status', 'active')


class LeadAdmin(admin.ModelAdmin):
    inlines = [HistoryInline]
    list_display = ('uuid', 'borrower', 'product', 'credit_params', 'rejected', 'reject_reason', 'created')
    readonly_fields = ('credit_params', 'utm_params')
    raw_id_fields = ('borrower', 'borrower_data')
    date_hierarchy = 'created'


class GuarantorInline(admin.TabularInline):
    model = Guarantor
    extra = 0


class CreditApplicationAdmin(admin.ModelAdmin):
    form = CreditApplicationAdminForm

    inlines = (GuarantorInline, HistoryInline)
    list_display = ('pk', 'borrower', 'product', 'status', 'reject_reason', 'created')
    list_filter = ('product', 'status',)
    readonly_fields = (
        'lead',
        'status',
        # 'change_status_button',
        # 'reject_reason',
        # 'status_reason',
        'created',
        'modified',
        'signed_at',
        'requested_params',
        'recommended_params',
        'approved_params',
        'report_link',
        'image_tag'
    )
    raw_id_fields = ['borrower_data']
    date_hierarchy = 'created'
    search_fields = ('lead__mobile_phone', 'borrower__iin')

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'lead',
                    'created',
                    'modified',
                    'status',
                    # 'change_status_button',
                    'image_tag',
                    'new_status',
                    'reject_reason',
                    'status_reason',
                    "report_link",
                )
            },
        ),
        (
            "Данные заёмщика",
            {"fields": (
                # "get_borrower_iin",
                # "get_borrower_full_name",
                "borrower_data",
            )},
        ),
        ("Общее", {"fields": (("product", "partner"),)},),
        (
            "Параметры займа",
            {
                "fields": (
                    ("requested_params", "recommended_params", "approved_params"),
                ),
            },
        ),
        # (
        #     "Ссылки на печатные формы",
        #     {
        #         "fields": (
        #             (
        #                 "get_statement_url",
        #                 "get_schedule_url",
        #                 "get_agreement_url",
        #                 "get_processing_agreement_url",
        #                 "get_contract_url",
        #             ),
        #         )
        #     },
        # ),
        ("OTP подтверждение", {
            "fields": (
                ("verified", "signed_at", "otp_signature"),
            )
        },),
    )

    def image_tag(self, obj):
        if hasattr(obj, 'biometry_photos'):
            if hasattr(obj.biometry_photos, 'document_photo'):
                try:
                    biometry_photos_instance = obj.init_biometry_photos()
                    photo = biometry_photos_instance.document_photo
                    return mark_safe('<img src="%s" width="100" height="100" />' % photo.url)
                except ValueError:
                    pass
    image_tag.short_description = 'Doc_photo'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["new_status"].choices = (
                [(obj.status, obj.get_status_display())] + obj.available_status_transitions()
        )
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:credit_id>/change-status/<str:new_status>/',
                self.admin_site.admin_view(self.manual_change_status),
                name='change-status',
            ),
        ]
        return custom_urls + urls

    # @admin.display
    # def change_status_button(self, obj: CreditApplication):
    #     template = ""
    #     style = "margin: 0 0 0 5px"
    #
    #     def add_button(obj_pk: int, status: CreditStatus) -> str:
    #         url = reverse('admin:change-status', args=[obj_pk, status])
    #         return f'<a href="{url}" class="button" style="{style}">{status.label}</a>'
    #
    #     try:
    #         if obj.status == CreditStatus.ISSUANCE:
    #             template += add_button(obj.pk, CreditStatus.ISSUED)
    #
    #         elif obj.status == CreditStatus.REJECTED:
    #             template += add_button(obj.pk, CreditStatus.IN_WORK)
    #
    #         elif obj.status == CreditStatus.IN_WORK_CREDIT_ADMIN:
    #             template += add_button(obj.pk, CreditStatus.IN_WORK)
    #             template += add_button(obj.pk, CreditStatus.FILLING)
    #
    #         elif obj.status == CreditStatus.DECISION:
    #             template += add_button(obj.pk, CreditStatus.IN_WORK)
    #
    #         return mark_safe(template)
    #
    #     except Exception as exc:
    #         logger.error("admin.change_status_button error %s", exc)
    #         return ''
    #
    # change_status_button.short_description = 'Поменять статус'

    def manual_change_status(self, request, credit_id, *args, **kwargs):
        credit: CreditApplication = CreditApplication.objects.get(pk=credit_id)
        from_status = credit.status
        new_status = kwargs.get('new_status')

        try:

            if from_status == CreditStatus.REJECTED and new_status == CreditStatus.IN_WORK:
                credit.to_work()

            elif from_status == CreditStatus.IN_WORK_CREDIT_ADMIN and new_status == CreditStatus.IN_WORK:
                credit.rework()
                credit.to_work()

            elif from_status == CreditStatus.IN_WORK_CREDIT_ADMIN and new_status == CreditStatus.FILLING:
                credit.rework()

            elif from_status == CreditStatus.DECISION and new_status == CreditStatus.IN_WORK:
                credit.rework()
                credit.to_work()

            elif from_status == CreditStatus.ISSUANCE and new_status == CreditStatus.ISSUED:
                credit.issued()

            credit.save()

        except Exception as exc:
            logger.error(
                "admin.manual_change_status error change status %s -> %s",
                from_status, new_status
            )

        return redirect(reverse('admin:credits_creditapplication_change', args=(credit_id,)))

    def report_link(self, obj):
        if not obj.credit_report:
            return "-"
        url = reverse("admin:credits_creditreport_change", args=(obj.credit_report.pk,))
        return mark_safe(f"<a href='{url}'>{str(obj.credit_report)}</a>")

    report_link.short_description = "Кредитное досье"


class CreditContractAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = 'contract_number', 'borrower', 'credit', 'product', 'params', 'contract_status', 'signed_at'
    list_filter = 'contract_status', 'product'
    date_hierarchy = 'contract_date'


class FinanceReportTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'const_name', 'is_expense', 'calculated', 'position')
    ordering = ['position']


class DocumentTypeInline(SortableInlineAdminMixin, admin.TabularInline):
    model = DocumentType
    extra = 0


class DocumentGroupForm(forms.ModelForm):
    id = forms.CharField(widget=forms.TextInput(attrs={'class': 'vTextField vTextFieldUpper'}))
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'vTextField'}))

    def clean_id(self):
        return self.cleaned_data['id'].upper()


class DocumentGroupAdmin(SortableAdminMixin, admin.ModelAdmin):  # Add SortableAdminBase here
    inlines = (DocumentTypeInline,)
    list_display = ('id', 'name', 'order')
    list_editable = ('order',)

    form = DocumentGroupForm

    class Media:
        css = {
            'all': ('css/admin/styles.css',)
        }

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.pk:
            return super().get_readonly_fields(request, obj) + ('id', 'order')
        return super().get_readonly_fields(request, obj)


class DocumentTypeAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'group')
    list_filter = ('group',)


class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ('status', 'role', 'subject')
    list_filter = ('status', 'role')
    ordering = ['status', 'role']


class ApplicationFaceMatchPhotoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'credit', 'borrower_photo_exists', 'document_photo_exists', 'similarity', 'attempts')

    readonly_fields = 'credit', 'similarity', 'attempts', 'vendor', 'query_id'

    def borrower_photo_exists(self, obj: ApplicationFaceMatchPhoto):
        return bool(obj.borrower_photo)

    borrower_photo_exists.boolean = True

    def document_photo_exists(self, obj: ApplicationFaceMatchPhoto):
        return bool(obj.document_photo)

    document_photo_exists.boolean = True


admin.site.register(EmailNotification, EmailNotificationAdmin)
admin.site.register([Partner])
admin.site.register(CreditDocument)
admin.site.register(Channel, ChannelAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(RejectionReason, RejectionReasonAdmin)
admin.site.register(Lead, LeadAdmin)
admin.site.register(CreditApplication, CreditApplicationAdmin)
admin.site.register(CreditContract, CreditContractAdmin)
admin.site.register([FinancingType, FundingPurpose])
admin.site.register(FinanceReportType, FinanceReportTypeAdmin)
admin.site.register(DocumentGroup, DocumentGroupAdmin)
admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(CreditReport, CreditReportAdmin)
admin.site.register(ApplicationFaceMatchPhoto, ApplicationFaceMatchPhotoAdmin)
admin.site.register(CreditApplicationPayment, CreditApplicationPaymentAdmin)
