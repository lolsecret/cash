import traceback
from typing import OrderedDict, Dict, Any
import logging

from PIL import Image
from django.db import transaction
from django.utils.translation import gettext as _, gettext
from django_fsm import can_proceed, has_transition_perm
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from apps.api.scoring.pipelines import lead_from_api_pipeline
from apps.core.models import City, Branch, Bank
from apps.credits import CreditStatus, Decision, RepaymentMethod
from apps.credits.models import (
    Product,
    CreditParams,
    CreditApplication,
    Lead,
    BusinessInfo,
    CreditDecisionVote,
    CreditDecision,
    CreditFinance,
    CreditHistory,
    CreditReport,
    CreditDocument,
    DocumentType,
    FinanceReportType,
    Guarantor,
    Comment,
    DocumentGroup, RejectionReason,
)
from apps.flow.models import StatusTrigger
from apps.flow.services import Flow
from apps.people import RelationshipType, Gender
from apps.people.models import (
    Person,
    Address,
    PersonalData,
    PersonContact,
    AdditionalContactRelation,
)
from apps.people.validators import IinValidator
from apps.users.models import User

logger = logging.getLogger(__name__)


class BorrowerSerializer(serializers.ModelSerializer):
    genderDisplay = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Person
        fields = '__all__'

    def get_genderDisplay(self, obj: Person):  # noqa
        return obj.get_gender_display()


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'


class PersonContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonContact
        fields = ('first_name', 'mobile_phone')


class AdditionalContactRelationSerializer(serializers.ModelSerializer):
    contact = PersonContactSerializer()
    relationship = serializers.ChoiceField(choices=RelationshipType.choices, allow_null=True, allow_blank=True)

    class Meta:
        model = AdditionalContactRelation
        exclude = ('id', 'record', 'profile_record')

    def update(self, instance: AdditionalContactRelation, validated_data: OrderedDict):
        contact = PersonContactSerializer(instance.contact, data=validated_data.pop('contact'))
        if contact.is_valid():
            contact.save()

        return super().update(instance, validated_data)


class BorrowerDataSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    reg_address = AddressSerializer(read_only=True)
    real_address = AddressSerializer()

    spouse_iin = serializers.CharField(allow_blank=True, allow_null=True)
    bank_id = serializers.IntegerField(required=False, allow_null=True)

    additional_contact = AdditionalContactRelationSerializer(required=False)

    class Meta:
        model = PersonalData
        exclude = (
            'person',
            'bank',
            'additional_contacts',
        )
        extra_kwargs = {
            'spouse_iin': {'required': False},
        }

    def update(self, instance: PersonalData, validated_data: OrderedDict):
        real_address_serializer = AddressSerializer(instance.real_address, data=validated_data.pop('real_address'))
        if real_address_serializer.is_valid():
            real_address_serializer.save()

        additional_contact = AdditionalContactRelationSerializer(
            instance.additional_contact(),
            data=validated_data.pop('additional_contact')
        )
        if additional_contact.is_valid():
            additional_contact.save()

        return super().update(instance, validated_data)


class ProductSerializer(serializers.ModelSerializer):
    financing_purpose = serializers.SerializerMethodField()
    financing_type = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('name', 'financing_purpose', 'financing_type', 'finance_report_month_count')

    def get_financing_purpose(self, obj: Product):  # noqa
        return obj.financing_purpose.name if obj.financing_purpose else ''

    def get_financing_type(self, obj: Product):  # noqa
        return obj.financing_type.name if obj.financing_type else ''


class CreditParamsSerializer(serializers.ModelSerializer):
    principal = serializers.IntegerField()
    aeir = serializers.SerializerMethodField(read_only=True)
    monthly_payment = serializers.ReadOnlyField()

    class Meta:
        model = CreditParams
        fields = '__all__'

    def get_aeir(self, obj: CreditParams):  # noqa
        if obj.aeir:
            return str(round(obj.aeir, 1)).replace('.', ',')


class CreditProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ('id', 'name')


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'code', 'branch_code')


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ('id', 'name', 'address', 'parent')


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = '__all__'


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = '__all__'


