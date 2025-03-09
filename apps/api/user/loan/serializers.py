from django.urls import reverse
from rest_framework import serializers

from apps.core.models import PrintForm
from apps.credits import RepaymentMethod
from apps.credits.models import CreditContract, CreditParams, CreditApplication


class LoanRepaymentSumSerializer(serializers.Serializer):  # noqa
    contract_number = serializers.CharField(required=True)
    kaspi = serializers.BooleanField()


class LoanRepaymentSumResponseSerializer(serializers.Serializer):  # noqa
    account_balance = serializers.FloatField(default=0)
    contract_number = serializers.CharField()
    current_amount_debt = serializers.FloatField()
    debt_date = serializers.DateField()
    is_holiday = serializers.ListField()
    possibility_of_payment = serializers.BooleanField()


class LoanRepaymentPartialSumResponseSerializer(LoanRepaymentSumResponseSerializer):  # noqa
    payment_minimum = serializers.FloatField()


class LoanRepaymentFullSumResponseSerializer(LoanRepaymentSumResponseSerializer):  # noqa
    kaspi_debt = serializers.FloatField()


class CreditParamsShortSerializer(serializers.ModelSerializer):

    class Meta:
        model = CreditParams
        fields = (
            'principal',
            'interest_rate',
            'period',
            'repayment_method',
            'desired_repayment_day',
            'contract_date',
        )
        read_only_fields = fields

    def get_payment_schedule(self, obj):
        if obj.payment_schedule:
            payments = [payment.__dict__ for payment in obj.payment_schedule.payments]
            schedule = obj.payment_schedule.__dict__
            schedule['payments'] = payments
            return schedule
        return None


class CreditContractPaymentSerializer(serializers.Serializer):
    payment_date = serializers.DateField()
    payment_amount = serializers.DecimalField(decimal_places=2, max_digits=16)
    minimum_amount_of_partial_repayment = serializers.DecimalField(decimal_places=2, max_digits=16)
    current_debt = serializers.DecimalField(decimal_places=2, max_digits=16)
    contract_number = serializers.CharField()
    contract_date = serializers.DateField()


class CreditPaymentSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    balance = serializers.DecimalField(decimal_places=2, max_digits=16)
    contracts = CreditContractPaymentSerializer(many=True)


class CreditPaymentRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(decimal_places=2, max_digits=16)
    contract_number = serializers.CharField()
    contract_date = serializers.DateField()


class CreditContractSerializer(serializers.ModelSerializer):
    params = serializers.SerializerMethodField(read_only=True)
    repayment_method = serializers.ChoiceField(choices=RepaymentMethod.choices, write_only=True)
    print_forms = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CreditContract
        fields = (
            'product',
            'borrower',
            'params',
            'contract_number',
            'contract_date',
            'contract_status',
            'reward',
            'payments',
            'remaining_principal',
            'overdue_amount',
            'penalty_amount',
            'signed_at',
            'closed_at',
            'repayment_method',
            'credit_id',
            'print_forms',
        )
        read_only_fields = fields

    def update(self, instance: CreditContract, validated_data):
        params = instance.params
        params.repayment_method = validated_data.get('repayment_method')
        params.save(update_fields=['repayment_method'])
        return validated_data

    @staticmethod
    def get_print_forms(obj):
        print_form_names = ["schedule-payments", "credit-application"]
        print_forms = PrintForm.objects.filter(slug__in=print_form_names)
        data = {}
        for print_form in print_forms:
            data[print_form.slug] = reverse(
                'profile-print-form-pdf', kwargs={'pk': obj.credit_id, 'form_name': print_form.slug}
            )
        return data

    @staticmethod
    def get_params(obj):
        return CreditParamsShortSerializer(obj.approved_params).data



class ValidateBorrowerOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(write_only=True, label="OTP")


# noinspection PyAbstractClass
class PaymentHistorySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)


class GuarantorSignSerializer(serializers.ModelSerializer):
    guarantor_print_form = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CreditContract
        fields = (
            'guarantor_print_form',
            'id',
        )
        read_only_fields = fields

    @staticmethod
    def get_guarantor_print_form(obj):
        print_form = PrintForm.objects.get(slug="guarantor")
        data = {
            print_form.slug: reverse(
                'profile-print-form-pdf', kwargs={'pk': obj.credit_id, 'form_name': print_form.slug}
            )
        }
        return data


class ProfileCreditApplicationSerializer(serializers.ModelSerializer):
    approved_params = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(source="get_status_display")
    print_forms = serializers.SerializerMethodField()

    class Meta:
        model = CreditApplication
        fields = (
            'approved_params',
            'status',
            'created',
            'id',
            'print_forms',
        )
        read_only_fields = fields

    def update(self, instance: CreditContract, validated_data):
        params = instance.params
        params.repayment_method = validated_data.get('repayment_method')
        params.save(update_fields=['repayment_method'])
        return validated_data

    @staticmethod
    def get_print_forms(obj):
        print_form_names = ["schedule-payments", "credit-application"]
        print_forms = PrintForm.objects.filter(slug__in=print_form_names)
        data = {}
        for print_form in print_forms:
            data[print_form.slug] = reverse(
                'profile-print-form-pdf', kwargs={'pk': obj.id, 'form_name': print_form.slug}
            )
        return data

    @staticmethod
    def get_approved_params(obj):
        return CreditParamsShortSerializer(obj.approved_params).data


