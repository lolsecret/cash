from typing import Optional, AnyStr
import re
import math
from datetime import date

from django.db.models import QuerySet, Manager
from django.core.exceptions import ValidationError


class PersonInfoFromIin:
    IIN_REGEX = re.compile(r'^(?P<year>[0-9]{2})'
                           r'(?P<month>[0-9]{2})'
                           r'(?P<day>[0-9]{2})'
                           r'(?P<gender>[0-9])[0-9]{5}')
    GENDER = ['FEMALE', 'MALE']
    CENTURY = [18, 19, 20]

    def __init__(self, value):
        self._matched_re: Optional[re.Match[AnyStr]] = None
        self.birthday: Optional[date] = None
        self.gender: Optional[str] = None
        self._validate_iin(value)
        self._parse_iin()

    def _validate_iin(self, value):
        self._matched_re = re.match(self.IIN_REGEX, value)

    def _parse_iin(self):
        try:
            result = {k: v for k, v in self._matched_re.groupdict().items()}
            self.gender = self.GENDER[int(result['gender']) % 2]
            century = int(abs(math.ceil(int(result["gender"]) / 2) - 1))
            year = f'{self.CENTURY[century]}{result["year"]}'
            self.birthday = date(int(year), int(result["month"]), int(result["day"]))
        except Exception:
            raise ValidationError("Не валидный ИИН")

    def as_dict(self):
        return {
            "birthday": self.birthday,
            "gender": self.gender
        }


class PersonQueryset(QuerySet):
    def registered(self):
        return self.filter(user__isnull=False)

    def active(self):
        return self.filter(user__is_active=True)

    def inactive(self):
        return self.filter(user__is_active=False)

    def with_records(self):
        return self.filter(records__isnull=False).distinct()

    def get_create_from_iin(self, iin: str):
        parsed_iin = PersonInfoFromIin(iin)
        instance, _ = self.get_or_create(iin=iin, defaults=parsed_iin.as_dict())
        return instance


class PersonFromIinManager(Manager):
    def create(self, iin: str):
        parsed_iin = PersonInfoFromIin(iin)
        instance, created = self.update_or_create(
            iin=iin,
            defaults={'birthday': parsed_iin.birthday, 'gender': parsed_iin.gender}
        )
        return instance
