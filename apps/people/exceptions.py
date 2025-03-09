from rest_framework.exceptions import ValidationError


class InvalidIin(ValidationError):
    default_detail = "Неверный ИИН"
