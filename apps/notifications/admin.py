from django.contrib import admin

from apps.core.admin import ReadOnlyMixin

from .models import OTP, SMSMessage, SMSType, SMSTemplate


class SMSMessageAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = (
        "created",
        "uuid",
        "recipients",
        "content",
        "error_code",
        "error_description",
    )
    list_display_links = (
        "created",
        "uuid",
    )
    search_fields = "recipients",
    readonly_fields = (
        "created",
        "uuid",
        "recipients",
        "content",
        "error_code",
        "error_description",
    )
    ordering = ("-created",)


class OTPAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("created", "mobile_phone", "verified", "code")
    list_display_links = ("created", "mobile_phone")
    readonly_fields = ("created", "mobile_phone", "verified", "code")
    search_fields = ("mobile_phone",)


class SMSTypeAdmin(admin.ModelAdmin):
    list_display = "id", "name"
    readonly_fields = "id",


class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = "name", "content"


admin.site.register(SMSMessage, SMSMessageAdmin)
admin.site.register(SMSType, SMSTypeAdmin)
admin.site.register(SMSTemplate, SMSTemplateAdmin)
admin.site.register(OTP, OTPAdmin)
