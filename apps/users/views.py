from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView, UpdateView, CreateView, DeleteView
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from .forms import UserForm
from .models import (
    User,
)


class UserListView(ListView):
    queryset = User.objects.order_by('last_name', 'first_name')
    paginate_by = 10

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['form'] = UserForm()
        context['form'].fields['password'].required = True
        return context


class UserCreateView(CreateView):
    model = User
    form_class = UserForm
    success_url = reverse_lazy('users-list')
    template_name = 'users/modals/create_user_modal.html'

    def post(self, request, *args, **kwargs):
        self.object = None  # noqa
        form: UserForm = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)

        form.save()
        return JsonResponse({"status": "success"}, status=status.HTTP_201_CREATED)


class UserEditView(UpdateView):
    model = User
    form_class = UserForm
    paginate_by = 10
    template_name = 'users/modals/user_form.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        return context

    def post(self, request, *args, **kwargs):
        self.object: User = self.get_object()  # noqa
        form: UserForm = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)

        password = form.cleaned_data.pop('password')
        if password:
            self.object.set_password(password)

        form.save()
        return JsonResponse({"status": "success"}, status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name='dispatch')
class UserDeleteView(DeleteView):
    model = User
    success_url = reverse_lazy('users-list')
