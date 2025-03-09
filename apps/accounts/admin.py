from django.contrib import admin

from apps.accounts.models import Profile, ProfilePersonalRecord


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'iin', 'name', 'is_registered')
    search_fields = (
        'phone',
        'person__iin',
    )
    readonly_fields = (
        'phone',
        'password',
        'person',
        'date_joined',
        'last_login',
    )
    exclude = (
        'is_superuser',
        'is_staff',
        'groups',
        'user_permissions',
    )
    ordering = ('-pk',)

    def iin(self, instance: Profile):
        return instance.person and instance.person.iin

    def name(self, instance: Profile):
        return " ".join([instance.last_name, instance.last_name])


class ProfilePersonalRecordAdmin(admin.ModelAdmin):
    list_display = ('profile', 'document_type', 'document_number', 'bank_account_number', 'selfie_exists')
    search_fields = ('profile__person__iin', 'document_number', 'bank_account_number')
    readonly_fields = ('profile', 'similarity', 'attempts')

    def selfie_exists(self, instance: ProfilePersonalRecord):
        return bool(instance.selfie)

    selfie_exists.boolean = True


admin.site.register(Profile, ProfileAdmin)
admin.site.register(ProfilePersonalRecord, ProfilePersonalRecordAdmin)
