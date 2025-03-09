import base64

from django.conf import settings
from rest_framework.permissions import BasePermission


class BaseAuthPermission(BasePermission):
    message = 'not allowed'

    def has_permission(self, request, view):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return False

        token_type, _, credentials = auth_header.partition(' ')
        username, password = base64.b64decode(credentials).decode().split(':')

        if not username or not settings.CALLBACK_1C_USERNAME == username:
            return False

        elif not password or not settings.CALLBACK_1C_PASSWORD == password:
            return False

        else:
            return True
