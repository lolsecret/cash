from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class NotificationTextType(TextChoices):
    CRM = 'CRM', _('CRM система')
    MFO_WEBSITE = 'MFO_WEBSITE', _('Сайт МФО')
