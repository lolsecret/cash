from django.db.models import IntegerChoices, TextChoices


class BlackListReason(TextChoices):
    AML = "AML", "Член списка ПОДФТ"
    OTHER = "Other", "Другая причина"

    @classmethod
    def as_dict(cls):
        return {key: value for key, value in cls.choices}


class BlackListSource(IntegerChoices):
    EGOV = 0, "Egov"
    CUSTOM = 1, "Добавлен вручную"


class AdminHistoryAction(TextChoices):
    CHANGE = "CHANGE", "Изменение"
    DELETE = "DELETE", "DELETE"
    ADDING = "ADDING", "Добавление"
    RETRY = "RETRY", "Ретрай"

