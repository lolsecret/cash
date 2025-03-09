from django.urls import path

from . import views

urlpatterns = [
    path("apply/", views.LeadApplyAPIView.as_view(), name='apply'),

    # path("apply/", views.LeadApplyAPIView.as_view(), name='apply'),
    # path("start/<uuid:uuid>/", views.LeadScoringView.as_view(), name="lead-scoring"),
]
