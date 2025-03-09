import logging

from django.contrib import admin
from django.contrib.admin.options import get_content_type_for_model
from django.db.models import Model
from django.urls import reverse
from django.urls.conf import path
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from apps.core.admin import ReadOnlyMixin
from apps.references import AdminHistoryAction
from apps.references.models import AdminHistory
from apps.flow.forms import ServiceAPIAdminForm
from apps.flow.models import (
    ExternalService,
    Pipeline,
    Job,
    ServiceHistory,
    ServiceResponse,
    ServiceReason,
    StatusTrigger,
    BiometricConfiguration,
)
from apps.flow.services import Flow

logger = logging.getLogger(__name__)


def service_duplicate_action(model, request, queryset):
    for obj in queryset:  # type: ExternalService
        obj.id = None
        obj.name += " Copy"
        obj.is_active = False
        obj.save()


service_duplicate_action.short_description = _("Duplicate selected record")


class ServiceAPIAdmin(admin.ModelAdmin):
    list_display = 'id', 'name', 'service_class', 'is_active', 'cache_lifetime'
    list_display_links = 'name',
    actions = [service_duplicate_action]
    form = ServiceAPIAdminForm

    fieldsets = (
        (None, {'fields': (
            ('name', 'is_active'),
            'service_class',
            ('address', 'username', 'password', 'token'),
            ('timeout', 'cache_lifetime'),
        )}),
        (_("Additional parameters"), {
            'classes': ('collapse', 'open'),
            "fields": (("params",),),
        },),
    )


class JobInline(admin.TabularInline):
    model = Job
    ordering = ("priority",)
    extra = 0


class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'background')
    inlines = (JobInline,)


class ServiceResponseInline(ReadOnlyMixin, admin.StackedInline):
    model = ServiceResponse
    extra = 0


class ServiceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "link_content_object",
        "service_name",
        "reference_id",
        "status",
        "runtime",
        "created",
        "has_response",
    )
    list_filter = ("service", "status")
    list_select_related = ("service", "service_response")
    date_hierarchy = "created"
    inlines = [ServiceResponseInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "service_name",
                    "link_content_object",
                    ("status", "repeat_button"),
                    "created_at",
                    "runtime",
                    "pipeline",
                    "request_id",
                )
            },
        ),
        (
            "Данные",
            {
                "fields": ("data",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def service_name(self, obj: ServiceHistory):
        return obj.service or "-"

    service_name.short_description = "Сервис"  # noqa

    def has_response(self, obj):
        return obj.data is not None

    has_response.short_description = "Наличие ответа"  # noqa
    has_response.boolean = True

    def link_content_object(self, instance: ServiceHistory):
        obj: Model = instance.content_object
        if not obj:
            return "-"

        model_class = obj._meta  # noqa
        change_url = reverse(
            'admin:%s_%s_change' % (
                model_class.app_label,
                model_class.object_name.lower()
            ),
            args=(obj.id,)
        )
        return mark_safe(f"<a href='{change_url}'>{f'{model_class.verbose_name.capitalize()}: {obj.id}'}</a>")

    link_content_object.allow_tags = True  # noqa
    link_content_object.short_description = _('in relation to')  # noqa

    def get_request(self, obj):
        if obj.response:
            return obj.response.response
        return "Нет данных"

    get_request.short_description = "Параметры запроса"  # noqa

    def get_response(self, obj):
        if obj.response:
            return obj.response.response
        return "Нет данных"

    get_response.short_description = "Ответ сервиса"  # noqa

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:service_history_id>/repeat/',
                self.admin_site.admin_view(self.repeat_service_request),
                name='repeat-service-request',
            ),
        ]
        return custom_urls + urls

    @admin.display
    def repeat_button(self, obj):
        if obj.status in Pipeline.SUCCESS_STATUSES:
            return ''

        try:
            url = reverse('admin:repeat-service-request', args=[obj.pk])

            return mark_safe(f"""
                <a href="{url}" class="button">Повторить запрос</a>
            """)
        except Exception as exc:
            logger.error("repeat_button error %s task_id %s", exc, obj.pk)
            return ''

    repeat_button.short_description = ''

    def repeat_service_request(self, request, service_history_id, *args, **kwargs):  # noqa
        service_history = ServiceHistory.objects.get(id=service_history_id)
        Flow(service_history.pipeline, service_history.content_object, retry=True).run()

        action_description = f'{AdminHistoryAction.RETRY.value}: {service_history.__str__()}'

        AdminHistory.objects.create(
            author=request.user,
            action_type=AdminHistoryAction.RETRY,
            content_type_id=get_content_type_for_model(service_history).pk,
            object_id=service_history.pk,
            field_name="Retry",
            action_description=action_description,
        )
        return redirect(reverse(
            'admin:flow_servicehistory_change',
            args=(service_history_id,)
        ))


class ServiceReasonAdmin(admin.ModelAdmin):
    list_display = ('service', 'key', 'message', 'is_active')
    list_display_links = ('key', 'message')
    list_filter = ('service', 'is_active')


class RejectReasonOnProductAdmin(admin.ModelAdmin):
    list_display = ('pk', 'product')
    filter_horizontal = ('reason',)


class StatusTriggerAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'status', 'pipeline', 'is_active')


class BiometricConfigurationAdmin(admin.ModelAdmin):
    list_display = '__str__', 'service'

    def has_add_permission(self, request):
        return not BiometricConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ExternalService, ServiceAPIAdmin)
admin.site.register(Pipeline, PipelineAdmin)
admin.site.register(ServiceHistory, ServiceHistoryAdmin)
admin.site.register(ServiceReason, ServiceReasonAdmin)
admin.site.register(StatusTrigger, StatusTriggerAdmin)
admin.site.register(BiometricConfiguration, BiometricConfigurationAdmin)
