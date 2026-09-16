"""The showcase's routes, which config/urls.py registers only under DEBUG."""

from django.urls import path

from .views import PreviewView
from .views import ShowcaseView
from .views import reset_preview

app_name = "showcase"
urlpatterns = [
    path("", ShowcaseView.as_view(), name="index"),
    path("preview/", PreviewView.as_view(), name="preview"),
    path("preview/reset/", reset_preview, name="reset"),
]
