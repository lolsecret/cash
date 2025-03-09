from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Профиль пользователя"

    def ready(self):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from apps.accounts.authentication import CustomJSONWebTokenAuthentication
        # Override JWTAuthentication with custom implementation
        JWTAuthentication = CustomJSONWebTokenAuthentication
