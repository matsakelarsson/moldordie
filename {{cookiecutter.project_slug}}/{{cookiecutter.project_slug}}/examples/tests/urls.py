"""The project's URLs without the examples page, as they are once a project has
deleted it: the navigation has to do without its route."""

from config.urls import urlpatterns as project_urlpatterns

urlpatterns = [
    pattern
    for pattern in project_urlpatterns
    if getattr(pattern, "namespace", None) != "examples"
]
