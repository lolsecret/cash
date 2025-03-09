from base64 import b64encode

from django.db import transaction
from rest_framework import serializers

from apps.credits.models import (
    Lead,
    CreditApplication,
    CreditReport,
    CreditHistory,
    CreditHistoryStatus,
    NegativeStatus, Guarantor,
)


class PKBSohoScoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditReport
        fields = (
            'lead',
            'soho_id_query',
            'soho_score',
        )


class PKBCustomScoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditReport
        fields = (
            'lead',
            'custom_scoring_flags',
        )


class CurrentCreditHistorySerializer(serializers.ModelSerializer):
    status = serializers.HiddenField(default=CreditHistoryStatus.CURRENT)

    class Meta:
        model = CreditHistory
        exclude = ("credit",)


class TerminatedCreditHistorySerializer(serializers.ModelSerializer):
    status = serializers.HiddenField(default=CreditHistoryStatus.TERMINATED)

    class Meta(CurrentCreditHistorySerializer.Meta):
        pass


class NegativeContractStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = NegativeStatus
        exclude = ("credit",)


class NegativeClientStatusSerializer(NegativeContractStatusSerializer):
    class Meta(NegativeContractStatusSerializer.Meta):
        exclude = ("credit", "status_id", "role", "role_code")


class CreditReportSerializer(serializers.ModelSerializer):
    negative_contract_statuses = NegativeContractStatusSerializer(many=True)
    negative_client_statuses = NegativeClientStatusSerializer(many=True)
    existing_contracts = CurrentCreditHistorySerializer(many=True)
    terminated_contracts = TerminatedCreditHistorySerializer(many=True)
    queries_30 = serializers.IntegerField()
    queries_90 = serializers.IntegerField()
    queries_120 = serializers.IntegerField()
    queries_180 = serializers.IntegerField()
    queries_360 = serializers.IntegerField()

    class Meta:
        model = CreditReport
        fields = (
            "negative_contract_statuses",
            "negative_client_statuses",
            "existing_contracts",
            "terminated_contracts",
            "queries_30",
            "queries_90",
            "queries_120",
            "queries_180",
            "queries_360",
        )

    def update(self, instance: CreditApplication, validated_data: dict):
        CreditReport.objects.update_or_create(
            # lead=instance,
            credit=instance,
            defaults={
                "pkb_query_last_30": validated_data["queries_30"],
                "pkb_query_last_90": validated_data["queries_90"],
                "pkb_query_last_120": validated_data["queries_120"],
                "pkb_query_last_180": validated_data["queries_180"],
                "pkb_query_last_360": validated_data["queries_360"],
            }
        )

        contracts = []
        for contract in validated_data["existing_contracts"]:
            contract["credit"] = instance
            contracts.append(CreditHistory(**contract))

        for contract in validated_data["terminated_contracts"]:
            contract["credit"] = instance
            contracts.append(CreditHistory(**contract))

        negative_statuses = []
        for contract in validated_data["negative_contract_statuses"]:
            contract["credit"] = instance
            negative_statuses.append(NegativeStatus(**contract))

        for contract in validated_data["negative_client_statuses"]:
            contract["credit"] = instance
            negative_statuses.append(NegativeStatus(**contract))

        with transaction.atomic():
            # Clean history before create new history
            instance.credit_history.all().delete()

            CreditHistory.objects.bulk_create(contracts)

            # Очистим историю перед новых сохранением
            instance.negative_statuses.all().delete()

            NegativeStatus.objects.bulk_create(negative_statuses)

        if hasattr(instance, 'credit_finance'):
            credit_finance = instance.credit_finance
            credit_finance.credit_debt_current = credit_finance.get_credit_debt_current_from_credit_history()
            credit_finance.save(update_fields=['credit_debt_current'])

        return instance


class CreditReportGuarantorSerializer(CreditReportSerializer):
    class Meta:
        model = CreditReport
        fields = CreditReportSerializer.Meta.fields

    def update(self, instance: Guarantor, validated_data: dict):
        CreditReport.objects.update_or_create(
            guarantor=instance,
            defaults={
                "pkb_query_last_30": validated_data["queries_30"],
                "pkb_query_last_90": validated_data["queries_90"],
                "pkb_query_last_120": validated_data["queries_120"],
                "pkb_query_last_180": validated_data["queries_180"],
                "pkb_query_last_360": validated_data["queries_360"],
            }
        )

        contracts = []
        for contract in validated_data["existing_contracts"]:
            contract["credit"] = instance.credit
            # contract["guarantor"] = instance
            contracts.append(CreditHistory(**contract))

        for contract in validated_data["terminated_contracts"]:
            contract["credit"] = instance.credit
            # contract["guarantor"] = instance
            contracts.append(CreditHistory(**contract))

        negative_statuses = []
        for contract in validated_data["negative_contract_statuses"]:
            contract["credit"] = instance.credit
            # contract["guarantor"] = instance
            negative_statuses.append(NegativeStatus(**contract))

        for contract in validated_data["negative_client_statuses"]:
            contract["credit"] = instance.credit
            # contract["guarantor"] = instance
            negative_statuses.append(NegativeStatus(**contract))

        with transaction.atomic():
            # Clean history before create new history
            # instance.credit_history.all().delete()

            CreditHistory.objects.bulk_create(contracts)

            # Очистим историю перед новых сохранением
            instance.negative_statuses.all().delete()

            NegativeStatus.objects.bulk_create(negative_statuses)

        return instance


class PKBReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditReport
        exclude = ("borrower",)


class PKBBiometricSerializer(serializers.ModelSerializer):
    format1 = serializers.HiddenField(default="image/jpeg")
    format2 = serializers.HiddenField(default="image/jpeg")

    def to_representation(self, instance: CreditApplication):
        biometric_images = instance.biometry_photos
        representation = super(PKBBiometricSerializer, self).to_representation(instance)
        data = {
            "photoBody1": b64encode(biometric_images.borrower_photo.getvalue()).decode("utf-8"),
            "filename1": biometric_images.borrower_photo.name,
            "photoBody2": b64encode(biometric_images.document_photo.getvalue()).decode("utf-8"),
            "filename2": biometric_images.document_photo.name,
        }
        return {**representation, **data}