class DocumentGroupSerializer(serializers.ModelSerializer):
    document_types = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DocumentGroup
        fields = '__all__'

    def get_document_types(self, obj: DocumentGroup):
        return DocumentTypeSerializer(obj.document_types.filter(active=True), many=True).data


class RejectionReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = RejectionReason
        fields = ('id', 'status')


class BusinessInfoSerializer(serializers.ModelSerializer):
    name = serializers.CharField(allow_blank=True)
    branch = serializers.CharField(allow_blank=True)
    place = serializers.CharField(allow_blank=True)
    website_social = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True, allow_null=True)
    expert_opinion = serializers.CharField(allow_blank=True, allow_null=True)
    funding_plan = serializers.CharField(allow_blank=True, allow_null=True)

    class Meta:
        model = BusinessInfo
        exclude = ('id', 'credit')


class CreditDecisionVoteSerializer(serializers.ModelSerializer):
    manager = serializers.SerializerMethodField()

    class Meta:
        model = CreditDecisionVote
        exclude = ('decision', 'modified')
        extra_kwargs = {
            'name': {'required': False},
        }

    def get_manager(self, obj: CreditDecisionVote):  # noqa
        return str(obj.manager)


class CreditDecisionSerializer(serializers.ModelSerializer):
    votes = CreditDecisionVoteSerializer(many=True)
    already_voted = serializers.SerializerMethodField()

    class Meta:
        model = CreditDecision
        exclude = ('credit',)

    def get_already_voted(self, obj: CreditDecision):
        request = self.context.get('request')
        return obj.is_already_voted(user=request.user)


class LeadSerializer(serializers.ModelSerializer):
    branch_id = serializers.IntegerField(allow_null=True)
    credit_params = CreditParamsSerializer(read_only=True)

    class Meta:
        model = Lead
        exclude = ('branch', 'borrower', 'borrower_data', 'product', 'channel')
        extra_kwargs = {
            'city': {'read_only': True},
        }


class CreditHistorySerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='get_status_display')
    start_date = serializers.DateField(format="%d.%m.%Y")
    end_date = serializers.DateField(format="%d.%m.%Y")
    total_amount = serializers.FloatField()
    monthly_payment = serializers.FloatField()
    outstanding_amount = serializers.FloatField()

    class Meta:
        model = CreditHistory
        exclude = ('credit',)


class CreditReportSerializer(serializers.ModelSerializer):
    # pkb_credit_report = serializers.CharField(source='pkb_credit_report')

    class Meta:
        model = CreditReport
        fields = ('pkb_credit_report', 'soho_score', 'custom_score')
        # exclude = ('id', 'lead', 'credit',)


class ReportSerializer(serializers.ModelSerializer):
    report = CreditReportSerializer(source='credit_report')
    history = CreditHistorySerializer(source='credit_history', many=True)

    class Meta:
        model = CreditApplication
        fields = ('report', 'history')


class CreditFinanceSerializer(serializers.ModelSerializer):
    net_balance_percentage = serializers.FloatField(read_only=True)
    equity_div_debit = serializers.FloatField(read_only=True)

    class Meta:
        model = CreditFinance
        exclude = ('credit',)

    def update(self, instance: CreditFinance, validated_data: OrderedDict):
        return super().update(instance, validated_data)


class LeadListSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)
    borrower_iin = serializers.ReadOnlyField(source='borrower.iin')
    borrower_full_name = serializers.SerializerMethodField(read_only=True)
    principal = serializers.ReadOnlyField(source='credit_params.principal')
    period = serializers.ReadOnlyField(source='credit_params.period')
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = Lead
        fields = (
            'id',
            'created',
            'borrower_iin',
            'borrower_full_name',
            'mobile_phone',
            'principal',
            'period',
            'product_name',
            'rejected',
            'reject_reason',
        )

    # noinspection PyMethodMayBeStatic
    def get_borrower_full_name(self, obj: Lead) -> str:
        full_name = obj.full_name
        if full_name:
            return full_name

        elif obj.borrower_data:
            return obj.borrower_data.full_name

        return ''


