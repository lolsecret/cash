from django.apps import AppConfig


class CreditsConfig(AppConfig):
    name = 'apps.credits'
    verbose_name = "Кредитные заявки"

    def ready(self):
        import apps.credits.signals  # noqa
