from django.urls import path

from .views import ItemCreateView
from .views import ItemDeleteView
from .views import ItemDetailView
from .views import ItemListView
from .views import ItemUpdateView

app_name = "app_template"
urlpatterns = [
    path("", view=ItemListView.as_view(), name="list"),
    path("new/", view=ItemCreateView.as_view(), name="create"),
    path("<int:pk>/", view=ItemDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", view=ItemUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", view=ItemDeleteView.as_view(), name="delete"),
]
