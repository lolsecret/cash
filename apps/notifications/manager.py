from datetime import timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone


class OTPQueryset(QuerySet):
    def expired(self):
        created_max = timezone.now() - timedelta(minutes=settings.OTP_VALIDITY_PERIOD)
        return self.filter(created__lt=created_max)

    def active(self):
        created_min = timezone.now() - timedelta(minutes=settings.OTP_VALIDITY_PERIOD)
        return self.filter(created__gte=created_min, verified=False)
