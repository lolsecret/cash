from typing import Any, Dict

from celery import Task, shared_task
from django.apps import apps

from config import celery_app
from .integrations.exceptions import RejectRequestException
from .models import ExternalService


class ServiceTask(Task):
    name = 'flow.ServiceTask'
    throws = RejectRequestException

    def run(
            self,
            app_model: str,
            instance_id: int,
            service_pk: int,
            pipeline_data: Dict[str, Any],
            data: Dict[str, Any]
    ) -> None:
        model = apps.get_model(app_model)
        instance = model.objects.get(id=instance_id)

        service = ExternalService.objects.get(pk=service_pk)
        service.get_class(instance, cached_data=None, **data).run_service()


@shared_task
def run_service_background(service_id, obj_id, model_name):
    from django.apps import apps
    service = ExternalService.objects.get(id=service_id)
    Model = apps.get_model(model_name)
    obj = Model.objects.get(id=obj_id)

    service.run_service(obj)


celery_app.register_task(ServiceTask())
