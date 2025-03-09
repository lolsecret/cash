from apps.core.forms import BaseModelForm
from .models import SMSTemplate, SMSType


class SMSTemplateForm(BaseModelForm):
    class Meta:
        model = SMSTemplate
        fields = (
            'name',
            'content',
        )
        labels = {
            'name': 'Заголовок СМС',
            'content': 'Текст СМС',
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        template_exists = SMSTemplate.objects.values_list('name__id', flat=True)
        self.fields['name'].queryset = SMSType.objects.exclude(pk__in=template_exists)
