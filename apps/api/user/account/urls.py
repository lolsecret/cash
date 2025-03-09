from django.urls import path

from . import views

urlpatterns = [
    path('info/', views.AccountInfo.as_view(), name="account-info"),
    path('profile-data/', views.ProfileDataView.as_view(), name='profile-data')
]
