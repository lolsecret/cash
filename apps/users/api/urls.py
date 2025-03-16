from django.urls import path

from . import views

urlpatterns = [
    path('profile/', views.ProfileView.as_view()),
    # path('permissions/', CreditDetailView.as_view()),
    path('managers/', views.ManagerList.as_view()),
    path('users/', views.UserListView.as_view()),
    path('users/<int:pk>/', views.UserDetailView.as_view()),
    path('token/', views.CustomAuthToken.as_view())
]
