from django.utils import timezone

from apps.core.models import Branch
from apps.credits import RepaymentMethod, Decision, CreditStatus
from apps.credits.models.people import BusinessInfo, Guarantor
from apps.users import Roles
from apps.users.models import User
from num2words import num2words
from rest_framework import serializers
from apps.credits.models.application import CreditContract, CreditDecision, CreditDecisionVote, StatusTransition

from apps.people.models import Person, PersonalData

from .models import CreditApplication, CreditDocument, Product, CreditParams, Lead, FundingPurpose, \
    CreditApplicationPayment, CreditWithdrawal
from .utils import num2wordskz, num2wordsfloat
from ..accounts.models import BankCard


class CreditApplicationShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditApplication
        fields = [
            'pk',
            'status',
            'status_reason',
        ]


class CreditDocumentSerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(source='pk')
    url = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = CreditDocument
        fields = [
            'document_id',
            'document_type',
            # 'group',
            'url',
            'thumbnail',
        ]

    def get_url(self, obj: CreditDocument):  # noqa
        if obj.image:
            return obj.image.url
        return obj.document.url

    def get_thumbnail(self, obj: CreditDocument):  # noqa
        if obj.image:
            return obj.thumbnail.url
        return '/static/images/file-icons/pdf.svg'


# Serializers for prints
class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'


class LeadSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'

class BorrowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = '__all__'


class BorrowerDataSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    reg_address = serializers.ReadOnlyField(source='reg_address.__str__')
    real_address = serializers.ReadOnlyField(source='real_address.__str__')

    class Meta:
        model = PersonalData
        fields = '__all__'


class FundingPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FundingPurpose
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    financing_purpose = serializers.SerializerMethodField()
    financing_type = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_financing_purpose(self, obj: Product):  # noqa
        return obj.financing_purpose.name if obj.financing_purpose else ''

    def get_financing_type(self, obj: Product):  # noqa
        return obj.financing_type.name if obj.financing_type else ''


class BorrowerPrintSerializer(serializers.ModelSerializer):
    birthday = serializers.DateField(format="%d.%m.%Y")

    class Meta:
        model = Person
        fields = '__all__'


class BorrowerDataPrintSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    reg_address = serializers.ReadOnlyField(source='reg_address.__str__')
    real_address = serializers.ReadOnlyField(source='real_address.__str__')
    document_issue_date = serializers.DateField(format="%d.%m.%Y")
    bank_name = serializers.SerializerMethodField()
    person = BorrowerPrintSerializer()

    class Meta:
        model = PersonalData
        fields = '__all__'

    def get_bank_name(self, obj: PersonalData):  # noqa
        return obj.bank.name if obj.bank else ''


class CreditParamsSerializer(serializers.ModelSerializer):
    principal_kz = serializers.SerializerMethodField(read_only=True)
    principal_ru = serializers.SerializerMethodField(read_only=True)
    interest_rate_kz = serializers.SerializerMethodField(read_only=True)
    interest_rate_ru = serializers.SerializerMethodField(read_only=True)
    repayment_method_kz = serializers.SerializerMethodField(read_only=True)
    repayment_method_ru = serializers.SerializerMethodField(read_only=True)
    contract_date = serializers.DateField(format="%d.%m.%Y", read_only=True)
    repayment_date = serializers.DateField(format="%d.%m.%Y", read_only=True)
    last_payment_date = serializers.DateField(format="%d.%m.%Y", read_only=True)
    aeir_kz = serializers.SerializerMethodField(read_only=True)
    aeir_ru = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CreditParams
        fields = '__all__'

    def get_interest_rate_ru(self, obj): # noqa
        rate = obj.interest_rate
        if rate:
            return num2wordsfloat(rate, lang="ru").lower()

    def get_interest_rate_kz(self, obj): # noqa
        rate = obj.interest_rate
        if rate:
            return num2wordsfloat(rate, lang="kz").lower()

    def get_aeir_ru(self, obj): # noqa
        rate = obj.aeir
        if rate:
            return num2wordsfloat(rate, lang="ru").lower()

    def get_aeir_kz(self, obj): # noqa
        rate = obj.aeir
        if rate:
            return num2wordsfloat(rate, lang="kz").lower()

    def get_principal_ru(self, obj): # noqa
        amount = int(obj.principal)
        return str(num2words(number=amount, lang="ru")).lower()

    def get_principal_kz(self, obj): # noqa
        amount = int(obj.principal)
        return num2wordskz(amount).lower()

    def get_repayment_method_kz(self, obj): # noqa
        if obj.repayment_method == RepaymentMethod.ANNUITY:
            return 'Аннуитетті төлеу әдісі'
        elif obj.repayment_method == RepaymentMethod.EQUAL_INSTALMENTS:
            return 'Тең үлестермен'

        return 'Дифференциалды төлемдер әдісі'

    def get_repayment_method_ru(self, obj): # noqa
        if obj.repayment_method == RepaymentMethod.ANNUITY:
            return 'Аннуитетные платежи'
        elif obj.repayment_method == RepaymentMethod.EQUAL_INSTALMENTS:
            return 'Равными долями'

        return 'Метод дифференцированных платежей'


