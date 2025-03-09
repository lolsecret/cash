from django.urls import path

from . import views

urlpatterns = [
    path('profile/', views.ProfileView.as_view()),
    # path('permissions/', CreditDetailView.as_view()),
    path('managers/', views.ManagerList.as_view())
]
