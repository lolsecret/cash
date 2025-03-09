from rest_framework import serializers


class PaymentScheduleSerializer(serializers.Serializer):  # noqa
    amountOfRepayment = serializers.FloatField(source='amount_of_repayment')
    payment = serializers.FloatField(source='')
    paymentNumber = serializers.IntegerField(source='payment_number')
    paymentOfRemuneration = serializers.FloatField(source='payment_of_remuneration')
    AmountPaid = serializers.FloatField(source='amount_paid')
    Fines = serializers.FloatField(source='fines')
    plannedBalance = serializers.FloatField(source='planned_balance')
    targetDates = serializers.DateField(source='target_dates')
    PaymentStatus = serializers.CharField(source='payment_status', allow_null=True)


class ContractInfoSerializer(serializers.Serializer):  # noqa
    Arrears = serializers.DecimalField(source='arrears', decimal_places=2, max_digits=16)
    ContractNumber = serializers.CharField(source='contract_number')
    DateOfConclusion = serializers.DateField(source='date_of_conclusion')
    ExpirationDate = serializers.DateField(source='expiration_date')
    KDIF = serializers.FloatField(source='kdif')
    LoanAmount = serializers.FloatField(source='loan_amount')
    PlannedPaymentAmount = serializers.FloatField(source='planned_payment_amount')
    PlannedPaymentDate = serializers.DateField(source='planned_payment_date')
    RemnantOfPrincipal = serializers.FloatField(source='remnant_of_principal')
    RateRemuneration = serializers.FloatField(source='rate_remuneration')
    CurrentAmountDebt = serializers.FloatField(source='current_amount_debt')
    CurrentAmountDebt2 = serializers.FloatField(source='current_amount_debt2')
    PaymentSchedule = PaymentScheduleSerializer(source='payment_schedule', many=True)

    def run_validation(self, data: dict = None):
        data['PaymentSchedule'] = data.get('PaymentSchedule').get('PaymentLine')
        return super().run_validation(data)


class AccountInfoSerializer(serializers.Serializer):  # noqa
    status = serializers.CharField(default="Заемщик найден")
    AccountBalance = serializers.FloatField(source='account_balance', default=0)
    ClientName = serializers.CharField(source='client_name')
    ClientFirstName = serializers.CharField(source='client_first_name')
    ClientLastName = serializers.CharField(source='client_last_name')
    ClientPatronymic = serializers.CharField(source='client_patronymic', allow_null=True)
    Email = serializers.CharField(source='email', allow_null=True)
    IIN = serializers.CharField(source='iin')
    MobilePhone = serializers.CharField(source='mobile_phone')
    OtherInformation = serializers.CharField(source='other_information', allow_null=True)
    ContractInfo = ContractInfoSerializer(source='user_contract_info', many=True)


class PaymentHistorySerializer(serializers.Serializer):  # noqa
    paymentNumber = serializers.IntegerField()
    targetDates = serializers.DateField()
    payment = serializers.FloatField()
    type = serializers.CharField(allow_null=True)
