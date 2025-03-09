import orjson
from lxml import etree

from django.db import models
from django.utils.translation import gettext_lazy as _


class Log(models.Model):
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_WARNING = 'WARNING'
    STATUS_ERROR = 'ERROR'

    STATUSES = (
        (STATUS_SUCCESS, 'Успешно'),
        (STATUS_WARNING, 'Предупреждение'),
        (STATUS_ERROR, 'Ошибка'),
    )

    id = models.BigAutoField(primary_key=True)
    uid = models.CharField("uid", max_length=32, blank=True, null=True, db_index=True)
    conversation_id = models.CharField(max_length=32, blank=True, null=True)
    status = models.CharField(_("Status"), max_length=10, choices=STATUSES, default=STATUS_SUCCESS)
    iin = models.CharField(max_length=12, blank=True, null=True, db_index=True)
    level = models.CharField(_("Level"), max_length=10)
    time = models.DateTimeField("Time", auto_now_add=True, db_index=True)
    method = models.CharField(_("Method"), max_length=128, db_index=True)
    content = models.TextField(_("Content"))
    token = models.TextField(_("Token"), blank=True, null=True)
    response_status = models.PositiveSmallIntegerField(_("Response code"), blank=True, null=True)
    runtime = models.PositiveSmallIntegerField(_("Runtime"), blank=True, null=True)

    class Meta:
        ordering = ['-pk']

    @property
    def pretty_message(self):
        message = self.content

        try:
            message = orjson.loads(message)
            return orjson.dumps(message, option=orjson.OPT_INDENT_2).decode('utf-8')

        except Exception as exc:  # noqa

            try:
                root = etree.fromstring(message)
                pretty = etree.tostring(root, encoding='utf-8', pretty_print=True)
                return pretty.decode()

            except Exception as exc:  # noqa
                pass

        return message
