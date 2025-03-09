from django.urls import path
from .views import (
    BankAccountListCreateView,
    BankAccountDetailView,
    BankCardListCreateView,
    BankCardDetailView,
)

urlpatterns = [
    path('accounts/', BankAccountListCreateView.as_view(), name='bank-account-list-create'),
    path('accounts/<int:pk>/', BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('cards/', BankCardListCreateView.as_view(), name='bank-card-list-create'),
    path('cards/<int:pk>/', BankCardDetailView.as_view(), name='bank-card-detail'),
]
