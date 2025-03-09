from rest_framework import serializers

from apps.people.validators import IINRegexValidator, validate_iin

from .models import BlackListMember


class BlackListMemberSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for BlackListMember model
    """
    iin = serializers.CharField(
        label="ИИН",
        required=True,
        validators=[IINRegexValidator, validate_iin],
    )
    manager = serializers.CharField(source="manager.full_name", read_only=True)

    class Meta:
        model = BlackListMember
        exclude = ("changed_at",)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def create(self, validated_data):
        request = self.context["request"]
        return BlackListMember.objects.create(manager=request.user, **validated_data)
