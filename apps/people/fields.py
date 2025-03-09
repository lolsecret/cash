from rest_framework.serializers import CharField

from .validators import IINRegexValidator, validate_iin


class IINField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label", "ИИН")
        kwargs["validators"] = [IINRegexValidator, validate_iin]

        super().__init__(*args, **kwargs)
