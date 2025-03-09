from django.urls import path, include

from . import views

urlpatterns = [
    path('auth/', include('apps.api.user.auth.urls')),

    path('account/', include('apps.api.user.account.urls')),
    path('card/', include('apps.api.user.card.urls')),
    path('loan/', include('apps.api.user.loan.urls')),

    path('<int:pk>/active-request/', views.ActiveRequestView.as_view(), name='user-active-request'),
]
