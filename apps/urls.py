from django.urls import include, path
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView


urlpatterns = [
    path('credits/', include('apps.credits.urls')),
    path("core/", include("apps.core.api.urls")),
    path('sms/', include('apps.notifications.urls')),
    path('users/', include('apps.users.urls')),
    path('profiles/', include('apps.accounts.urls')),
    path('flow/', include('apps.flow.api.urls')),
    path('logger/', include('apps.logger.urls')),
    path('tinymce/', include('tinymce.urls')),
]
