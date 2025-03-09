from rest_framework import serializers

from apps.credits.api.serializers import PersonContactSerializer
from apps.people.models import PersonalData
from apps.people.serializers import PersonSerializer


class ProfileDataSerializer(serializers.ModelSerializer):
    person = PersonSerializer()
    additional_contacts = PersonContactSerializer(many=True)

    class Meta:
        model = PersonalData
        fields = (
            "first_name",
            "last_name",
            "middle_name",
            "mobile_phone",
            "person",
            "additional_contacts",
        )