# noinspection PyMethodMayBeStatic
class CreditListSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)
    borrower_iin = serializers.ReadOnlyField(source='borrower.iin')
    borrower_full_name = serializers.ReadOnlyField(source='borrower_data.full_name')
    mobile_phone = PhoneNumberField(source='lead.mobile_phone', read_only=True)
    principal = serializers.ReadOnlyField(source='requested_params.principal')
    period = serializers.ReadOnlyField(source='requested_params.period')
    channel = serializers.ReadOnlyField(source='lead.utm_source')
    manager = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.ReadOnlyField(source='get_status_display')
    status_color = serializers.ReadOnlyField(source='get_status_color')

    class Meta:
        model = CreditApplication
        fields = (
            'id',
            'created',
            'borrower_iin',
            'borrower_full_name',
            'mobile_phone',
            'principal',
            'period',
            'manager',
            'channel',
            'status',
            'status_display',
            'status_color',
        )

    def get_manager(self, obj: CreditApplication):
        return obj.manager.__str__() if obj.manager else ''


# noinspection PyAbstractClass
class CreditCreateSerializer(serializers.Serializer):
    iin = serializers.CharField(validators=[IinValidator()])
    mobile_phone = PhoneNumberField(write_only=True)
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    desired_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    desired_period = serializers.IntegerField()
    repayment_method = serializers.ChoiceField(choices=RepaymentMethod.choices)

    def validate(self, attrs):
        print(attrs)
        product: Product = attrs['product']
        desired_amount = attrs['desired_amount']
        desired_period = attrs['desired_period']

        if desired_amount not in product.principal_limits:
            raise serializers.ValidationError({'desired_amount': _("Указанная сумма не подходит по параметрам")})

        if desired_period not in product.period_limits:
            raise serializers.ValidationError({'desired_period': _("Указанный период не подходит по параметрам")})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Lead:
        try:
            lead: Lead = lead_from_api_pipeline(validated_data)
            lead.check_params()

            logger.info('lead.product.pipeline: %s', lead.product.pipeline)
            credit = lead.create_credit_application(manager=self.context['request'].user)
            credit.to_check()
            credit.save()

            logger.info("Api.views: flow run pipeline for lead %s", lead.pk)
            transaction.on_commit(lambda: Flow(lead.product.pipeline, lead).run())

        except Exception as exc:
            logger.error("CreditCreateSerializer error %s", exc)
            raise exc

        return lead


# noinspection PyAbstractClass
class CreditRedirectSerializer(serializers.Serializer):
    credit_ids = serializers.CharField(required=True)
    manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


# noinspection DuplicatedCode
class CreditApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    lead = LeadSerializer()
    borrower = BorrowerSerializer(read_only=True)
    borrower_data = BorrowerDataSerializer()
    product = ProductSerializer(read_only=True)

    requested_params = CreditParamsSerializer(read_only=True)
    recommended_params = CreditParamsSerializer(read_only=True)
    approved_params = CreditParamsSerializer()

    business_info = BusinessInfoSerializer()
    decision = CreditDecisionSerializer(read_only=True)

    # credit_finance = CreditFinanceSerializer(allow_null=True)

    class Meta:
        model = CreditApplication
        fields = '__all__'
        extra_kwargs = {
            'status': {'read_only': True},
            'status_reason': {'read_only': True},
            'reject_reason': {'read_only': True},
            'otp_signature': {'read_only': True},
            'verified': {'read_only': True},
        }

    def update(self, instance: CreditApplication, validated_data: OrderedDict):
        lead_data = validated_data.pop('lead')
        borrower_data = validated_data.pop('borrower_data')
        approved_params_data = validated_data.pop('approved_params')

        # Сохраняем данные в лиде
        lead_serializer = LeadSerializer(instance.lead, data=lead_data)
        lead_serializer.is_valid(raise_exception=True)
        lead_serializer.save()

        # Сохраняем данные заемщика
        borrower_data_serializer = BorrowerDataSerializer(instance.borrower_data, data=borrower_data)
        borrower_data_serializer.is_valid(raise_exception=True)
        borrower_data_serializer.save()

        # Сохраняем информацию о бизнесе
        business_info = BusinessInfoSerializer(instance.business_info, data=validated_data.pop('business_info'))
        business_info.is_valid(raise_exception=True)
        business_info.save()

        # Сохраняем подтвержденные параметры
        approved_params_serializer = CreditParamsSerializer(instance.approved_params, data=approved_params_data)
        approved_params_serializer.is_valid(raise_exception=True)
        approved_params_serializer.save()

        # Сохраняем подтвержденные параметры в кредитном контракте(если имеется)
        if hasattr(instance, 'contract'):
            contract_params_serializer = CreditParamsSerializer(instance.contract.params, data=approved_params_data)
            contract_params_serializer.is_valid(raise_exception=True)
            contract_params_serializer.save()

        return instance


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ('content', 'author')


