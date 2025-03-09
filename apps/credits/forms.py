import logging
from pprint import pprint

from PIL import Image
from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column
from django_fsm import can_proceed

from apps.api.scoring.pipelines import lead_from_api_pipeline
from apps.core.forms import BaseForm, BaseModelForm, DateInput, DateTimeInput, TimeInput
from apps.core.models import City, Bank, Branch
from apps.people import MaritalStatus, RelationshipType, Gender
from apps.people.models import PersonContact, PersonalData, Address, Person
from apps.credits import RepaymentMethod, CreditStatus
from apps.credits.models import (
    Product,
    Lead,
    BusinessInfo,
    CreditApplication,
    CreditParams,
    CreditFinance,
    CreditDocument,
    DocumentType, RejectionReason,
)
from apps.people.validators import IinValidator

logger = logging.getLogger(__name__)


class NumberInputField(forms.IntegerField):
    def __init__(self, label, *, max_value=None, min_value=None, **kwargs):
        kwargs['label'] = label
        kwargs['widget'] = forms.TextInput(attrs={'class': 'number-input'})
        super().__init__(max_value=max_value, min_value=min_value, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(' ', '')
        return super().to_python(value)


class SimpleLeadForm(BaseForm):
    iin = forms.CharField(
        label='ИИН',
        widget=forms.TextInput(attrs={'class': 'iin-input'}),
        validators=[IinValidator()]
    )
    mobile_phone = forms.CharField(
        label='Мобильный тел.',
        widget=forms.TextInput(attrs={'class': 'phone-input', 'placeholder': '+7(xxx)xxx xx xx'}),
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        label="Город/нас. пункт",
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        label='Программа',
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    desired_amount = NumberInputField(_("Запрашиваемый сумма"))
    # desired_amount = forms.IntegerField(
    #     label="Запрашиваемый сумма",
    #     # min_value=200_000,
    #     # max_value=5_000_000,
    #     widget=forms.TextInput(attrs={'class': 'number-input'}),
    # )
    desired_period = NumberInputField(_("Запрашиваемый срок <small class='text-muted'>(мес)</small>"))
    repayment_method = forms.ChoiceField(
        choices=[('', '----')] + RepaymentMethod.choices,
        label="Метод погашения",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper.layout = Layout(
            Column('iin', css_class='form-group col-md-12 mb-3'),
            Column('mobile_phone', css_class='form-group col-md-12 mb-3'),
            Column('city', css_class='form-group col-md-12 mb-3'),
            Column('desired_amount', css_class='form-group col-md-12 mb-3'),
            Column('desired_period', css_class='form-group col-md-12 mb-3'),
            Column('product', css_class='form-group col-md-12 mb-3'),
            Column('repayment_method', css_class='form-group col-md-12 mb-3'),
        )

    def clean_desired_amount(self):
        product: Product = self.cleaned_data.get('product')
        desired_amount = self.cleaned_data.get('desired_amount')
        if product.principal_limits.lower > desired_amount:
            raise ValidationError(
                _("Ошибка суммы, не может быть меньше %(value)s"),
                params={'value': f"{product.principal_limits.lower:,}".replace(',', ' ')},
                code='invalid'
            )

        elif product.principal_limits.upper < desired_amount:
            raise ValidationError(
                _("Ошибка суммы, не может быть больше %(value)s"),
                params={'value': f"{product.principal_limits.upper:,}".replace(',', ' ')},
                code='invalid'
            )

        return desired_amount

    def clean_desired_period(self):
        product: Product = self.cleaned_data.get('product')
        desired_period = self.cleaned_data.get('desired_period')
        if product.period_limits.lower > desired_period:
            raise ValidationError(
                _("Ошибка срока, не может быть меньше %(value)s"),
                params={'value': f"{product.period_limits.lower:,}".replace(',', ' ')},
                code='invalid'
            )

        elif product.period_limits.upper < desired_period:
            raise ValidationError(
                _("Ошибка срока, не может быть больше %(value)s"),
                params={'value': f"{product.period_limits.upper:,}".replace(',', ' ')},
                code='invalid'
            )
        return desired_period

    def create(self) -> Lead:
        lead: Lead = lead_from_api_pipeline({'channel': None, 'branch': Branch.objects.first(), **self.cleaned_data})

        if lead.credit_params.principal not in lead.product.principal_limits:
            lead.reject(_("Указанная сумма не подходит по параметрам"))

        if lead.credit_params.period not in lead.product.period_limits:
            lead.reject(_("Указанный период не подходит по параметрам"))

        return lead


class CreditPreviewForm(BaseForm):
    class Meta:
        model = CreditApplication
        fields = (
            'product',
        )


class CreditParamsForm(BaseForm):
    principal = NumberInputField(_("Сумма"))
    period = forms.IntegerField(
        label='Срок',
        required=True,
        widget=forms.TextInput(attrs={'class': 'period-input'}),
    )
    interest_rate = forms.DecimalField(
        label='Ставка <small>(%)</small>',
        required=False,
        widget=forms.TextInput(attrs={'class': 'percent-input'}),
    )
    repayment_method = forms.ChoiceField(
        choices=RepaymentMethod.choices,
        label='Метод погашения',
        required=False,
    )

    def save(self, credit_params: CreditParams):
        if isinstance(credit_params, CreditParams):
            for attr, value in self.cleaned_data.items():
                if value:
                    setattr(credit_params, attr, value)
            credit_params.save()


class AddressForm(BaseForm):
    country = forms.CharField(label='Страна')
    region = forms.CharField(label='Регион')
    city = forms.CharField(label='Город')
    district = forms.CharField(label='Область')
    street = forms.CharField(label='Улица')
    building = forms.CharField(label='Дом / здание')
    corpus = forms.CharField(label='Корпус')
    flat = forms.CharField(label='Квартира')


class BorrowerDataForm(BaseForm):
    resident = forms.BooleanField(label="Резидент")
    citizenship = forms.BooleanField(label="Гражданство")

    document_type = forms.CharField(label="Вид документов")
    document_series = forms.CharField(label="Серия", required=False)
    document_number = forms.CharField(label="Номер")
    document_issue_date = forms.DateField(label="Дата выдачи")
    document_exp_date = forms.DateField(label="Срок действия")
    document_issue_org = forms.CharField(label="Кем выдан")

    marital_status = forms.ChoiceField(choices=MaritalStatus.choices, label="Семейное положение")
    dependants_additional = forms.IntegerField(label="Кол-во иждевенцев", initial=0)
    education = forms.CharField(label="Образование")


class BorrowerForm(BaseForm):
    iin = forms.CharField(label='ИИН')
    resident = forms.BooleanField(label="Резидент")
    citizenship = forms.CharField(label="Гражданство")
    marital_status = forms.ChoiceField(choices=MaritalStatus.choices, label="Семейное положение")


class RegAddressForm(AddressForm):
    """Адрес прописки"""
    country = forms.CharField(label='Страна', required=False)
    region = forms.CharField(label='Регион', required=False)
    city = forms.CharField(label='Город', required=False)
    district = forms.CharField(label='Область', required=False)
    street = forms.CharField(label='Улица', required=False)
    building = forms.CharField(label='Дом / здание', required=False)
    corpus = forms.CharField(label='Корпус', required=False)
    flat = forms.CharField(label='Квартира', required=False)


class RealAddressForm(AddressForm):
    """Адрес проживания"""
    same_reg_address = forms.BooleanField(
        label='Адрес проживания совпадает с адресом прописки',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    country = forms.CharField(label='Страна', required=False)
    region = forms.CharField(label='Область', required=False)
    city = forms.CharField(label='Населенный пункт', required=False)
    district = forms.CharField(label='Район', required=False)
    street = forms.CharField(label='Улица', required=False)
    building = forms.CharField(label='Дом / здание', required=False)
    corpus = forms.CharField(label='Корпус', required=False)
    flat = forms.CharField(label='Квартира', required=False)

    def save(self, personal_record: PersonalData):
        same_reg_address = self.cleaned_data.pop('same_reg_address')
        real_address_data = self.cleaned_data.copy()
        if same_reg_address:
            real_address_data = forms.model_to_dict(personal_record.reg_address, exclude=['id'])

        for attr, val in real_address_data.items():
            setattr(personal_record.real_address, attr, val)

        personal_record.real_address.save()


class RegAddressUpdateForm(BaseModelForm):
    class Meta:
        model = Address
        fields = '__all__'

    def save(self, commit=True) -> Address:
        return super().save(commit)


class RealAddressUpdateForm(RegAddressUpdateForm):
    same_reg_address = forms.BooleanField(
        label='Адрес проживания совпадает с адресом прописки',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def update_data_with_same_address(self, data: dict):
        for attr, value in data.items():
            if hasattr(self.instance, attr):
                setattr(self.instance, attr, value)


class RegAddressCreateForm(BaseModelForm):
    country = forms.CharField(label='Страна', required=False)
    region = forms.CharField(label='Регион', required=False)
    city = forms.CharField(label='Город', required=False)
    district = forms.CharField(label='Область', required=False)
    street = forms.CharField(label='Улица', required=False)
    building = forms.CharField(label='Дом / здание', required=False)
    corpus = forms.CharField(label='Корпус', required=False)
    flat = forms.CharField(label='Квартира', required=False)

    class Meta:
        model = Address
        fields = '__all__'


class RealAddressCreateForm(RegAddressCreateForm):
    same_reg_address = forms.BooleanField(
        label='Адрес проживания совпадает с адресом прописки',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class BorrowerAdditionalForm(BaseModelForm):
    """Дополнительные данные клиента"""
    marital_status = forms.ChoiceField(choices=MaritalStatus.choices, label="Семейное положение")
    spouse_iin = forms.CharField(
        label="ИИН Супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'iin-input', 'pattern': '[0-9]+'}),
        validators=[IinValidator],
    )
    spouse_phone = forms.CharField(
        label="Телефон супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'phone-input'}),
    )
    spouse_name = forms.CharField(label="ФИО супруги/а", required=False)

    dependants_additional = forms.IntegerField(
        label="Кол-во иждевенцев",
        widget=forms.TextInput(attrs={'class': 'dependants-input'}),
    )
    education = forms.CharField(label="Образование", required=False)

    class Meta:
        model = PersonalData
        fields = (
            'marital_status',
            'spouse_iin',
            'spouse_phone',
            'spouse_name',
            'dependants_additional',
            'education',
            'bank',
            'bank_account_number',
        )


class AccountDetailsForm(BaseForm):
    """Контактные данные"""
    bank_name = forms.ModelChoiceField(
        queryset=Bank.objects.all(),
        label="Наименование банка",
        required=False,
        empty_label='-- Выберите банк --'
    )
    bank_account_number = forms.CharField(label="Номер счета", required=False)
    bank_bik = forms.CharField(label="БИК банка", required=False)


class AdditionalContactForm(BaseForm):
    """Контактные данные"""
    first_name = forms.CharField(label="ФИО дополнительного контакта", required=False)
    mobile_phone = forms.CharField(
        label="Мобильный телефон",
        required=False,
        widget=forms.TextInput(attrs={'class': 'phone-input'}),
    )
    relationship = forms.ChoiceField(label="Степень родства", choices=RelationshipType.choices, required=False)

    def save(self, person_record: PersonalData):
        relationship = self.cleaned_data.pop('relationship')
        additional_contact = person_record.additional_contact_relation.first()
        if not additional_contact:
            contact_info = PersonContact.objects.create(**self.cleaned_data)
            person_record.additional_contact_relation.create(
                record=person_record,
                contact=contact_info,
                relationship=relationship,
            )

        else:
            for attr, val in self.cleaned_data.items():
                setattr(additional_contact.contact, attr, val)
            additional_contact.contact.save()
            additional_contact.relationship = relationship
            additional_contact.save()


class BusinessInfoForm(BaseModelForm):
    """Информация о бизнесе"""
    name = forms.CharField(label="Наименование ИП", required=False)
    branch = forms.CharField(label="Отрасль", required=False)
    place = forms.CharField(label="Место бизнеса", required=False)
    working_since = forms.IntegerField(label="Время работы ИП", required=False)
    website_social = forms.CharField(label="Веб сайт/соц. сети", required=False)
    description = forms.CharField(
        label="Описание бизнеса",
        widget=forms.Textarea(attrs={'rows': 8}),
        required=False,
    )
    expert_opinion = forms.CharField(
        label="Заключение кредитного эксперта",
        widget=forms.Textarea(attrs={'rows': 8}),
        required=False,
    )
    funding_plan = forms.CharField(
        label="План финансирования",
        widget=forms.Textarea(attrs={'rows': 8}),
        required=False,
    )

    class Meta:
        model = BusinessInfo
        exclude = ['credit']


class CreditFinanceForm(BaseModelForm):
    """Финансовые данные"""
    cash_box = NumberInputField(_("Касса"), required=False)
    avg_daily_revenue = NumberInputField(_("Среднесуточный размер выручки"), required=False)
    economy = NumberInputField(_("Сбережения"), required=False)
    tmz = NumberInputField(_("ТМЗ"), required=False)
    receivable = NumberInputField(_("Дебиторская задолженность"), required=False)
    equipment = NumberInputField(_("Оборудование"), required=False)
    transport = NumberInputField(_("Транспорт"), required=False)
    real_property = NumberInputField(_("Недвижимость"), required=False)
    other_current_assets = NumberInputField(_("Прочие оборотные активы"), required=False)
    credit_debt = NumberInputField(_("Кредитная задолженность (долги за товар и прочее)"), required=False)

    # Readonly fields
    total_working_capital = forms.IntegerField(
        label="Всего оборотных средств",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    total_fixed_assets = forms.IntegerField(
        label="Всего основных средств",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    active_currency_rate = forms.IntegerField(
        label=_("Итого Дебет"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    credit_debt_current = forms.IntegerField(
        label=_("Задолженность по текущим кредитам"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    credit_debt_total = forms.IntegerField(
        label=_("Всего кредитная задолженность"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    equity = forms.IntegerField(
        label=_("Собственный капитал"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )
    passive_currency_rate = forms.IntegerField(
        label=_("Итого Кредит"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'number-input'}),
    )

    class Meta:
        model = CreditFinance
        exclude = (
            'credit',
            # 'credit_debt_total',
        )
        labels = {
            'financial_info_period': 'Время выезда',
            'formation_time': 'Время',
        }
        widgets = {
            'financial_info_period': DateInput(),
            'formation_time': TimeInput(),
        }

    def clean(self):
        # Всего оборотных средств
        self.cleaned_data['total_working_capital'] = sum([
            self.cleaned_data.get('receivable', 0),
            self.cleaned_data.get('economy', 0),
            self.cleaned_data.get('tmz', 0),
            self.cleaned_data.get('other_current_assets', 0),
        ])

        # Всего основных средств
        self.cleaned_data['total_fixed_assets'] = sum([
            self.cleaned_data.get('equipment', 0),
            self.cleaned_data.get('transport', 0),
            self.cleaned_data.get('real_property', 0),
        ])

        # Итого Дебет
        self.cleaned_data['active_currency_rate'] = sum([
            self.cleaned_data.get('total_working_capital', 0),
            self.cleaned_data.get('total_fixed_assets', 0),
        ])

        # Всего кредитная задолженность
        self.cleaned_data['credit_debt_total'] = sum([
            self.cleaned_data.get('credit_debt', 0),
            self.cleaned_data.get('credit_debt_current', 0),
        ])

        # Собственный капитал
        active_currency_rate = self.cleaned_data.get('active_currency_rate', 0)
        credit_debt_total = self.cleaned_data.get('credit_debt_total', 0)
        try:
            self.cleaned_data['equity'] = active_currency_rate - credit_debt_total
        except Exception as exc:
            logger.error("ошибка вычисления credit_finance.equity %s", exc)

        # Итого Кредит
        self.cleaned_data['passive_currency_rate'] = sum([
            self.cleaned_data.get('credit_debt', 0),
            self.cleaned_data.get('credit_debt_current', 0),
        ])
        return self.cleaned_data


class CreditFinanceReportForm(BaseModelForm):
    """Финансовые данные"""

    class Meta:
        model = CreditFinance
        fields = (
            'begin_date',
            'end_date',
            'report_comment',
        )


class CreditApplicationPreviewForm(BaseForm):
    status = forms.ChoiceField(choices=CreditStatus.choices, label='Статус', required=False)
    principal = NumberInputField(label=_('Сумма займа'), disabled=True, required=False)
    period = forms.IntegerField(label=_('Срок займа'), disabled=True, required=False)
    repayment_method = forms.ChoiceField(
        choices=RepaymentMethod.choices,
        label='Метод погашения',
        required=False,
    )
    status_reason = forms.ModelChoiceField(
        queryset=RejectionReason.objects.filter(active=True),
        label=_('Детали отказа'),
        required=False,
    )
    comment = forms.CharField(
        required=True,
        label='',
        widget=forms.Textarea(attrs={'rows': '2'}),
    )


class CreditApplicationDetailForm(
    RealAddressForm,
    BorrowerAdditionalForm,
    AdditionalContactForm,
    # AccountDetailsForm,
    BusinessInfoForm,
    BaseForm,
):
    """Общая форма для редактирования заявки"""

    product = forms.ModelChoiceField(
        label='Программа',
        queryset=Product.objects.all(),
    )
    branch = forms.ModelChoiceField(
        label='Филиал',
        queryset=Branch.objects.all(),
    )


class LeadForm(BaseModelForm):
    class Meta:
        model = Lead
        fields = (
            'branch',
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.fields['branch'].initial:
            self.fields['branch'].initial = Branch.objects.first()
            self.fields['branch'].empty_label = None


class CreditApplicationForm(BaseModelForm):
    class Meta:
        model = CreditApplication
        fields = (
            'product',
        )


class PersonForm(BaseForm):
    iin = forms.CharField(
        label='ИИН',
        widget=forms.TextInput(attrs={'class': 'iin-input'}),
    )
    gender = forms.ChoiceField(label='Пол', choices=Gender.choices)
    birthday = forms.DateField(label='Дата рождения')

    def save(self):
        return Person.from_iin.create(self.cleaned_data.get('iin'))


class GuarantorForm(AccountDetailsForm, BaseModelForm):
    person_iin = forms.CharField(
        label='ИИН',
        widget=forms.TextInput(attrs={'class': 'iin-input'})
    )
    person_birthday = forms.DateField(label='Дата рождения', required=False)

    document_type = forms.CharField(label='Вид документов')
    document_series = forms.CharField(label='Серия', required=False)
    document_number = forms.CharField(label='Номер')
    document_issue_date = forms.DateField(
        label='Дата выдачи',
        widget=forms.DateInput(attrs={'class': 'date-input'})
    )
    document_exp_date = forms.DateField(
        label='Срок действия',
        widget=forms.DateInput(attrs={'class': 'date-input'})
    )
    document_issue_org = forms.CharField(label='Кем выдан')

    marital_status = forms.ChoiceField(
        label="Семейное положение",
        choices=MaritalStatus.choices,
    )
    spouse_iin = forms.CharField(
        label="ИИН Супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'iin-input'})
    )
    spouse_phone = forms.CharField(
        label="Телефон супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'phone-input'}),
    )
    spouse_name = forms.CharField(label="ФИО супруги/а", required=False)

    dependants_additional = forms.IntegerField(
        label="Кол-во иждевенцев",
        initial=0,
        widget=forms.TextInput(attrs={'class': 'dependants-input'})
    )
    education = forms.CharField(label="Образование", required=False)

    class Meta:
        model = PersonalData
        exclude = (
            'dependants_child',
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        instance: PersonalData = kwargs.get('instance')
        if isinstance(instance, PersonalData):
            self.fields['person_iin'].initial = instance.person.iin
            self.fields['person_birthday'].initial = instance.person.birthday

    def clean_person(self):
        return Person.from_iin.create(self.cleaned_data.get('person_iin'))

    def clean(self):
        person_iin = self.cleaned_data.get('person_iin')
        person_birthday = self.cleaned_data.get('person_birthday')
        self.cleaned_data.update({'person': Person.from_iin.create(person_iin)})
        self.errors.pop('person')
        return self.cleaned_data


class GuarantorUpdateForm(AccountDetailsForm, BaseForm):
    person_iin = forms.CharField(label='ИИН')
    person_birthday = forms.DateField(label='Дата рождения', required=False)

    last_name = forms.CharField(label='Фамилия')
    first_name = forms.CharField(label='Имя')
    middle_name = forms.CharField(label='Отчество', required=False)
    citizenship = forms.CharField(label='Гражданство')
    resident = forms.BooleanField(label='Резидент', required=False)

    document_type = forms.CharField(label='Вид документов')
    document_series = forms.CharField(label='Серия', required=False)
    document_number = forms.CharField(label='Номер')
    document_issue_date = forms.DateField(label='Дата выдачи')
    document_exp_date = forms.DateField(label='Срок действия')
    document_issue_org = forms.CharField(label='Кем выдан')

    marital_status = forms.ChoiceField(label="Семейное положение", choices=MaritalStatus.choices)
    spouse_iin = forms.CharField(
        label="ИИН Супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'iin-input'})
    )
    spouse_phone = forms.CharField(
        label="Телефон супруги/а",
        required=False,
        widget=forms.TextInput(attrs={'class': 'phone-input'}),
    )
    spouse_name = forms.CharField(label="ФИО супруги/а", required=False)

    dependants_additional = forms.CharField(label="Кол-во иждевенцев", initial=0)
    education = forms.CharField(label="Образование", required=False)

    def __init__(self, **kwargs):
        self.instance: PersonalData = kwargs.pop('instance')
        super().__init__(**kwargs)
        self.initial_data()

    def initial_data(self):
        if hasattr(self.instance, 'person'):
            self.fields['person_iin'].initial = self.instance.person.iin
            self.fields['person_birthday'].initial = self.instance.person.birthday

        print("self.instance:", self.instance)
        for key in self.fields.keys():
            if hasattr(self.instance, key):
                print(key, getattr(self.instance, key))
                self.fields[key].initial = getattr(self.instance, key)

    def save(self, commit=False) -> PersonalData:
        for key, value in self.cleaned_data.items():
            if hasattr(self.instance, key):
                value = None if value == '' else value
                setattr(self.instance, key, value)

        if commit:
            self.instance.save()

        return self.instance


class DocumentUploadForm(forms.Form):
    document_type = forms.CharField()
    file = forms.FileField()

    def save(self, credit: CreditApplication):
        document_type = get_object_or_404(DocumentType, code=self.cleaned_data['document_type'])
        file = self.cleaned_data['file']
        try:
            image_obj = Image.open(file)
            image_obj.verify()
            return CreditDocument.objects.create(
                credit=credit,
                document_type=document_type,
                image=file,
            )

        except Exception:  # noqa
            return CreditDocument.objects.create(
                credit=credit,
                document_type=document_type,
                document=file,
            )


class CreditApplicationAdminForm(forms.ModelForm):
    new_status = forms.ChoiceField(choices=CreditStatus.choices, label="Смена статуса")

    class Meta:
        model = CreditApplication
        fields = ("new_status", "reject_reason", "status_reason")

    def save(self, commit=False):
        instance = super().save(commit=False)
        new_status = self.cleaned_data.get("new_status")
        transition_method = instance.get_transition_by_status(new_status)
        if can_proceed(transition_method):
            transition_method()
            instance.status_reason = self.cleaned_data.get('status_reason', '')
            instance.reject_reason = self.cleaned_data.get('reject_reason', '')
            instance.save()
        return instance
