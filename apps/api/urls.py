from django.urls import path, include

urlpatterns = [
    # Public endpoints
    path("scoring/", include("apps.api.scoring.urls")),

    path('content/', include('apps.api.content.urls')),
    # Profile endpoints
    path("user/", include("apps.api.user.urls")),
]
