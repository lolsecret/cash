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

from .models import CreditApplication, CreditDocument, Product, CreditParams, Lead, FundingPurpose
from .utils import num2wordskz, num2wordsfloat


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
