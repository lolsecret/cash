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
        )
