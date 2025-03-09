from rest_framework import serializers
from drf_writable_nested.mixins import NestedUpdateMixin

from apps.people.models import PersonalData
from apps.people.serializers import AddressSerializer


class BorrowerSerializer(NestedUpdateMixin, serializers.ModelSerializer):
    reg_address = AddressSerializer()
    real_address = AddressSerializer(required=False)

    class Meta:
        model = PersonalData
        exclude = ("mobile_phone",)
