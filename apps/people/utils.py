from typing import Optional, Match, AnyStr
import re
import math
from datetime import date

from django.core.exceptions import ValidationError

from . import Gender

CENTURY = {
    1: 18,
    2: 18,
    3: 19,
    4: 19,
    5: 20,
    6: 20,
}


def get_birthday_from_iin(iin: str) -> date:
    year = int(iin[:2])
    month = int(iin[2:4])
    day = int(iin[4:6])

    century = CENTURY.get(int(iin[6]), 20)
    year += century * 100

    return date(year, month, day)


def get_gender_from_iin(iin: str):
    gender_digit = int(iin[6])
    if gender_digit % 2 == 0:
        return Gender.FEMALE
    return Gender.MALE


class PersonInfoFromIin:
    IIN_REGEX = re.compile(r'^(?P<year>[0-9]{2})'
                           r'(?P<month>[0-9]{2})'
                           r'(?P<day>[0-9]{2})'
                           r'(?P<gender>[1-6])[0-9]{5}')
    GENDER = ['FEMALE', 'MALE']
    CENTURY = [18, 19, 20]

    def __init__(self, value):
        self._matched_re: Optional[Match[AnyStr]] = None
        self.birthday: Optional[date] = None
        self.gender: Optional[str] = None
        self._validate_iin(value)
        self._parse_iin()

    def _validate_iin(self, value):
        self._matched_re = re.match(self.IIN_REGEX, value)

    def _parse_iin(self):
        try:
            result = {k: int(v) for k, v in self._matched_re.groupdict().items()}
            self.gender = self.GENDER[result['gender'] % 2]
            century = math.ceil(result["gender"] / 2) - 1
            year = f'{self.CENTURY[century]}{result["year"]}'
            self.birthday = date(int(year), result["month"], result["day"])
        except Exception:
            raise ValidationError(_("IIN parsing error"))


def convert_gender_from_gbdfl(gender_ru: str): # noqa
    gender = {'Мужской': 'MALE', 'Женский': 'FEMALE'} # noqa
    return gender[gender_ru]
