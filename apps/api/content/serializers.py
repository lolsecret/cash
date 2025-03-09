from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from apps.core.models import NotificationText
from apps.credits.models import Product
from apps.people.validators import IinValidator


class CallMeSerializer(serializers.Serializer):  # noqa
    phone = serializers.CharField(error_messages={'required': 'Ошибка: не заполнен поле Номер телефона'})
    name = serializers.CharField(error_messages={'required': 'Ошибка: не заполнено поле Фамилия Имя'})


class EmailSerializer(serializers.Serializer):  # noqa
    phone = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    text = serializers.CharField()


# "phone": "+7 (705) 197-25-15",
#     "iin": "870713300511",
#     "amount": 200000,
#     "month": 16,
#     "agree_personal_data": true,
#     "agree_contact_details": true,
#     "member_of_ip": true,
#     "utm_source": 2,
#     "repayment_method": 0
class CreditRequestSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    iin = serializers.CharField(
        min_length=12, max_length=12,
        validators=[IinValidator()]
    )
    amount = serializers.IntegerField()
    month = serializers.IntegerField()
    repayment_method = serializers.IntegerField()
    agree_personal_data = serializers.BooleanField()
    agree_contact_details = serializers.BooleanField()
    utm_source = serializers.CharField(allow_null=True)
    utm = serializers.DictField(required=False, allow_null=True)

    def validate_agree_personal_data(self, value):
        if not value:
            raise serializers.ValidationError(
                'Ошибка: нет согласие на сбор и обработку персональных данных'
            )
        return value

    def validate_agree_contact_details(self, value):
        if not value:
            raise serializers.ValidationError(
                'Ошибка: нет разрешение на доступ к контактным данным'
            )
        return value


class NotificationTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationText
        fields = '__all__'


class ProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'id',
            'interest_rate',
            'principal_limits',
            'period',
            'bonus_days'
        )
