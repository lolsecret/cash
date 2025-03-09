from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class InvalidIin(ValidationError):
    default_detail = "Неверный ИИН"


class CreditContractNotFound(ValidationError):
    default_code = "credit_contract_not_found"
    default_detail = {'iin': [_('У данного ИИНа не найден контракт')]}