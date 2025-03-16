from django.urls import path, include
from rest_framework import routers

from apps.credits.api import views

router = routers.DefaultRouter()
router.register(r'(?P<credit_id>\d+)/documents', views.CreditDocumentViewSet, basename="credit-document")

urlpatterns = [
    path('leads/export/', views.LeadsExportView.as_view(), name='export_leads_csv'),
    path('list/export/', views.CreditApplicationsExportView.as_view(), name='export_credits_csv'),
    path('registration-journals/', views.RegistrationJournalView.as_view(), name='registration-journals-view'),
    path('registration-journals/export/', views.RegistrationJournalsExportView.as_view(), name='export_journals_csv'),

    path('', include(router.urls)),
    path('parse-iin/', views.ParseIINView.as_view()),

    path('leads/', views.LeadListView.as_view()),
    path('list/', views.CreditListView.as_view()),
    path('create/', views.CreditCreateView.as_view()),
    path('redirect/', views.CreditRedirectView.as_view()),
    path('<int:pk>/', views.CreditDetailView.as_view()),
    path('<int:pk>/preview/', views.CreditPreviewView.as_view()),
    path('<int:pk>/reject/', views.RejectCreditView.as_view()),
    path('<int:pk>/credit-report/', views.CreditReportView.as_view()),
    path('<int:pk>/credit-finance/', views.CreditFinanceUpdateView.as_view()),
    path('<int:pk>/change-status/', views.CreditChangeStatusView.as_view()),
    path('<int:pk>/callback-change-status/', views.Callback1cChangeStatusView.as_view()),

    path('<int:credit_id>/credit-history/', views.CreditHistoryDetailView.as_view()),
    path('<int:pk>/upload-files/', views.CreditUploadFilesView.as_view()),
    path('<int:pk>/vote/', views.CreditVoteView.as_view()),

    path('<int:pk>/print-forms/', views.PrintFormsView.as_view()),

    path('products/<int:pk>/', views.ProductDetailView.as_view()),
    path('rejection-reasons/<int:pk>/', views.RejectionReasonDetailView.as_view()),


    path('credit-statuses/', views.CreditStatusesListView.as_view()),
    path('products/', views.CreditProductListView.as_view()),
    path('cities/', views.CityListView.as_view()),
    path('branches/', views.BranchListView.as_view()),
    path('banks/', views.BankListView.as_view()),
    path('document-groups/', views.DocumentGroupsListView.as_view()),
    path('rejection-reasons/', views.RejectionReasonListView.as_view()),

    path('dashboard/', views.StatisticView.as_view()),

    path('<int:pk>/finance-report/', views.FinanceReportCalcView.as_view()),
    path('finance-report-type/', views.FinanceReportTypeView.as_view()),
]
