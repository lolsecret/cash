from django.contrib import admin

from apps.core.admin import HiddenAdmin

from .models import (
    AdditionalContactRelation,
    Address,
    PersonContact,
    Person,
    PersonalData,
    BankAccount,
)


class PersonalRecordMixin:
    fieldsets = (
        (None, {"fields": (("first_name", "last_name", "middle_name"),)}),
        (
            "Документ",
            {
                "fields": (
                    ("document_type", "document_series", "document_number"),
                    ("document_issue_date", "document_exp_date", "document_issue_org"),
                )
            },
        ),
        (
            "Общая информация",
            {
                "fields": (
                    ("resident", "citizenship"),
                    ("marital_status", "dependants_child", "dependants_additional"),
                    "education",
                    ("job_place", "job_title"),
                )
            },
        ),
        (
            "Контактная информация",
            {
                "fields": (
                    ("reg_address", "real_address"),
                    ("mobile_phone", "home_phone", "work_phone"),
                )
            },
        ),
        (
            "Реквизиты",
            {
                "fields": (
                    "bank",
                    "bank_account_number",
                )
            },
        ),
    )
    readonly_fields = ("reg_address", "real_address")


class PersonalRecordInline(PersonalRecordMixin, admin.StackedInline):
    extra = 0
    model = PersonalData


class PersonAdmin(admin.ModelAdmin):
    inlines = (PersonalRecordInline,)
    list_display = ('iin',)
    search_fields = ('iin',)
    readonly_fields = ('iin', 'gender', 'birthday')

    def has_module_permission(self, request):
        return False


class AdditionalContactInline(admin.TabularInline):
    extra = 0
    model = AdditionalContactRelation
    classes = ('collapse',)


class BankAccountInline(admin.TabularInline):
    model = BankAccount


class PersonalDataAdmin(PersonalRecordMixin, admin.ModelAdmin):
    list_display = ('id', 'get_iin', 'full_name', 'created')
    inlines = (AdditionalContactInline, BankAccountInline)
    readonly_fields = ('reg_address', 'real_address')

    search_fields = ('person__iin', 'first_name', 'last_name')

    def get_iin(self, instance: PersonalData):  # noqa
        return instance.person.iin


admin.site.register(Address, HiddenAdmin)
admin.site.register(PersonContact, HiddenAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(PersonalData, PersonalDataAdmin)
