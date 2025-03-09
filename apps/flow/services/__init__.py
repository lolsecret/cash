from typing import Any, Dict, Optional, TYPE_CHECKING, Union
import logging

from contextlib import suppress
from celery import chain
from celery.result import AsyncResult

from apps.core.utils import generate_uid
from apps.flow import RejectReason
from apps.flow.integrations.exceptions import RejectRequestException, ServiceErrorException, ServiceUnavailable
from apps.flow.models import Pipeline

if TYPE_CHECKING:
    from apps.credits.models import Lead, CreditApplication

logger = logging.getLogger(__name__)


class Flow:
    def __init__(
            self,
            pipeline: Pipeline,
            instance: Union['Lead', 'CreditApplication'],
            pipeline_data: Optional[Dict[str, Any]] = None,
            retry: bool = False,
            uid: Optional[str] = None,
    ):
        self.pipeline = pipeline
        self.instance = instance
        self.pipeline_data = pipeline_data or {}
        self.retry = retry
        self.data = {"pipeline_id": self.pipeline.pk, "get_cache": retry, 'uid': uid or generate_uid()}

    def run(self):
        logger.info("Pipeline.Flow: run %s", self.pipeline)
        try:
            if self.retry:
                return self.retry_failed_jobs()

            elif self.pipeline.background:
                return self.chained_async_jobs()

            return self.run_jobs()

        except Exception as exc:
            logger.error('Pipeline.run: error %s', exc, exc_info=True)

    def retry_failed_jobs(self):
        for service in self.pipeline.retry_jobs(self.instance):
            logger.info("Retry failed service: service %s begin", service)
            try:
                service.service.get_class(self.instance, **self.data).run_service()
                logger.info('Retry failed service: service %s success', service)
            except Exception as exc:
                logger.error("Retry failed service: service %s failed, error %s", service, exc)
            #     if service.raise_exception:
            #         raise exc
            logger.info('Retry failed service: service %s end', service)

    def run_jobs(self) -> None:
        for service in self.pipeline.active_jobs():
            logger.info("Pipeline.Flow: service %s begin job", service)
            try:
                service.service.get_class(self.instance, **self.data).run_service()

            except RejectRequestException as exc:
                logger.error("Pipeline.Flow: error %s", exc)
                # TODO: добавить перевод ошибки
                error = str(exc)
                with suppress(KeyError):
                    error = RejectReason[error]

                self.instance.reject(reason_code=error)

                # Если нужно прервать цепочку действий
                if service.raise_exception:
                    raise exc

                return

            logger.info("Pipeline.Flow: service %s end job")

    def chained_async_jobs(self) -> AsyncResult:
        from apps.flow.tasks import ServiceTask
        jobs = []
        task = ServiceTask()
        for service in self.pipeline.active_jobs():
            app_model = '%s.%s' % (self.instance._meta.app_label, self.instance._meta.model_name)  # noqa
            jobs.append(
                task.si(
                    app_model=app_model,
                    instance_id=self.instance.id,
                    service_pk=service.service.pk,
                    pipeline_data=self.pipeline_data,
                    data=self.data,
                )
            )
        return chain(*jobs)()
