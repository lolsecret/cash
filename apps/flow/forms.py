from django import forms
from django.forms import JSONField
from django_json_widget.widgets import JSONEditorWidget

from .integrations.base import BaseService
from .models import ExternalService


class ServiceAPIAdminForm(forms.ModelForm):
    params = JSONField(required=False, widget=JSONEditorWidget(mode='code'), label='Параметры')
    cache_lifetime = forms.IntegerField(required=False, label='Время жизни кэша')
    service_class = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_class'] = forms.ChoiceField(choices=BaseService.get_descriptions())

    class Meta:
        model = ExternalService
        fields = '__all__'
