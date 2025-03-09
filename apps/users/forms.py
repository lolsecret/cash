from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BaseModelForm
from .models import User


class UserForm(BaseModelForm):
    phone = forms.CharField(
        label='Номер телефона',
        widget=forms.TextInput(attrs={'class': 'phone-input', 'placeholder': '+7(xxx)xxx xx xx'}),
    )
    password = forms.CharField(
        label='Пароль',
        required=False,
    )

    class Meta:
        model = User
        fields = (
            'last_name',
            'first_name',
            'middle_name',
            'role',
            'email',
            'phone',
            'branch',
            'is_active',
        )
        required = (
            'last_name',
            'first_name',
            'role',
            'email',
            'phone',
            'branch',
        )
        labels = {
            'middle_name': 'Отчество',
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if hasattr(self.Meta, 'required') and isinstance(self.Meta.required, (list, tuple)):
            for field in self.Meta.required:
                if field in self.fields:
                    self.fields[field].required = True

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and len(password) < 6:
            raise ValidationError(_('Слишком короткий пароль'), code='invalid')
        return password
