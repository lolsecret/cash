from django.db import models


class CreditApplicationVerigram(models.Model):
    """Поля для интеграции с сервисом Verigram Flow"""

    verigram_flow_id = models.CharField(
        "ID Flow Verigram",
        max_length=100,
        null=True,
        blank=True,
    )
    verigram_flow_url = models.URLField(
        "URL Flow Verigram",
        max_length=1000,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True
