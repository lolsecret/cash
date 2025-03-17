from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    name = serializers.ReadOnlyField(source='__str__')

    class Meta:
        model = User
        fields = (
            'id',
            'last_name',
            'first_name',
            'middle_name',
            'name',
            'email',
            'phone',
            'role',
            'is_active',
            'branch'
        )

class EmailAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Email")
    password = serializers.CharField(
        label="Password",
        style={'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Пытаемся аутентифицировать пользователя с email и паролем
            user = authenticate(
                request=self.context.get('request'),
                email=email,
                password=password
            )

            # Если аутентификация не удалась
            if not user:
                msg = 'Невозможно войти с предоставленными учетными данными.'
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = 'Должны быть указаны "email" и "password".'
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs
