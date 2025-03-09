from django.urls import path

from . import views

urlpatterns = [
    path('payment/history/', views.PaymentHistory.as_view(), name='payment-history'),
    path('payment/partial/sum/', views.LoanPaymentSumPartialView.as_view(), name='payment-partial-sum'),
    path('payment/full/sum/', views.LoanPaymentSumFullView.as_view(), name='payment-full-sum'),
    path('credits/contract/', views.CreditContractView.as_view(), name='credits-contract'),
    path('credits/get-contracts/', views.ProfileCreditContractsView.as_view(), name='get_contracts'),
    path('credits/validate-to-sign/', views.ValidateBorrowerOTPtoSign.as_view(), name='validate_to_sign'),
    path('payment/<str:iin>/contract/', views.CreditPaymentView.as_view(), name='payment-contract'),
    path('credits/', views.ProfileCreditsView.as_view(), name='credit-list'),
    path('credits/<int:pk>/', views.ProfileCreditsView.as_view(), name='credit-detail'),]
