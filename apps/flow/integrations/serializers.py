from typing import Any, Dict

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from drf_writable_nested import NestedUpdateMixin

from apps.accounts.models import ProfilePersonalRecord
from apps.core.utils import format_datetime
from apps.credits.models import Lead, CreditApplication, RepaymentMethod, Decimal, Guarantor, CreditContract
from apps.people import MaritalStatus
from apps.people.models import (
    Address,
    Person,
    PersonalData,
)


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        exclude = ("iin",)
        extra_kwargs = {"iin": {"read_only": True}}


class AddressSerializer(NestedUpdateMixin, serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class PersonalDataSerializer(NestedUpdateMixin, serializers.ModelSerializer):
    person = PersonSerializer(required=False)
    reg_address = AddressSerializer()
    real_address = AddressSerializer(required=False)

    class Meta:
        model = PersonalData
        fields = "__all__"

    @transaction.atomic
    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

class ProfilePersonalRecordSerializer(NestedUpdateMixin, serializers.ModelSerializer):
    person = PersonSerializer(required=False, source='profile.person')
    reg_address = AddressSerializer()
    real_address = AddressSerializer(required=False)

    class Meta:
        model = ProfilePersonalRecord
        fields = "__all__"

    @transaction.atomic
    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class Backend1cCheckClientSerializer(serializers.ModelSerializer):
    LoanAmount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    desired_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)

    def update(self, instance: Lead, validated_data):
        current_loan_amount = validated_data.get("LoanAmount") or 0  # действующий кредит
        instance.current_loan_amount = current_loan_amount
        instance.save(update_fields=['current_loan_amount'])

        desired_amount = max(0, min(
            instance.product.max_loan_amount - current_loan_amount, instance.credit_params.principal
        ))

        instance.credit_params.principal = desired_amount
        instance.credit_params.save(update_fields=["principal"])
        return instance

    class Meta:
        model = Lead
        fields = ("LoanAmount", "desired_amount")


class Backend1cCreateClientAddressSerializer(serializers.ModelSerializer):
    country = serializers.ReadOnlyField()
    region = serializers.SerializerMethodField()
    area = serializers.ReadOnlyField(default="")
    locality = serializers.ReadOnlyField(source="city", default="")
    street = serializers.ReadOnlyField()
    houseNumber = serializers.ReadOnlyField(source="building")
    caseNumber = serializers.ReadOnlyField(default="")
    apartmentNumber = serializers.ReadOnlyField(default="flat")

    class Meta:
        model = Address
        fields = (
            'country',
            'region',
            'area',
            'locality',
            'street',
            'houseNumber',
            'caseNumber',
            'apartmentNumber',
        )

    def get_region(self, obj: Address):  # noqa
        return obj.region or obj.district


