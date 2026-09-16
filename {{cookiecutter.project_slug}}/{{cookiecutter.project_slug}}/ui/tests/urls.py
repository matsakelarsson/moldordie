"""The project's URLs with the showcase, which config/urls.py registers only under
DEBUG, so that the showcase's tests reach it with DEBUG off."""

from django.urls import include
from django.urls import path

from config.urls import urlpatterns as project_urlpatterns

urlpatterns = [
    *project_urlpatterns,
    path(
        "ui/components/",
        include("{{ cookiecutter.project_slug }}.ui.showcase_urls", namespace="showcase"),
    ),
]
