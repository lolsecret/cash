from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError


class ProfileAlreadyExists(ValidationError):
    default_code = "profile_already_exists"
    default_detail = {'phone': [_('Пользователь с таким телефоном уже зарегистрирован, '
                                  'просим пройти авторизацию.')]}


class IsRegistered(ValidationError):
    default_code = "is_registered"
    default_detail = {'iin': [_('Данный пользователь уже зарегистрирован')]}


class PersonalRecordAlreadyExists(ValidationError):
    default_code = "personal_record_already_exists"
    default_detail = {'iin': [_('Данный пользователь уже внес свои данные')]}


class IsNotClient(ValidationError):
    default_code = "is_not_client"
    default_detail = {"iin": [_('Регистрация доступна клиентам ТОО МФО Quantum. '
                                'Для получения консультации обратитесь '
                                'в службу поддержки по телефону +7 (707) 500-03-33.')]}
