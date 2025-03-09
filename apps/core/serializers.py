from django.core.validators import validate_slug
from rest_framework import serializers
from rest_framework.fields import Field

from apps.credits.models.product import Channel


class ReadOnlySerializerMixin(Field):
    def __new__(cls, *args, **kwargs):
        setattr(
            cls.Meta, "read_only_fields",
            [field.name for field in cls.Meta.model._meta.get_fields()],
        )
        return super(ReadOnlySerializerMixin, cls).__new__(cls, *args, **kwargs)


class IntegerRangeSerializer(serializers.Serializer):
    min = serializers.IntegerField(required=True)
    max = serializers.IntegerField(required=True)

    def to_representation(self, instance) -> dict:
        representation = dict()
        representation["min"] = instance.lower
        representation["max"] = instance.upper - 1

        return representation


class DecimalRangeSerializer(IntegerRangeSerializer):
    min = serializers.DecimalField(max_digits=19, decimal_places=2, required=True)
    max = serializers.DecimalField(max_digits=19, decimal_places=2, required=True)

    def to_representation(self, instance) -> dict:
        representation = dict()
        representation["min"] = instance.lower
        representation["max"] = instance.upper

        return representation


class TextChoiceSerializer(serializers.Serializer):
    const_name = serializers.CharField()
    name = serializers.CharField()


class DashboardDateSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, allow_null=True, input_formats=["%Y-%m-%d"])
    end_date = serializers.DateField(required=False, allow_null=True, input_formats=["%Y-%m-%d"])
    channel = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        validate_data = super().validate(attrs)
        if validate_data.get('channel'):
            channel = Channel.objects.get(id=validate_data.get('channel'))
            validate_data['channel'] = channel

        return validate_data