class CreditParamsWithScheduleSerializer(CreditParamsSerializer):
    total_interest = serializers.DecimalField(max_digits=16, decimal_places=2)
    overpayment = serializers.DecimalField(max_digits=16, decimal_places=2)
    schedule_payments = serializers.SerializerMethodField(read_only=True)

    def get_schedule_payments(self, obj: CreditParams): # noqa
        if obj.payments:
            payments = [payment.__dict__ for payment in obj.payments]
            schedule = obj.__dict__
            schedule['payments'] = payments
            schedule['total_interest'] = obj.monthly_payment * obj.period
            schedule['overpayment'] = schedule['total_interest'] - obj.principal
            return schedule
        return None


class CreditContractSerializer(serializers.ModelSerializer):
    params = CreditParamsWithScheduleSerializer(read_only=True)

    class Meta:
        model = CreditContract
        fields = '__all__'


class CreditGuarantorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guarantor
        fields = '__all__'


class CreditBusinessInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessInfo
        fields = '__all__'


class VoteManagerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('last_name', 'first_name', 'middle_name', 'full_name', 'role')

    def get_full_name(self, obj): # noqa
        return " ".join(filter(None, [obj.last_name, obj.first_name, obj.middle_name]))


class CreditDecisionVoteSerializer(serializers.ModelSerializer):
    manager = VoteManagerSerializer(read_only=True)

    class Meta:
        model = CreditDecisionVote
        fields = '__all__'


class CreditDecisionSerializer(serializers.ModelSerializer):
    votes = serializers.SerializerMethodField()
    chairman_vote = serializers.SerializerMethodField()
    created = serializers.DateTimeField(format="%d.%m.%Y")

    class Meta:
        model = CreditDecision
        fields = '__all__'

    def get_chairman_vote(self, obj): # noqa
        if obj.votes.exists():
            instance = obj.votes.filter(manager__role=Roles.CREDIT_COMMITTEE_CHAIRMAN).first()
            return CreditDecisionVoteSerializer(instance=instance).data
        return {}

    def get_votes(self, obj): # noqa
        if obj.votes.exists():
            instances = obj.votes.exclude(manager__role=Roles.CREDIT_COMMITTEE_CHAIRMAN)
            return CreditDecisionVoteSerializer(instance=instances, many=True).data
        return {}


class StatusTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusTransition
        fields = '__all__'


class CreditApplicationPrintSerializer(serializers.ModelSerializer):
    lead = LeadSerializer(read_only=True)
    borrower = BorrowerPrintSerializer(read_only=True)
    borrower_data = BorrowerDataPrintSerializer(read_only=True)
    product = ProductSerializer(read_only=True)
    approved_params = CreditParamsSerializer(read_only=True)
    requested_params = CreditParamsSerializer(read_only=True)
    contract = CreditContractSerializer(read_only=True)
    business_info = CreditBusinessInfoSerializer(read_only=True)
    decision = serializers.SerializerMethodField(read_only=True)
    created = serializers.DateTimeField(format="%d.%m.%Y", read_only=True)
    votes_result = serializers.SerializerMethodField(read_only=True)
    status_transitions = StatusTransitionSerializer(read_only=True, many=True)
    issued_data = serializers.SerializerMethodField(read_only=True)
    signed_at = serializers.DateTimeField(format="%H:%M:%S",read_only=True)

    class Meta:
        model = CreditApplication
        fields = '__all__'

    def get_issued_data(self, obj): # noqa
        created = None
        status_transitions_query = obj.status_transitions.filter(status=obj.status)
        if obj.status == CreditStatus.ISSUED and status_transitions_query.exists():
            created = status_transitions_query.first().created

        return timezone.localtime(created).strftime("%d.%m.%Y")


    def get_decision(self, obj): # noqa
        return CreditDecisionSerializer(instance=obj.decision).data

    def get_votes_result(self, obj):
        decision = self.get_decision(obj)
        status = {Decision.FOR: "Одобрено", Decision.AGAINST: "Отказано"}
        if not decision.get('votes') or not decision.get('chairman_vote'):
            return "Нет данных по голосованию"

        votes = [vote['status'] for vote in decision['votes']]
        chairman_vote = decision['chairman_vote']['status']

        if Decision.AGAINST not in votes and (chairman_vote == Decision.FOR or not chairman_vote):
            return status[Decision.FOR]
        elif chairman_vote == Decision.AGAINST or Decision.FOR not in votes:
            return status[Decision.AGAINST]

        return status[chairman_vote]


