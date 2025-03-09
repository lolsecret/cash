from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers

from apps.core.serializers import ReadOnlySerializerMixin

from .models import (
    AdditionalContactRelation,
    Address,
    # ContactInfo,
    Person,
    # PersonalRecord,
    PersonalData,
)


class PersonSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()

    class Meta:
        model = Person
        exclude = ["id"]
        extra_kwargs = {"iin": {"read_only": True}}


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        exclude = ["id"]

#
# class ContactInfoSerializer(serializers.ModelSerializer):
#     mobile_phone = serializers.CharField(required=True)
#
#     class Meta:
#         model = ContactInfo
#         exclude = ["id"]
#
#
# class ContactInfoCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ContactInfo
#         fields = "__all__"
#
#
# class AdditionalContactSerializer(serializers.ModelSerializer):
#     contact = ContactInfoSerializer(required=True)
#     relationship = serializers.CharField(required=True)
#
#     class Meta:
#         model = AdditionalContactRelation
#         fields = ["contact", "relationship"]
#
#
# class PersonalRecordDataSerializer(WritableNestedModelSerializer):
#     person = PersonSerializer(read_only=True)
#     reg_address = AddressSerializer(read_only=True)
#     real_address = AddressSerializer()
#     additional_contacts = AdditionalContactSerializer(
#         source="additionalcontactrelation_set", many=True
#     )
#     email = serializers.EmailField(read_only=True, source="person.user.email")
#     email_confirmed = serializers.BooleanField(read_only=True, source='person.user.email_confirmed')
#
#     class Meta:
#         model = PersonalRecord
#         fields = (
#             "first_name",
#             "last_name",
#             "middle_name",
#             "mobile_phone",
#             "home_phone",
#             "work_phone",
#             "email",
#             "email_confirmed",
#             "person",
#             "reg_address",
#             "real_address",
#             "additional_contacts",
#             "marital_status",
#             "resident",
#             "citizenship",
#             "document_type",
#             "document_series",
#             "document_number",
#             "document_issue_date",
#             "document_issue_org",
#             "document_exp_date",
#             "dependants_child",
#             "dependants_additional",
#             "education",
#             "job_place",
#             "job_title",
#             "additional_income",
#             "additional_expenses",
#         )
#         extra_kwargs = {
#             "resident": {"read_only": True},
#             "citizenship": {"read_only": True},
#             "document_type": {"read_only": True},
#             "document_series": {"read_only": True},
#             "document_number": {"read_only": True},
#             "document_issue_date": {"read_only": True},
#             "document_issue_org": {"read_only": True},
#             "document_exp_date": {"read_only": True},
#         }
#
#
# class BorrowerRetrieveSerializer(ReadOnlySerializerMixin, serializers.ModelSerializer):
#     person = PersonSerializer()
#     reg_address = AddressSerializer(read_only=True)
#     real_address = AddressSerializer()
#     additional_contacts = AdditionalContactSerializer(
#         source="additionalcontactrelation_set", many=True
#     )
#     email = serializers.EmailField(source="person.user.email")
#     email_confirmed = serializers.BooleanField(source='person.user.email_confirmed')
#
#     class Meta:
#         model = PersonalRecord
#         fields = (
#             "first_name",
#             "last_name",
#             "middle_name",
#             "mobile_phone",
#             "home_phone",
#             "work_phone",
#             "email",
#             "email_confirmed",
#             "person",
#             "reg_address",
#             "real_address",
#             "additional_contacts",
#             "marital_status",
#             "resident",
#             "citizenship",
#             "document_type",
#             "document_series",
#             "document_number",
#             "document_issue_date",
#             "document_issue_org",
#             "document_exp_date",
#             "dependants_child",
#             "dependants_additional",
#             "education",
#             "job_place",
#             "job_title",
#             "additional_income",
#             "additional_expenses",
#         )


class PersonalDataShortSerializer(serializers.ModelSerializer):
    document_exp_date = serializers.DateField(format="%d.%m.%Y")

    class Meta:
        model = PersonalData
        fields = (
            "first_name",
            "last_name",
            "middle_name",
            "document_type",
            "document_number",
            "document_exp_date",
            "bank_account_number"
        )
