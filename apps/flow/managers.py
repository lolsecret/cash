from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from apps.flow import ServiceStatus


class ServiceReasonQuerySet(QuerySet):
    def by_service(self, service):
        return self.filter(service=service, is_active=True)


class HistoryQuerySet(QuerySet):
    def find_cached_data(self, service, reference) -> QuerySet:
        return self.filter(
            service=service,
            reference_id=reference,
            created_at__gte=timezone.now() - timedelta(days=service.cache_lifetime),
            status=ServiceStatus.WAS_REQUEST,
            data__isnull=False,
        )


class StatusTriggerQuerySet(QuerySet):
    def find(self, status) -> QuerySet:
        return self.filter(status=status, is_active=True)
