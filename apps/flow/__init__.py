from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

default_app_config = 'apps.flow.apps.FlowConfig'


class ServiceStatus(TextChoices):
    NO_REQUEST = "NO_REQUEST", _('Не было запроса')
    WAS_REQUEST = "WAS_REQUEST", _('Был запрос')
    CHECKED = "CHECKED", _('Проверено')
    REQUEST_ERROR = "REQUEST_ERROR", _('Ошибка запроса')
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE", _('Сервис не доступен')
    CACHED_REQUEST = "CACHED_REQUEST", _('Заполнен из кэша')


class RejectReason(TextChoices):
    DUPLICATE_IN_CRM = 'DUPLICATE_IN_CRM', _("Дубликат ИИН в работе")
    BORROWER_NOT_ENTREPRENEUR = 'BORROWER_NOT_ENTREPRENEUR', _("Тип клиента не ИП")
    AGE_RESTRICTION_FOR_MEN = 'AGE_RESTRICTION_FOR_MEN', _("Не соответствует возрасту")
    AGE_RESTRICTION_FOR_WOMEN = 'AGE_RESTRICTION_FOR_WOMEN', _("Не соответствует возрасту")
    UNACCEPTABLE_AMOUNT = 'UNACCEPTABLE_AMOUNT', _("Не подходит по сумме")

    REJECT_PKB_SOHO = 'REJECT_PKB_SOHO', _("Отказ по ПКБ Soho")
    REJECT_FOR_CUSTOM_SCORING = 'REJECT_FOR_CUSTOM_SCORING', _("Отказ по ПКБ Custom Scoring")
    REJECT_ADDITIONAL_SOURCES = 'REJECT_ADDITIONAL_SOURCES', _("Отказ по ПКБ доп источникам")


class ServicePurposes(TextChoices):
    DEFAULT = "DEFAULT", _("По умолчанию")
    KYC = "KYC", _("Биометрия фото")
