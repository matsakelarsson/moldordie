from django.urls import path

from .views import theme_stylesheet

app_name = "ui"
urlpatterns = [
    path("theme.css", theme_stylesheet, name="theme"),
]