# noinspection PyMethodMayBeStatic
class CreditPreviewSerializer(serializers.ModelSerializer):
    borrower_iin = serializers.ReadOnlyField(source='borrower.iin')
    borrower_name = serializers.ReadOnlyField(source='borrower_data.full_name')
    borrower_phone = serializers.ReadOnlyField(source='lead.mobile_phone.__str__')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    credit_report = CreditReportSerializer(source='lead.get_credit_report', read_only=True)
    requested_params = CreditParamsSerializer(read_only=True)
    next_statuses = serializers.SerializerMethodField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    status = serializers.CharField(write_only=True, allow_null=True)
    status_reason = serializers.CharField(write_only=True, allow_null=True)
    comment = serializers.CharField(write_only=True)

    class Meta:
        model = CreditApplication
        fields = (
            'borrower_iin',
            'borrower_name',
            'borrower_phone',
            'status',
            'status_display',
            'credit_report',
            'requested_params',
            'next_statuses',
            'comments',

            'comment',
            'status_reason',
        )

    def get_credit_report(self, obj: CreditApplication):
        return CreditReportSerializer(obj.lead.get_credit_report()).data

    def get_next_statuses(self, obj: CreditApplication):
        return obj.available_status_transitions()

    def update(self, instance: CreditApplication, validated_data: OrderedDict):
        request = self.context.get('request')
        next_status = validated_data.pop('status')
        status_reason = validated_data.pop('status_reason')
        comment = validated_data.pop('comment')

        # Если есть только коммент
        if not next_status and comment:
            Comment.objects.create(
                credit=instance,
                author=self.context['request'].user,
                content=comment,
            )
            instance.status_reason = comment
            instance.save(update_fields=['status_reason'])
            return instance

        try:
            # Попытка изменения статуса
            transition_method = instance.get_transition_by_status(next_status)
            with transaction.atomic():
                transition_method()

                if status_reason:
                    reason = str(status_reason)
                    instance.status_reason = f'{comment}, {reason}' if comment else reason
                if comment:
                    Comment.objects.create(credit=instance, author=request.user, content=comment)

                instance.save()

        except Exception as exc:
            logger.error("CreditPreviewSerializer.update error", exc)

        return instance


# noinspection PyAbstractClass
class RejectCreditSerializer(serializers.Serializer):
    reason = serializers.PrimaryKeyRelatedField(queryset=RejectionReason.objects.all())
    comment = serializers.CharField()


class CreditUploadFilesSerializer(serializers.Serializer):  # noqa
    file = serializers.FileField()

    def save(self, **kwargs):
        print('save', self.__dict__)
        print('save', self.validated_data)


