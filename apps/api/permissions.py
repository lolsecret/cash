from rest_framework.permissions import IsAuthenticated as IsAuthenticatedBase

from apps.accounts.models import Profile


class IsProfile(IsAuthenticatedBase):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and isinstance(request.user, Profile)


class IsProfileAuthenticated(IsAuthenticatedBase):
    def has_permission(self, request, view):
        is_profile = isinstance(request.user, Profile)
        return super().has_permission(request, view) and is_profile and request.user.is_registered
