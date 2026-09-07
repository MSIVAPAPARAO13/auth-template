"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda req: redirect("login"), name="root"),
    path("", include("accounts.urls")),
]

if settings.DEBUG and hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