class CreditDocumentsSerializer(serializers.ModelSerializer):
    document_type = serializers.CharField(source='document_type.code')
    thumbnail = serializers.SerializerMethodField(source='thumbnail', read_only=True)
    document = serializers.FileField(allow_null=True)
    image = serializers.ImageField(read_only=True)
    filename = serializers.CharField(read_only=True)
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CreditDocument
        exclude = ('credit',)

    def get_thumbnail(self, obj: CreditDocument):  # noqa
        extensions = {
            'doc': 'word.png',
            'docx': 'word.png',
            'xls': 'excel.png',
            'xlsx': 'excel.png',
            'pdf': 'pdf.png',
        }

        if obj.image:
            try:
                return obj.thumbnail.url
            except Exception as exc:
                logger.error("get_thumbnail %s error %s", obj.image, exc)
                return None

        elif obj.filename:
            name, extension = obj.filename.rsplit('.', 1)
            icon = extensions.get(extension, extensions.get('pdf'))
            return f'/static/images/file-icons/{icon}'

        return '/static/images/file-icons/pdf.png'

    def get_url(self, obj: CreditDocument) -> str:
        if obj.image:
            return obj.image.url
        return obj.document.url

    def validate_document(self, value):  # noqa
        if not value:
            raise serializers.ValidationError(_("Это поле не может быть пустым"))
        return value

    def validate(self, attrs: OrderedDict):
        try:
            Image.open(attrs.get('document')).verify()
            attrs['image'] = attrs.pop('document')

        except Exception:  # noqa
            """загружаемый документ не картинка"""

        return attrs

    def create(self, validated_data: OrderedDict):
        document_type_data = validated_data.pop('document_type')
        document_type = DocumentType.objects.filter(code=document_type_data['code']).first()
        validated_data['document_type'] = document_type
        return super().create(validated_data)


class FinanceReportCalcSerializer(serializers.Serializer):  # noqa
    finance_reports = serializers.JSONField(required=True)


class FinanceReportTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceReportType
        fields = ('name',
                  'const_name',
                  'is_expense',
                  'calculated',
                  'position')


class CreditChangeStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=CreditStatus.choices)
    comment = serializers.CharField(required=False, write_only=True, allow_null=True, allow_blank=True)

    class Meta:
        model = CreditApplication
        fields = ('status', 'comment')

    def update(self, instance: CreditApplication, validated_data: OrderedDict):
        request = self.context.get('request')
        new_status = validated_data.pop('status')
        comment = validated_data.pop('comment')
        old_status = instance.status
        extra_log = {
            'credit_id': instance.pk,
            'old_status': old_status,
            'new_status': new_status,
            'user': request.user,
        }
        logger.info('credit %s try change status: %s -> %s', instance, old_status, new_status, extra=extra_log)

        try:
            transition_method = instance.get_transition_by_status(new_status)  # noqa
            if can_proceed(transition_method) and has_transition_perm(transition_method, request.user):
                transition_method()
                instance.save()

                logger.info(
                    'credit %s change status success: %s -> %s', instance, old_status, new_status,
                    extra=extra_log
                )
                StatusTrigger.run(status=new_status, credit=instance)

                if comment:
                    Comment.objects.create(credit=instance, author=request.user, content=comment)

            return instance

        except Exception as exc:
            traceback.print_exc()
            logger.error(
                "credit %s change status error: %s -> %s error=%s", instance, old_status, new_status, exc,
                extra=extra_log
            )
            raise serializers.ValidationError({"status": "Ошибка смены статуса"})


class Callback1cChangeStatusSerializer(CreditChangeStatusSerializer):
    class Meta:
        model = CreditApplication
        fields = CreditChangeStatusSerializer.Meta.fields

    def update(self, instance: CreditApplication, validated_data: OrderedDict):
        new_status = validated_data.get('status')
        old_status = instance.status
        if new_status != CreditStatus.ISSUED and old_status != CreditStatus.ISSUANCE:
            raise serializers.ValidationError({"status": f"Ошибка смены статуса. Входящий статус - {new_status}"})
        return super().update(instance, validated_data)


class CreditVoteSerializer(serializers.Serializer):  # noqa
    decision = serializers.ChoiceField(choices=Decision.choices)
    comment = serializers.CharField()
    additional = serializers.CharField()
    has_guarantor = serializers.BooleanField(default=False)
    params = CreditParamsSerializer()

    # def update(self, instance, validated_data):
    #     print('update', validated_data)
    #     pass
    #
    # class Meta:
    #     model = CreditApplication
    #     fields = (
    #         'decision',
    #         'comment',
    #         'additional',
    #     )
    #
    # def validate_decision(self, value):  # noqa
    #     if value not in Decision:
    #         raise serializers.ValidationError("Ошибка параметра")
    #     return value
    #
    # def update(self, instance: CreditApplication, validated_data: OrderedDict):
    #     print('validated_data:', validated_data)
    #     return instance


