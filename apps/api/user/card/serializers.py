from rest_framework import serializers

from apps.accounts.models import BankAccount, BankCard


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['id', 'iban', 'bank_name', 'created']


class BankCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankCard
        fields = ['id', 'card_number', 'expiration_date', 'card_holder', 'card_type', 'created']
