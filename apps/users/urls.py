from django.urls import path, include

from . import views

urlpatterns = [
    path('', views.UserListView.as_view(), name='users-list'),
    path('create/', views.UserCreateView.as_view(), name='users-create'),
    path('<int:pk>/edit/', views.UserEditView.as_view(), name='users-edit'),
    path('<int:pk>/delete/', views.UserDeleteView.as_view(), name='users-delete'),

    path('api/', include('apps.users.api.urls')),
]
