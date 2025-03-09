from django import forms
from django.contrib import admin
from django.contrib.admin.options import get_content_type_for_model
from django.contrib.auth.admin import (
    GroupAdmin as BaseGroupAdmin,
    UserAdmin as BaseUserAdmin, sensitive_post_parameters_m
)
from django.contrib.auth.models import Group, Permission
from django.utils.translation import gettext_lazy as _

from .models import User, StatusPermission, RoleGroupPermissions, ProxyGroup
from ..references import AdminHistoryAction
from ..references.models import AdminHistory

admin.site.unregister(Group)


@admin.register(RoleGroupPermissions)
class RoleGroupPermissionAdmin(admin.ModelAdmin):
    list_display = ['role', ]
    filter_horizontal = ['group_permissions']


class RoleAdmin(BaseGroupAdmin):
    list_display = ("name", "get_partner_name", "get_staff_count")
    list_filter = ("partner__name",)

    def get_staff_count(self, instance):
        return instance.users.count()

    get_staff_count.short_description = "Количество сотрудников"

    def get_partner_name(self, instance):
        if instance.partner:
            return instance.partner.name
        return ""

    get_partner_name.short_description = "Партнер"

    def get_queryset(self, request):
        return (
            super()
                .get_queryset(request)
                .select_related("partner")
                .prefetch_related("users")
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (_("Personal info"), {
            "fields": (
                "email",
                "phone",
                ("last_name", "first_name"),
                "password",
                "role",
            )
        }),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "created", "modified")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2"), }),
    )
    readonly_fields = ("last_login", "created", "modified")
    list_display = ("__str__", "email", "is_staff", "is_active", "role")
    search_fields = ("email",)
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    ordering = ("email",)
    filter_horizontal = ()

    def log_addition(self, request, object, message):
        action_description = f'{AdminHistoryAction.ADDING.value}: {object.__str__()}'

        AdminHistory.objects.create(
            author=request.user,
            action_type=AdminHistoryAction.ADDING,
            content_type_id=get_content_type_for_model(object).pk,
            object_id=object.pk,
            field_name=object.__str__(),
            action_description=action_description,
        )
        return super().log_addition(request, object, message)

    def log_deletion(self, request, object, object_repr):
        action_description = f'{AdminHistoryAction.DELETE.value}: {object.__str__()}'

        AdminHistory.objects.create(
            author=request.user,
            action_type=AdminHistoryAction.DELETE,
            content_type_id=get_content_type_for_model(object).pk,
            object_id=object.pk,
            field_name=object_repr,
            action_description=action_description,
        )
        return super().log_addition(request, object, object_repr)

    def user_change_password(self, request, id, form_url=''):
        from django.contrib.admin.utils import unquote

        user = self.get_object(request, unquote(id))
        form = self.change_password_form(user, request.POST)
        if form.is_valid():
            action_description = f'{AdminHistoryAction.CHANGE.value}: {user.__str__()}'

            AdminHistory.objects.create(
                author=user,
                action_type=AdminHistoryAction.CHANGE,
                content_type_id=get_content_type_for_model(user).pk,
                object_id=user.pk,
                field_name="Password",
                action_description=action_description,
            )
        return super().user_change_password(request, id)


class StagePermission(forms.ModelForm):
    permission = forms.ModelChoiceField(queryset=Permission.objects.filter(
        content_type__model="creditapplication"  # noqa
    ))

    class Meta:
        model = StatusPermission
        fields = "__all__"


class StatusPermissionAdmin(admin.TabularInline):
    model = StatusPermission
    form = StagePermission


@admin.register(ProxyGroup)
class GroupAdmin(BaseGroupAdmin):
    list_display = ("name",)
    inlines = [
        StatusPermissionAdmin
    ]
    #
    # @admin.display(description="Количество сотрудников", ordering="users_count")
    # def get_staff_count(self, obj: Group):
    #     return obj.users_count
    #
    # def get_queryset(self, request):
    #     qs = super(GroupAdmin, self).get_queryset(request)
    #     return qs.annotate(users_count=Count("user__id"))

    def log_change(self, request, object, message):
        action_description = f'{AdminHistoryAction.CHANGE.value}: {object.__str__()}'
        if isinstance(message, list) and len(message):
            if "Permissions" in message[0].get('changed', {}).get('fields', []):
                AdminHistory.objects.create(
                    author=request.user,
                    action_type=AdminHistoryAction.CHANGE,
                    content_type_id=get_content_type_for_model(object).pk,
                    object_id=object.pk,
                    field_name="Permissions",
                    action_description=action_description,
                )
        return super().log_change(request, object, message)