# noinspection PyAbstractClass
class GuarantorPersonSerializer(serializers.Serializer):
    iin = serializers.RegexField(
        regex=r"^[0-9]{2}[0-9]{2}[0-9]{2}[0-9]{1}[0-9]{4}[0-9]{1}",
        min_length=12, max_length=12,
    )
    gender = serializers.ChoiceField(choices=Gender.choices)
    birthday = serializers.DateField(read_only=True)
    age = serializers.IntegerField(read_only=True)


class GuarantorDataSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    reg_address = AddressSerializer(required=False)
    real_address = AddressSerializer(required=False)

    mobile_phone = PhoneNumberField(required=False)

    spouse_iin = serializers.CharField(allow_blank=True, allow_null=True)
    bank_id = serializers.IntegerField(required=False, allow_null=True)

    additional_contact = AdditionalContactRelationSerializer(required=False)

    class Meta:
        model = PersonalData
        exclude = (
            'person',
            'bank',
            'additional_contacts',
        )
        extra_kwargs = {
            'spouse_iin': {'required': False},
        }


class GuarantorSerializer(serializers.ModelSerializer):
    person = GuarantorPersonSerializer()
    person_record = GuarantorDataSerializer()
    credit_report = CreditReportSerializer(source='get_credit_report', read_only=True)

    class Meta:
        model = Guarantor
        exclude = ('credit',)

    # noinspection PyMethodMayBeStatic
    def validate_person(self, attrs: dict) -> Person:
        return Person.from_iin.create(attrs['iin'])

    def validate(self, attrs: dict):
        person: Person = attrs.get('person')
        credit_id = self.context.get('kwargs', {}).get('credit_id')
        if Guarantor.objects.filter(credit_id=credit_id, person_record__person__iin=person.iin).exists():
            raise serializers.ValidationError({"iin": gettext("Гарант с таким иин уже добавлен.")})

        return attrs

    def create(self, validated_data):
        kwargs: dict = self.context.get('kwargs')

        person: Person = validated_data.get('person')
        person_record_data = validated_data.pop('person_record')
        reg_address_data = person_record_data.pop('reg_address')
        real_address_data = person_record_data.pop('real_address')

        additional_contact_data = person_record_data.pop('additional_contact')

        reg_address_serializer = AddressSerializer(data=reg_address_data)
        if not reg_address_serializer.is_valid():
            raise serializers.ValidationError(reg_address_serializer.errors)

        real_address_serializer = AddressSerializer(data=real_address_data)
        if not real_address_serializer.is_valid():
            raise serializers.ValidationError(real_address_serializer.errors)

        with transaction.atomic():
            reg_address = reg_address_serializer.save()
            real_address = real_address_serializer.save()

            person_record = PersonalData(**person_record_data)
            person_record.person = person
            person_record.reg_address = reg_address
            person_record.real_address = real_address

            person_record.save()

            additional_contact = AdditionalContactRelationSerializer(
                person_record.additional_contact(),
                data=additional_contact_data,
            )
            if additional_contact.is_valid():
                additional_contact.save()

        validated_data['credit_id'] = kwargs.get('credit_id')
        validated_data['person_record'] = person_record

        try:
            return super().create(validated_data)
        except Exception as exc:
            logger.error("GuarantorSerializer.create: %s", exc)
            raise TypeError(exc)

    def update(self, instance: Guarantor, validated_data: dict):
        person: Person = validated_data.pop('person')
        person_record_data: dict = validated_data.pop('person_record')

        reg_address_data = person_record_data.pop('reg_address')
        reg_address_serializer = AddressSerializer(instance.person_record.reg_address, data=reg_address_data)
        if not reg_address_serializer.is_valid():
            raise serializers.ValidationError(reg_address_serializer.errors)

        real_address_data = person_record_data.pop('real_address')
        real_address_serializer = AddressSerializer(instance.person_record.real_address, data=real_address_data)
        if not real_address_serializer.is_valid():
            raise serializers.ValidationError(real_address_serializer.errors)

        person_record_serializer = GuarantorDataSerializer(instance.person_record, data=person_record_data)
        if not person_record_serializer.is_valid():
            raise serializers.ValidationError(person_record_serializer.errors)

        additional_contact_data = person_record_data.pop('additional_contact')
        additional_contact = AdditionalContactRelationSerializer(
            instance.person_record.additional_contact(),
            data=additional_contact_data,
        )
        if not additional_contact.is_valid():
            raise serializers.ValidationError(additional_contact.errors)

        with transaction.atomic():
            reg_address_serializer.save()
            real_address_serializer.save()
            person_record_serializer.save()
            additional_contact.save()

        return instance


