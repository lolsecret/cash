from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from apps.credits import CreditStatus
from apps.users import Roles


class EmailNotification(TimeStampedModel):
    class Meta:
        verbose_name = 'Email уведомление'
        verbose_name_plural = 'Email уведомление'

    status = models.CharField(_("Статус"), max_length=50, choices=CreditStatus.choices)
    subject = models.CharField(_("Тема"), max_length=255)
    text = models.TextField(_("Текст"))
    role = models.CharField(
        _("Роль"),
        max_length=30,
        choices=Roles.choices,
    )

    def __str__(self):
        return f"Email уведомление №{self.id} по статусу: {self.get_status_display()}"