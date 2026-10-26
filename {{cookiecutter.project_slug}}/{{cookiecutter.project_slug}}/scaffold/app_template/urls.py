from django.urls import path

from {{ cookiecutter.project_slug }}.scaffold.app_template.views import ItemCreateView
from {{ cookiecutter.project_slug }}.scaffold.app_template.views import ItemDeleteView
from {{ cookiecutter.project_slug }}.scaffold.app_template.views import ItemDetailView
from {{ cookiecutter.project_slug }}.scaffold.app_template.views import ItemListView
from {{ cookiecutter.project_slug }}.scaffold.app_template.views import ItemUpdateView

app_name = "app_template"
urlpatterns = [
    path("", view=ItemListView.as_view(), name="list"),
    path("new/", view=ItemCreateView.as_view(), name="create"),
    path("<int:pk>/", view=ItemDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", view=ItemUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", view=ItemDeleteView.as_view(), name="delete"),
]