# noinspection PyMethodMayBeStatic
class CreditApplicationExportSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S')
    iin = serializers.CharField(source='contract.borrower.iin')
    fio = serializers.CharField(source='borrower_data.full_name')
    phone = serializers.CharField(source='lead.mobile_phone')
    requested_amount = serializers.DecimalField(
        source='requested_params.principal', decimal_places=2, max_digits=10
    )
    approved_amount = serializers.DecimalField(
        source='approved_params.principal', decimal_places=2, max_digits=10
    )
    requested_period = serializers.IntegerField(
        source='requested_params.period',
    )
    approved_period = serializers.IntegerField(
        source='approved_params.principal',
    )
    channel = serializers.CharField(source='lead.channel')
    status = serializers.SerializerMethodField()
    age = serializers.IntegerField(source='borrower.age')
    reg_address = serializers.CharField(source='borrower_data.reg_address')
    real_address = serializers.CharField(source='borrower_data.real_address')
    soho_score = serializers.IntegerField(
        source='lead.credit_report.soho_score'
    )
    interest_rate = serializers.DecimalField(
        source='approved_params.interest_rate', decimal_places=2, max_digits=5
    )
    comment = serializers.CharField(source='credit_finance.report_comment')
    custom_score = serializers.CharField(
        source='lead.credit_report.custom_score'
    )

    def get_status(self, obj: CreditApplication) -> str:
        return obj.get_status_display()

    class Meta:
        model = CreditApplication
        fields = (
            'id', 'created', 'iin', 'fio', 'phone',
            'requested_amount', 'approved_amount',
            'requested_period', 'approved_period',
            'manager', 'channel', 'status', 'age',
            'reg_address', 'real_address',
            'soho_score', 'interest_rate', 'comment', 'custom_score'
        )


class LeadExportSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S')
    iin = serializers.CharField(source='borrower.iin')
    fio = serializers.CharField(source='borrower_data.full_name')
    status = serializers.CharField(source='credit.status')

    class Meta:
        model = Lead
        fields = ('id', 'created', 'status', 'iin', 'fio', 'mobile_phone')


# noinspection PyMethodMayBeStatic
class RegistrationJournalListSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(format='%Y-%m-%d')
    order_number = serializers.SerializerMethodField()
    borrower_name = serializers.SerializerMethodField()
    committee_decision = serializers.SerializerMethodField()
    contract_number = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = CreditApplication
        fields = (
            "order_number",
            "created",
            "id",
            "borrower_name",
            "committee_decision",
            "contract_number",
            "status",
        )

    def get_order_number(self, obj: CreditApplication): # noqa
        credit_ids = CreditApplication.objects.filter(
            status=CreditStatus.ISSUED,
        ).order_by('pk').values_list('pk', flat=True)
        return list(credit_ids).index(obj.pk) + 1

    def get_borrower_name(self, obj: CreditApplication):
        business_name = obj.business_info.name
        borrower_name = obj.borrower_data.full_name

        if not business_name.startswith("ИП"):
            business_name = f'ИП {business_name}'

        return f'{borrower_name} {business_name}'

    def get_committee_decision(self, obj: CreditApplication):
        return f'№ {obj.pk} от {obj.decision.created.date()}'

    def get_contract_number(self, obj: CreditApplication):
        return f'№ {obj.contract.contract_number} от {obj.contract.contract_date.date()}'

    def get_status(self, obj: CreditApplication):
        return obj.get_status_display()


class ValidateGuarantorOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(write_only=True, label="OTP")


class ProductDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ('id', 'name', 'principal_limits', 'period', 'interest_rate',
                  'is_active', 'financing_purpose', 'financing_type')


class RejectionReasonDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = RejectionReason
        fields = ('id', 'status', 'active', 'order')
