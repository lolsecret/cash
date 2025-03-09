from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView, DeleteView, CreateView
from rest_framework import status

from .forms import SMSTemplateForm
from .models import SMSMessage, SMSTemplate


class SMSMessageListView(ListView):
    queryset = SMSMessage.objects.order_by('-pk')
    paginate_by = 10

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        return context


class SMSTemplateListView(ListView):
    queryset = SMSTemplate.objects.order_by('name')
    paginate_by = 10

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['create_form'] = SMSTemplateForm()
        return context


class SMSTemplateCreateView(CreateView):
    model = SMSTemplate
    form_class = SMSTemplateForm
    success_url = reverse_lazy('sms-template-list')


class SMSTemplateModalEditView(UpdateView):
    model = SMSTemplate
    form_class = SMSTemplateForm
    paginate_by = 10
    template_name = 'notifications/modals/smstemplate_form.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # noqa
        form = self.get_form()
        if not form.is_valid():
            return JsonResponse({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        form.save()
        return JsonResponse({"status": "success"})


class SMSTemplateDeleteView(DeleteView):
    model = SMSTemplate
    success_url = reverse_lazy('sms-template-list')
