import logging

from celery.result import AsyncResult
from django.conf import settings
from django.contrib import admin
from django.core.files.storage import FileSystemStorage
from django.core.handlers.wsgi import WSGIRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.core.admin import ReadOnlyMixin
from config import celery_app
from . import AdminHistoryAction
from .models import BlackListMember, IndividualProprietorList, AdminHistory, Region
from .services import SyncIPService
from .tasks import download_ips_from_url_task, load_from_excel_ips

logger = logging.getLogger(__name__)


class BlackListMemberAdmin(admin.ModelAdmin):
    list_display = (
        "iin",
        "last_name",
        "first_name",
        "middle_name",
        "birthday",
        "reason",
    )
    list_display_links = ("iin", "last_name")
    list_filter = ("reason",)
    search_fields = ("iin",)


class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")


class IndividualProprietorListAdmin(admin.ModelAdmin):
    list_display = ("iin", "name", "full_name", "kato_code", "created_at")
    search_fields = ("iin", "name", "full_name", "kato_code")
    list_filter = ("region",)

    def name(self, obj: IndividualProprietorList):
        return obj.full_name

    name.short_description = "Наименование ИП"

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields['name'].label = "Наименование ИП"
        return form

    def get_urls(self):
        urls = super().get_urls()
        discount_urls = [
            path('upload_xlsx/', self.admin_site.admin_view(self.upload_xlsx), name='upload_ips_list'),
        ]
        return discount_urls + urls

    def upload_excel_file(self, request):
        try:
            file = request.FILES["file"]
            folder = settings.MEDIA_ROOT
            fs = FileSystemStorage(location=folder)
            filename = fs.save(file.name, file)
            load = load_from_excel_ips.delay(f'{folder}/{filename}')
            res = AsyncResult(load.id, app=celery_app)
            res.get()
            self.message_user(request, "Загрузка списка ИП в процессе.")
        except Exception as exc:
            logger.error("upload_excel_file: error %s", exc)
            raise exc

    # noinspection SpellCheckingInspection
    def upload_xlsx(self, request: WSGIRequest):
        errors = []
        if request.method == "POST":
            # if 'file_url' in request.POST and request.POST['file_url']:
            #     download_ips_from_url_task.delay(request.POST['file_url'])
            #     return redirect("admin:references_individualproprietorlist_changelist")

            if 'file' in request.POST and request.POST['file']:
                try:
                    self.upload_excel_file(request)
                    return redirect("admin:references_individualproprietorlist_changelist")

                except Exception as exc:
                    logger.error("upload_xlsx: error %s", exc, extra=request.POST)
                    errors.append(f"Error: {str(exc)}")

            elif 'sync_from_site' in request.POST and request.POST['sync_from_site'] == 'on':
                self.message_user(request, "Загрузка списка ИП в процессе.")
                SyncIPService.sync()
                return redirect("admin:references_individualproprietorlist_changelist")

        context = dict(
            self.admin_site.each_context(request),
            title="Загрузка списка ИП с Excel",
            errors=errors,
        )
        return TemplateResponse(request, "admin/references/individualproprietorlist/upload_form.html", context)


class AdminHistoryAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_filter = [
        'author',
        'content_type',
        'action_type'
    ]

    search_fields = [
        'action_description'
    ]

    list_display = [
        'created',
        'author',
        'object_link',
        'action_type',
        'field_name',
        'field_before',
        'field_after',
    ]

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def object_link(self, obj):
        if obj:
            if obj.action_type == AdminHistoryAction.DELETE:
                link = escape(obj.action_description)
            else:
                ct = obj.content_type
                link = '<a href="%s">%s</a>' % (
                    reverse('admin:%s_%s_change' % (ct.app_label, ct.model), args=[obj.object_id]),
                    escape(obj.action_description),
                )
            return mark_safe(link)

    object_link.admin_order_field = "action_description"
    object_link.short_description = "Описание изменения"


admin.site.register(BlackListMember, BlackListMemberAdmin)
admin.site.register(Region, RegionAdmin)
admin.site.register(IndividualProprietorList, IndividualProprietorListAdmin)
admin.site.register(AdminHistory, AdminHistoryAdmin)
