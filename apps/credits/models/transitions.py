from typing import Optional, List, Union
import logging
from django.db import models
from django_fsm import transition, FSMField

from apps.credits import CreditStatus

logger = logging.getLogger(__name__)


class ModelStatusMixin:
    # class Meta:
    #     abstract = True

    class ChangeStatusException(Exception):
        """Ошибка смены статуса"""

    # status = models.CharField(
    #     "Статус",
    #     max_length=20,
    #     choices=CreditStatus.choices,
    #     default=CreditStatus.NEW,
    #     db_index=True,
    # )
    status = FSMField(
        choices=CreditStatus.choices,
        default=CreditStatus.NEW,
        # protected=True
    )

    # def change_status(
    #         self,
    #         source: Union[str, CreditStatus, List[CreditStatus]],
    #         target: CreditStatus,
    #         reason: Optional[str] = None,
    #         raise_exception: bool = False,
    #         on_error: Optional[CreditStatus] = None,
    # ) -> bool:
    #     conditions = dict()
    #
    #     if isinstance(source, str) and source == '*':
    #         """Nothing"""
    #
    #     elif isinstance(source, CreditStatus):
    #         conditions.update(status=source)
    #
    #     elif isinstance(source, list):
    #         conditions.update(status__in=source)
    #
    #     update_fields = dict(status=target)
    #
    #     if reason:
    #         update_fields.update(status_reason=reason)
    #
    #     success = self.__class__.objects.filter(**{'pk': self.pk, **conditions}).update(**update_fields)
    #
    #     if success == 0:
    #         error = f"error change status from source: {source} to target: {target} for application: {self.pk}"
    #         if raise_exception:
    #             raise self.ChangeStatusException(error)
    #
    #         if isinstance(on_error, CreditStatus):
    #             self.__class__.objects.filter(**{'pk': self.pk}).update(status=on_error)
    #
    #         return False
    #
    #     if hasattr(self, 'status_transitions'):
    #         self.status_transitions.create(status=target, reason=reason)
    #
    #     return True

    @transition(
        status,
        source=CreditStatus.NEW,
        target=CreditStatus.IN_PROGRESS
    )
    def in_check(self):
        """Запуск внутрених проверок"""

    @transition(
        status,
        source=CreditStatus.IN_PROGRESS,
        target=CreditStatus.IN_WORK
    )
    def in_work(self):
        """Направляем заявку в работу"""

    @transition(
        status,
        source=(CreditStatus.IN_WORK,),
        target=CreditStatus.CALLBACK
    )
    def callback(self):
        """Перезвонить"""

    @transition(
        status,
        source=CreditStatus.IN_WORK,
        target=CreditStatus.FIN_ANALYSIS
    )
    def fin_analysis(self):
        """Фин аланиз, необходимо получить кред. отчет"""

    @transition(
        status,
        source=(CreditStatus.IN_WORK, CreditStatus.FIN_ANALYSIS, CreditStatus.FILLING),
        target=CreditStatus.DECISION
    )
    def to_decision(self):
        """Отпрвляем на решение КК"""
        from apps.credits.models import CreditDecision

        CreditDecision.objects.create(credit=self)

    @transition(
        status,
        source=CreditStatus.DECISION,
        target=CreditStatus.DECISION_CHAIRPERSON
    )
    def to_decision_chairperson(self):
        """Ожидает решение председателя"""

    @transition(
        status,
        source=(CreditStatus.DECISION,
                CreditStatus.DECISION_CHAIRPERSON,
                CreditStatus.IN_WORK_CREDIT_ADMIN),
        target=CreditStatus.FILLING,
        permission="credits.can_return_for_revision"
    )
    def rework(self):
        """Отправляем на доработку"""

    @transition(
        status,
        source=(CreditStatus.DECISION_CHAIRPERSON,),
        target=CreditStatus.APPROVED
    )
    def to_approve(self):
        """Заявка одорбрена"""

    @transition(
        status,
        source=(CreditStatus.IN_PROGRESS,
                CreditStatus.IN_WORK,
                CreditStatus.DECISION,
                CreditStatus.DECISION_CHAIRPERSON),
        target=CreditStatus.REJECTED
    )
    def reject(self, reason, comment=None):
        """Заявка отказана КК, отправим уведомление клиенту"""
        self.reject_reason = reason
        self.status_reason = comment

    @transition(
        status,
        source='+',
        target=CreditStatus.ISSUANCE
    )
    def issuance(self):
        """Кредит отправлен на выдачу, запустим фоновое задание создание клиента и контракта"""

    @transition(
        status,
        source=CreditStatus.ISSUANCE,
        target=CreditStatus.ISSUED
    )
    def issued(self):
        """От 1С получаем callback Кредит выдан, отправим смс уведомление клиенту"""

    def get_transitions(self) -> dict:
        # TODO: нужно вынести от сюда, справочник скорее исключение
        return {
            CreditStatus.DECISION: self.to_decision,
            CreditStatus.FIN_ANALYSIS: self.fin_analysis,
            CreditStatus.REJECTED: self.reject,
            CreditStatus.ISSUANCE: self.issuance,
        }

    def status_trigger(self, status: CreditStatus):
        from apps.flow.models import StatusTrigger
        from apps.flow.services import Flow

        for process in StatusTrigger.objects.find(status=status):
            if process.pipeline:
                Flow(process.pipeline, self).run()  # noqa