class Backend1cCreateClientSerializer(serializers.ModelSerializer):
    CLIENT_TYPE: str = 'ФизЛицо'
    CUSTOMER_TYPE: str = 'ИП'
    MARITAL_STATUS = {
        MaritalStatus.MARRIED: 'ЖенатЗамужем',
        MaritalStatus.SINGLE: 'ХолостНеЗамужем',
        MaritalStatus.DIVORCED: 'ВдовецВдова',
        MaritalStatus.WIDOW: 'РазведенРазведена'
    }

    borrowerID = serializers.CharField(source="borrower.iin", read_only=True)
    iin = serializers.CharField(source="borrower.iin", read_only=True)
    surName = serializers.CharField(source="borrower_data.last_name", default="", read_only=True)
    name = serializers.CharField(source="borrower_data.first_name", default="", read_only=True)
    middleName = serializers.CharField(source="borrower_data.middle_name", default="", read_only=True)
    dateofBirth = serializers.DateField(source="borrower.birthday", read_only=True, format="%Y-%m-%d")  # noqa
    document = serializers.SerializerMethodField()
    sex = serializers.CharField(source='borrower.get_gender_display')
    resident = serializers.BooleanField(source="borrower_data.resident", read_only=True)
    ContactInformation = serializers.SerializerMethodField()
    ContactFaces = serializers.SerializerMethodField()
    LegalAddress = Backend1cCreateClientAddressSerializer(source="borrower_data.reg_address")
    ActualAddress = Backend1cCreateClientAddressSerializer(source="borrower_data.real_address")
    PkbInfo = serializers.SerializerMethodField()
    BusinessInfo = serializers.SerializerMethodField()
    BankAccount = serializers.SerializerMethodField()
    familyStatus = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    amountOfChildren = serializers.CharField(source="borrower_data.dependants_child", read_only=True)
    countryOfCitizenship = serializers.CharField(source="borrower_data.citizenship", read_only=True)

    def get_document(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        # enumeration: УдостоверениеЛичностиРК
        # enumeration: ПаспортРК
        # enumeration: ВидНаЖительствоВРК
        # enumeration: ПаспортИностранца
        borrower_data: PersonalData = obj.borrower_data
        return {
            # "documentType": borrower_data.document_type,
            "documentType": 'УдостоверениеЛичностиРК',
            "documentNumber": borrower_data.document_number,
            "dateOfIssue": borrower_data.document_issue_date,
            "issuedBy": borrower_data.document_issue_org,
            "validity": borrower_data.document_exp_date,
        }

    def get_ContactInformation(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        return {
            "mobilePhone": obj.lead.mobile_phone.as_e164,
            "homePhone": "",
            "cityPhone": "",
            "email": "",
        }

    def get_ContactFaces(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        additional_contact = obj.borrower_data.additional_contact_relation.first()
        additional_phone = getattr(additional_contact, "contact", None)
        return {
            "ContactPerson": {
                "relationDegree": getattr(additional_contact, "relationship", ""),
                "fullName": getattr(additional_phone, "full_name", ""),
                "additionalContacts": getattr(additional_phone, "mobile_phone", "")
            }
        }

    def get_PkbInfo(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        soho_score = 0
        if hasattr(obj, 'credit_report') and obj.credit_report.soho_score:
            soho_score = obj.credit_report.soho_score

        return {
            "CATOCode": "",  # todo: done
            "experianSoho": soho_score,  # todo: done
            "customerType": self.CUSTOMER_TYPE,  # todo: done
        }

    def get_BusinessInfo(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        return {
            'businessName': obj.business_info.name,  # todo: done
            'industry': obj.business_info.branch,  # todo: done
            'placeOfBusiness': obj.business_info.place  # todo: done
        }

    def get_BankAccount(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        return {
            'iban': obj.borrower_data.bank_account_number,
            'nameBank': obj.borrower_data.bank.name,
            'bikBank': obj.borrower_data.bank.bic,
        }

    def get_familyStatus(self, obj: CreditApplication) -> str:  # noqa
        return self.MARITAL_STATUS.get(MaritalStatus(obj.borrower_data.marital_status), MaritalStatus.SINGLE)

    def get_type(self, obj: CreditApplication) -> str:  # noqa
        # ЮрЛицо/ФизЛицо
        return 'ФизЛицо'

    class Meta:
        model = CreditApplication
        fields = (
            "borrowerID",
            "iin",
            "surName",
            "name",
            "middleName",
            "dateofBirth",
            "document",
            "sex",
            "resident",
            "ContactInformation",
            "ContactFaces",
            "LegalAddress",
            "ActualAddress",
            "PkbInfo",
            "BusinessInfo",
            "BankAccount",
            "familyStatus",
            "type",
            "amountOfChildren",
            "countryOfCitizenship",
        )


class Backend1cCreateContractSerializer(serializers.Serializer):  # noqa
    loanManager = serializers.CharField(source="borrower_data.full_name", read_only=True)
    borrowerID = serializers.CharField(source="borrower.iin", read_only=True)
    guarantorID = serializers.SerializerMethodField()
    productID = serializers.SerializerMethodField()
    applicationID = serializers.IntegerField(source="id", read_only=True)
    businessName = serializers.CharField(source="borrower.job_place", default="", read_only=True)
    loanAmount = serializers.DecimalField(source="contract.params.principal", max_digits=20, decimal_places=2)
    periodOfLoan = serializers.IntegerField(source="contract.params.period", read_only=True)
    repaymentDate = serializers.DateField(source="contract.params.last_payment_date", format="%Y-%m-%d")
    rateRemuneration = serializers.DecimalField(source="contract.params.interest_rate", max_digits=5, decimal_places=2)
    kdif = serializers.DecimalField(source="contract.params.aeir", max_digits=5, decimal_places=1)
    repaymentMethod = serializers.SerializerMethodField()
    monthlyPayment = serializers.DecimalField(source="contract.params.monthly_payment", max_digits=20, decimal_places=2)
    loanPurpose = serializers.CharField(default="")  # todo: add loan purpose
    loanRepaymentFrequency = serializers.CharField(default="Ежемесячно")  # todo: Нужно ли добавить это?
    contractNumber = serializers.CharField(source="contract.contract_number", read_only=True)
    dateOfConclusion = serializers.SerializerMethodField()
    dateOfIssue = serializers.SerializerMethodField()
    contractСurrency = serializers.CharField(default="KZT", read_only=True)  # noqa символ на киррилице, НЕ ПРАВИТЬ!
    contractExpirationDate = serializers.DateField(source="contract.params.last_payment_date", format="%Y-%m-%d")
    PaymentSchedule = serializers.SerializerMethodField()
    BankAccount = serializers.SerializerMethodField()
    WarrantyNumber = serializers.SerializerMethodField()
    WarrantyPeriod = serializers.SerializerMethodField()

    def get_guarantorID(self, obj: CreditApplication) -> str: # noqa
        if obj.has_guarantors():
            return obj.guarantors.first().person_record.person.iin
        return ""

    def get_repaymentMethod(self, obj: CreditApplication) -> str:  # noqa
        return obj.contract.params.get_repayment_method_display()

    def get_productID(self, obj: CreditApplication) -> str:  # noqa
        rm_code = RepaymentMethod.code_for_1c(obj.approved_params.repayment_method)
        guarantor_code = "G" if obj.has_guarantors() else "B"
        return obj.product.contract_code + rm_code + guarantor_code

    def get_dateOfConclusion(self, obj: CreditApplication):  # noqa
        return timezone.localdate(obj.contract.contract_date)

    def get_dateOfIssue(self, obj: CreditApplication):  # noqa
        return timezone.localdate(obj.contract.contract_date)

    def get_PaymentSchedule(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        return {"PaymentLine": [
            {
                'paymentNumber': month,
                'targetDates': payment.maturity_date,
                # 'period': payment.maturity_date.strftime("%Y-%m-%d"),  # todo: Уточнить про даты
                'amountOfRepayment': payment.principal_amount,
                'paymentOfRemuneration': payment.reward_amount,
                'payment': payment.monthly_payment,
                'plannedBalance': payment.remaining_debt,
                'amountOfRepaymentPaid': Decimal('0.00'),
                'paymentOfRemunerationPaid': Decimal('0.00'),
            } for month, payment in enumerate(obj.approved_params.payments)]
        }

    def get_BankAccount(self, obj: CreditApplication) -> Dict[str, Any]:  # noqa
        bank = obj.borrower_data.bank
        bank_account_number = obj.borrower_data.bank_account_number
        return {
            'iban': bank_account_number.replace(' ', '') if bank_account_number else '',  # Убрать пробелы в IBAN
            'nameBank': bank.name if bank else '',
            'bikBank': bank.bic if bank else '',
        }

    def get_WarrantyNumber(self, obj: CreditApplication) -> str:  # noqa
        return f'{obj.contract.contract_number}Г1' if obj.has_guarantors() else ''

    def get_WarrantyPeriod(self, obj: CreditApplication) -> str:  # noqa
        return obj.contract.params.last_payment_date if obj.has_guarantors() else None


class Backend1cCreateGuarantorSerializer(serializers.ModelSerializer):
    CUSTOMER_TYPE: str = 'ИП'
    MARITAL_STATUS = {
        MaritalStatus.MARRIED: 'ЖенатЗамужем',
        MaritalStatus.SINGLE: 'ХолостНеЗамужем',
        MaritalStatus.DIVORCED: 'ВдовецВдова',
        MaritalStatus.WIDOW: 'РазведенРазведена'
    }
    guarantorID = serializers.CharField(source="person_record.person.iin", default="", read_only=True)
    iin = serializers.CharField(source="person_record.person.iin", read_only=True)
    surName = serializers.CharField(source="person_record.last_name", default="", read_only=True)
    name = serializers.CharField(source="person_record.first_name", default="", read_only=True)
    middleName = serializers.CharField(source="person_record.middle_name", default="", read_only=True)
    dateofBirth = serializers.DateField(source="person_record.person.birthday", read_only=True, format="%Y-%m-%d")  # noqa
    document = serializers.SerializerMethodField()
    sex = serializers.CharField(source='person_record.person.get_gender_display')
    resident = serializers.BooleanField(source="person_record.resident", read_only=True)
    ContactInformation = serializers.SerializerMethodField()
    LegalAddress = Backend1cCreateClientAddressSerializer(source="person_record.reg_address")
    ActualAddress = Backend1cCreateClientAddressSerializer(source="person_record.real_address")
    countryOfCitizenship = serializers.CharField(source="person_record.citizenship", read_only=True)
    familyStatus = serializers.SerializerMethodField()
    amountOfChildren = serializers.CharField(source="person_record.dependants_child", read_only=True)
    PkbInfo = serializers.SerializerMethodField()

    def get_document(self, obj: Guarantor) -> Dict[str, Any]:  # noqa
        person_record: PersonalData = obj.person_record
        return {
            "documentType": 'УдостоверениеЛичностиРК',
            "documentNumber": person_record.document_number,
            "dateOfIssue": person_record.document_issue_date,
            "issuedBy": person_record.document_issue_org,
            "validity": person_record.document_exp_date,
        }

    def get_ContactInformation(self, obj: Guarantor) -> Dict[str, Any]:  # noqa
        return {
            "mobilePhone": obj.credit.lead.mobile_phone.as_e164,
            "homePhone": "",
            "cityPhone": "",
            "email": "",
        }

    def get_PkbInfo(self, obj: Guarantor) -> Dict[str, Any]:  # noqa
        soho_score = 0
        if hasattr(obj, 'credit_report') and obj.credit_report.soho_score:
            soho_score = obj.credit_report.soho_score

        return {
            "CATOCode": "",  # todo: done
            "experianSoho": soho_score,  # todo: done
            "customerType": self.CUSTOMER_TYPE,  # todo: done
        }

    def get_familyStatus(self, obj: Guarantor) -> str:  # noqa
        return self.MARITAL_STATUS.get(MaritalStatus(obj.person_record.marital_status), MaritalStatus.SINGLE)

    class Meta:
        model = Guarantor
        fields = (
            "guarantorID",
            "iin",
            "surName",
            "name",
            "middleName",
            "dateofBirth",
            "document",
            "sex",
            "resident",
            "ContactInformation",
            "ActualAddress",
            "LegalAddress",
            "countryOfCitizenship",
            "familyStatus",
            "amountOfChildren",
            "PkbInfo",
        )


class BackendPaymentPayRequestSerializer(serializers.ModelSerializer):
    command = serializers.SerializerMethodField()
    txn_id = serializers.SerializerMethodField()
    sum = serializers.SerializerMethodField()
    pay_type = serializers.SerializerMethodField()
    txn_date = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    account = serializers.CharField(source="borrower.iin")
    contract_date = serializers.DateTimeField(format='%Y-%m-%d')

    class Meta:
        model = CreditContract
        fields = (
            "command",
            "txn_id",
            "sum",
            "account",
            "pay_type",
            "txn_date",
            "contract_number",
            "contract_date",
            "service_name"
        )

    def get_command(self, obj): # noqa
        return "pay"

    def get_pay_type(self, obj): # noqa
        return "1"

    def get_txn_id(self, obj):
        payment = self.context.get('payment')
        return payment.id

    def get_txn_date(self, obj): # noqa
        return format_datetime(timezone.localtime())

    def get_service_name(self, obj): # noqa
        return "Smart Billing"

    def get_sum(self, obj):
        payment = self.context.get('payment')
        return payment.amount
