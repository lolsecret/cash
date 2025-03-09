import redis
from django.apps import AppConfig
from django.conf import settings
# from prometheus_redis_client import REGISTRY


class CoreConfig(AppConfig):
    name = 'apps.core'
    verbose_name = '1. Общие настройки'

    def ready(self):
        super().ready()

        # REGISTRY.set_redis(redis.from_url(settings.PROMETHEUS_REDIS_URI))
