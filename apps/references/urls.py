from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("", views.BlackListMemberViewSet)

urlpatterns = [
    path("reasons/", views.BlackListReasonsListView.as_view()),
    path("", include(router.urls)),
]
