from django.urls import path, include

from apps.flow.api.views import PKBBiometricUploadAPIView

urlpatterns = [
    path('biometry/<uuid:uuid>/', PKBBiometricUploadAPIView.as_view()),
]
