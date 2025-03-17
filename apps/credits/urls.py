from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import CreditSigningViewSet, UserPaymentsListView, CreatePaymentView, PaymentDetailView, \
    PaymentCallbackView, WithdrawalCreateView

router = DefaultRouter()
router.register(r'signing', CreditSigningViewSet, basename='credit-signing')

urlpatterns = [
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('leads/', views.LeadListView.as_view(), name='leads-list'),
    path('leads/new/', views.CreateLeadView.as_view(), name='leads-create'),
    path('leads/<int:pk>/', views.LeadDetailView.as_view(), name='lead-detail'),
    path('journal-view/', views.JournalView.as_view(), name='journal-view'),
    # path('', views.CreditApplicationListView.as_view(), name='credits-list'),
    path('list/', views.CreditApplicationListView.as_view(), name='credits-list'),
    path('list/<str:product>/', views.CreditApplicationListView.as_view(), name='credits-list'),
    path('redirect/', views.CreditsRedirectView.as_view(), name='credits-redirect'),
    path('<int:pk>/', views.CreditApplicationView.as_view(), name='credit-edit'),
    path('<int:pk>/v2/', views.CreditApplicationV2View.as_view(), name='credit-edit-v2'),
    path('<int:pk>/preview/', views.CreditApplicationPreviewView.as_view(), name='credit-preview'),
    path('<int:pk>/status/', views.CreditChangeStatusView.as_view(), name='credit-change-status'),
    path('<int:pk>/reject/', views.CreditApplicationRejectView.as_view(), name='credit-reject'),
    path('<int:pk>/finance-report/', views.FinanceReportView.as_view(), name='finance-report'),
    path('<int:pk>/upload-files/', views.CreditUploadFilesView.as_view(), name='upload-files'),
    path('<int:pk>/remove-files/', views.CreditRemoveFileView.as_view(), name='remove-files'),
    path('<int:pk>/credit-vote/', views.CreditVoteView.as_view(), name='credit-vote'),

    path('<int:pk>/guarantors/', views.GuarantorView.as_view(), name='guarantor-create'),
    path('<int:credit_pk>/guarantors/new/', views.GuarantorCreateView.as_view(), name='guarantor-create'),
    path('<int:credit_pk>/guarantors/<int:pk>/edit/', views.GuarantorUpdateView.as_view(), name='guarantor-edit'),
    path('<int:credit_pk>/guarantors/<int:pk>/delete/', views.GuarantorDeleteView.as_view(), name='guarantor-delete'),

    path('<int:pk>/print-form/<str:form_name>.html', views.print_forms_view, name='credit-print-form'),
    path('<int:pk>/print-form/<str:form_name>.pdf', views.print_forms_pdf_view, name='credit-print-form-pdf'),

    path('payments/', UserPaymentsListView.as_view(), name='payment-list'),
    path('<int:pk>/payment/', CreatePaymentView.as_view(), name='credit-payment-create'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('payments/callback/', PaymentCallbackView.as_view(), name='payment-callback'),

    # Создание и инициация вывода средств
    path('contracts/<int:contract_id>/withdrawal/',
         WithdrawalCreateView.as_view(),
         name='contract-withdrawal'),

    path('', include(router.urls)),
    path('api/', include('apps.credits.api.urls')),
]
