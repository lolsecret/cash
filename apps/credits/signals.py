from typing import Type, Any, Dict

from constance import config
from django.conf import settings
from django.contrib.admin.options import get_content_type_for_model
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver

from apps.credits.calculators import calc_aeir
from apps.credits.models import StatusTransition, CreditParams, CreditApplication
from apps.credits.tasks import send_email_notification
from apps.references import AdminHistoryAction
from apps.references.models import AdminHistory


# @receiver(post_delete, sender=StatusTransition)
# def on_status_transition(
#         sender: Type[StatusTransition],
#         instance: StatusTransition,
#         created: bool,
#         **kwargs: Dict[str, Any]
# ) -> None:
#     pass


@receiver(pre_save, sender=CreditParams)
def on_change_credit_params(
        sender: Type[CreditParams],
        instance: CreditParams,
        **kwargs: Dict[str, Any]
) -> None:
    instance.aeir = calc_aeir(
        instance.principal,
        instance.interest_rate,
        instance.contract_date,
        instance.calculator.payments
    )


@receiver(pre_save, sender=CreditApplication)
def on_change_credit_application(
        sender: Type[CreditApplication],
        instance: CreditApplication,
        **kwargs
) -> None:
    if instance._state.adding:  # noqa // new object will be created
        pass
    else:
        previous = CreditApplication.objects.get(id=instance.id)
        if previous.status != instance.status:
            if settings.EMAIL_ENABLE:
                send_email_notification.delay(instance.pk, instance.status)

            instance.status_transitions.create(status=instance.status, reason=instance.status_reason)

            field_name = "Status"
            action_description = {AdminHistoryAction.CHANGE.value: instance.__str__()}
            history = AdminHistory.objects.create(
                action_type=AdminHistoryAction.CHANGE,
                content_type_id=get_content_type_for_model(instance).pk,
                object_id=instance.pk,
                field_name=field_name,
                field_after=instance.status,
                field_before=previous.status,
                action_description=action_description,
            )


# @receiver(post_save, sender=CreditApplication)
# def on_change_credit_application(
#         sender: Type[CreditApplication],
#         instance: CreditApplication,
#         **kwargs
# ) -> None:
#     pass
