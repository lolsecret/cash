from django.db.models import TextChoices


class MaritalStatus(TextChoices):
    MARRIED = "MARRIED", "Женат/замужем"
    SINGLE = "SINGLE", "Холост/не замужем"
    DIVORCED = "DIVORCED", "Разведен(а)"
    WIDOW = "WIDOW", "Вдовец/вдова"


class Gender(TextChoices):
    MALE = "MALE", "Мужской"
    FEMALE = "FEMALE", "Женский"


class RelationshipType(TextChoices):
    SPOUSE = "SPOUSE", "Супруг(а)"
    RELATIVE = "RELATIVE", "Родственник"
    FRIEND = "FRIEND", "Друг/Подруга"
