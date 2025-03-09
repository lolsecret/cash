from django.contrib import admin
from django.forms import Textarea
from django.db.models import TextField

from . import models


class HiddenAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}  # Hide model in admin list


class ChangeOnlyMixin:
    def has_add_permission(self, request, obj=None):  # noqa
        return False


class ReadOnlyMixin(ChangeOnlyMixin):
    def has_change_permission(self, request, obj=None):  # noqa
        return False


class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'index', 'address', 'parent')


class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch_code')


class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'bic')


class PrintFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    formfield_overrides = {
        TextField: {'widget': Textarea(attrs={'rows': 40, 'cols': 160})}
    }


class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created",
        "modified",
    )


class FAQAdmin(admin.ModelAdmin):
    list_display = (
        'question',
        'created',
        'modified',
    )


class NotificationTextAdmin(admin.ModelAdmin):
    list_display_links = ('code',)
    list_display = (
        'type',
        'code',
        'created',
        'modified',
    )
    list_filter = ('type',)
    search_fields = ('code', 'text')


class CreditIssuancePlanAdmin(admin.ModelAdmin):
    list_display = 'issuance_plan', 'year', 'month'


admin.site.register(models.Branch, BranchAdmin)
admin.site.register(models.City, CityAdmin)
admin.site.register(models.Bank, BankAdmin)
admin.site.register(models.PrintForm, PrintFormAdmin)
admin.site.register(models.Document, DocumentAdmin)
admin.site.register(models.FAQ, FAQAdmin)
admin.site.register(models.NotificationText, NotificationTextAdmin)
admin.site.register(models.CreditIssuancePlan, CreditIssuancePlanAdmin)
