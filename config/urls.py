"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda req: redirect("login"), name="root"),
    path("", include("accounts.urls")),
]
