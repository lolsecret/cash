from rest_framework import serializers

from apps.core.models import Bank, CreditIssuancePlan, Document, FAQ


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = '__all__'


class CreditIssuancePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditIssuancePlan
        fields = '__all__'


class DocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ('id', "title", "document")


class FAQListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ('id', "question", "answer")
