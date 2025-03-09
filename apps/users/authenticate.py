from django.contrib.auth.backends import  ModelBackend, Permission
from apps.users.models import RoleGroupPermissions


class CustomUserModelBackend(ModelBackend):

    def _get_user_permissions(self, user_obj):
        perms = user_obj.get_user_role_permissions()
        return perms

    def _get_group_permissions(self, user_obj):
        return user_obj.get_user_role_permissions()

