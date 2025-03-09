from django.urls import path

from apps.logger.views import LogListView, LogDetailView, LogDownloadView

urlpatterns = [
    path('', LogListView.as_view(), name='logger-list'),
    path('<int:pk>/', LogDetailView.as_view(), name='logger-detail'),
    path('<int:pk>/download/', LogDownloadView.as_view(), name='logger-download'),
]