class VerificationFlowSerializer(serializers.Serializer):
    """Сериализатор для данных Verigram Flow"""
    flow_id = serializers.CharField(required=True)
    vlink = serializers.URLField(required=True)
    flow_status = serializers.CharField(required=False)
    end_cause = serializers.CharField(required=False, allow_null=True)


class CreditSigningInitSerializer(serializers.Serializer):
    """Сериализатор для инициации подписания кредитной заявки"""

    credit_id = serializers.IntegerField(required=True)
    callback_url = serializers.URLField(required=False)

    def validate_credit_id(self, value):
        """Проверка доступности кредитной заявки для подписания"""
        try:
            credit = CreditApplication.objects.get(pk=value)
        except CreditApplication.DoesNotExist:
            raise serializers.ValidationError("Кредитная заявка не найдена")

        # Проверка статуса заявки
        valid_statuses = [CreditStatus.APPROVED, CreditStatus.TO_SIGNING]
        if credit.status not in valid_statuses:
            raise serializers.ValidationError(
                f"Кредитная заявка должна быть в статусе: {', '.join(valid_statuses)}"
            )

        # Проверка наличия необходимых данных
        if not credit.borrower:
            raise serializers.ValidationError("У кредитной заявки отсутствует заемщик")

        if not credit.borrower.iin:
            raise serializers.ValidationError("У заемщика отсутствует ИИН")

        if not credit.lead or not credit.lead.mobile_phone:
            raise serializers.ValidationError("У заемщика отсутствует номер телефона")

        if not credit.approved_params:
            raise serializers.ValidationError("У кредитной заявки отсутствуют подтвержденные параметры")

        return value


class CreditSigningStatusSerializer(serializers.Serializer):
    """Сериализатор для проверки статуса подписания кредитной заявки"""

    flow_id = serializers.CharField(required=True)

    def validate_flow_id(self, value):
        """Проверка существования Flow"""
        try:
            credit = CreditApplication.objects.get(verigram_flow_id=value)
        except CreditApplication.DoesNotExist:
            raise serializers.ValidationError("Сеанс верификации не найден")

        return value


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment details."""
    payment_url = serializers.CharField(source='pay_link', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contract_number = serializers.CharField(source='contract.contract_number', read_only=True)
    credit_application_id = serializers.IntegerField(source='contract.credit.id', read_only=True)

    class Meta:
        model = CreditApplicationPayment
        fields = [
            'id', 'contract', 'contract_number', 'credit_application_id',
            'amount', 'status', 'status_display', 'payment_url', 'order_id',
            'created', 'modified'
        ]
        read_only_fields = ['contract', 'amount', 'order_id', 'status', 'created', 'modified']


class PaymentCallbackSerializer(serializers.Serializer):
    """Сериализатор для обработки колбэков от платежного шлюза."""
    orderId = serializers.CharField(required=True)  # Изменено с order_id на orderId
    status = serializers.IntegerField(required=True)
    amount = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    currency = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    message = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    errorCategory = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cascadeErrors = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    isTrustedTransaction = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    finalAmount = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    authorize_status = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    eci = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    firstName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    lastName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    rrn = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    card_holder = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    card_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    card_exp_month = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    card_exp_year = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sign = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class BankCardSerializer(serializers.ModelSerializer):
    """Сериализатор для банковской карты."""

    class Meta:
        model = BankCard
        fields = ('id', 'card_number', 'expiration_date', 'card_holder', 'card_type')
        read_only_fields = ('id',)

    def to_representation(self, instance):
        """Маскируем номер карты при отображении."""
        ret = super().to_representation(instance)
        if ret.get('card_number'):
            # Оставляем только последние 4 цифры номера карты
            ret['card_number'] = '*' * 12 + ret['card_number'][-4:]
        return ret


class WithdrawalSerializer(serializers.Serializer):
    """
    Сериализатор для базовой информации о выводе средств.
    """
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(read_only=True, max_digits=12, decimal_places=2)
    tokenize_form_url = serializers.URLField(read_only=True)
    error_message = serializers.CharField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)


class WithdrawalCallbackSerializer(serializers.Serializer):
    """
    Сериализатор для обработки колбэков от платежного шлюза.
    """
    order_id = serializers.CharField(required=True)
    status = serializers.IntegerField(required=True)

    # Дополнительные поля, которые могут быть в колбэке
    card = serializers.DictField(required=False, allow_null=True)
    processing_order_id = serializers.CharField(required=False, allow_null=True)
    err = serializers.CharField(required=False, allow_null=True)
    msg = serializers.CharField(required=False, allow_null=True)
