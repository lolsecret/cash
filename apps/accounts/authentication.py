from django.utils.translation import gettext as _
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from django.apps import apps

def generate_access_token(user):
    """
    Generates an access token for the given user.
    """
    token = AccessToken.for_user(user)
    token["username"] = user.get_username()
    return str(token)

class CustomJSONWebTokenAuthentication(JWTAuthentication):
    """
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string specified in the setting
    `JWT_AUTH_HEADER_PREFIX`. For example:

        Authorization: Bearer <token>
    """

    def authenticate(self, request):
        """
        Overrides the default authenticate method to handle custom authentication.
        """
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def get_user(self, validated_token):
        """
        Returns an active user that matches the payload's user id.
        """
        username = validated_token.get("username")
        if not username:
            msg = _('Invalid payload.')
            raise exceptions.AuthenticationFailed(msg)

        Profile = apps.get_model("accounts", "Profile")
        try:
            user = Profile.objects.get_by_natural_key(username)
        except Profile.DoesNotExist:
            msg = _('Invalid signature.')
            raise exceptions.AuthenticationFailed(msg)

        if not user.is_active:
            msg = _('Profile account is disabled.')
            raise exceptions.AuthenticationFailed(msg)

        return user
