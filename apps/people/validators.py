from django.core.validators import RegexValidator

from .exceptions import InvalidIin


class IinValidator(RegexValidator):
    message = "Неверный ИИН"
    regex = r'^[0-9]{2}[0-9]{2}[0-9]{2}[0-9]{1}[0-9]{4}[0-9]{1}'

    def check(self, value: str) -> None:
        control_sum: int = 0
        counter: int = 1

        for item in range(0, len(value) - 1):
            control_sum += int(value[item]) * counter
            counter += 1

        if control_sum % 11 == 10:
            control_sum = 0
            counter = 3

            for item in range(0, len(value) - 1):
                control_sum += int(value[item]) * counter
                counter += 1
                if counter == 12:
                    counter = 1

        if control_sum % 11 != int(value[11]):
            raise InvalidIin(self.message, code=self.code)

    def __call__(self, value):
        super().__call__(value)
        self.check(value)
