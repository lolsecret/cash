from django.urls import path

from . import views

urlpatterns = [
    path('logs/', views.SMSMessageListView.as_view(), name='sms-list'),
    path('templates/create/', views.SMSTemplateCreateView.as_view(), name='sms-template-create'),
    path('templates/<int:pk>/edit/', views.SMSTemplateModalEditView.as_view(), name='sms-template-edit'),
    path('templates/<int:pk>/delete/', views.SMSTemplateDeleteView.as_view(), name='sms-template-delete'),
    path('templates/', views.SMSTemplateListView.as_view(), name='sms-template-list'),
]
