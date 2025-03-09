from django.urls import path

from apps.core.api.views import DocumentListView, FAQListView
from . import views

urlpatterns = [
    path('calculator/', views.CalculatorView.as_view()),
    path('document/', DocumentListView.as_view(), name='front-document'),
    path('faq/', FAQListView.as_view(), name='front-faq'),
    path('email/', views.EmailView.as_view(), name='email'),
    path('call/me/', views.CallMeView.as_view(), name='call-me'),
    path('notification_text/', views.NotificationTextListView.as_view()),

    path('credit/', views.CreditRequestView.as_view(), name='credit-request'),
    path('products/', views.ProductListView.as_view(), name='credit-products'),

    path('<int:pk>/print-forms/', views.ProfilePrintFormsView.as_view()),
    path('<int:pk>/print-form/<str:form_name>.html', views.PrintFormView.as_view(), name='profile-print-form'),
    path('<int:pk>/print-form/<str:form_name>.pdf', views.PrintFormPDFView.as_view(), name='profile-print-form-pdf'),
]
