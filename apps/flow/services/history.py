from typing import Type, Union
import logging
from collections import OrderedDict

from datetime import timedelta

from django.utils import timezone

from apps.credits.models import Guarantor
from apps.flow import ServiceStatus
from apps.flow.mixins import ServiceHistoryMixin
from apps.flow.models import ExternalService

logger = logging.getLogger(__name__)


class BaseHistory:
    instance: 'ServiceHistoryMixin'
    service: ExternalService

    save_response: bool = False
    history_url: str
    history_method: str = 'POST'
    status: ServiceStatus
    data: dict

    last_request: Union[bytes, str, None] = ''
    last_response: Union[bytes, str, None] = ''

    runtime: float = 0
    pipeline_id: int
    request_id: str

    def log_save(self):
        if hasattr(self.instance, 'history'):
            data = getattr(self, 'data', None)
            status = getattr(self, 'status', ServiceStatus.NO_REQUEST)
            runtime = getattr(self, 'runtime', 0)

            log_extra = {
                'instance_id': self.instance.pk,
                'service': self.service.name,
                'reference_id': self.instance.get_reference(),
                'status': status,
                'runtime': runtime,
            }

            try:
                history_model: Type['ServiceHistoryMixin'] = self.instance.history.model
                history = history_model.objects.create(
                    content_object=self.instance,
                    reference_id=self.instance.get_reference(),
                    service=self.service,
                    status=status,
                    runtime=runtime,
                    pipeline_id=self.pipeline_id,
                    request_id=self.request_id,
                )

                if isinstance(data, (dict, list, OrderedDict)):
                    try:
                        logger.info("History.log_save try history.data")
                        history.data = getattr(self, 'data', None)
                        history.save(update_fields=['data'])
                        logger.info("History.log_save success history.data")

                    except Exception as exc:
                        logger.error('history.set_response Exception:', exc, extra=log_extra)

                if self.save_response:
                    try:
                        logger.info("History.log_save try history.set_response")
                        response_model = history.set_response(
                            url=getattr(self, 'history_url', None),
                            method=getattr(self, 'history_method', None),
                            request=self.last_request,
                            response=self.last_response,
                        )
                        logger.info("History.log_save success history.set_response #history_id=%s", response_model.pk)

                    except Exception as exc:
                        logger.error('history.set_response Exception:', exc, extra=log_extra)

            except Exception as exc:
                logger.error("BaseHistory.log_save exception %s", exc, extra=log_extra)


def clean_oldest_log(hours=24):
    from apps.flow.models import ServiceResponse
    ServiceResponse.objects.only('created_at') \
        .filter(created_at__lte=timezone.now() - timedelta(hours=hours)) \
        .delete()
