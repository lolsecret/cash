from django.db.models import TextChoices


class SMSType(TextChoices):
    OTP = "OTP", "Отправка одноразового пароля"
    CABINET_PASSWORD = "CABINET_PASSWORD", "Отправка пароля от личного кабинета"
