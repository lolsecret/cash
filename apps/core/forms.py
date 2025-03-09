from django import forms
from crispy_forms.helper import FormHelper

from apps.flow import ServicePurposes
from apps.flow.models import ExternalService


class DateInput(forms.DateInput):
    input_type = 'date'


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'


class TimeInput(forms.DateTimeInput):
    input_type = 'time'


class BaseForm(forms.Form):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'form-label'


class BaseModelForm(forms.ModelForm):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'form-label'



