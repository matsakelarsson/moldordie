from django.urls import path

from .views import ExampleFormView
from .views import ExamplesView
from .views import ModalView
from .views import NoticesView
from .views import TabsView
from .views import ToggleView

app_name = "examples"
urlpatterns = [
    path("", view=ExamplesView.as_view(), name="index"),
    path("form/", view=ExampleFormView.as_view(), name="form"),
    path("toggle/", view=ToggleView.as_view(), name="toggle"),
    path("tabs/", view=TabsView.as_view(), name="tabs"),
    path("modal/", view=ModalView.as_view(), name="modal"),
    path("notices/", view=NoticesView.as_view(), name="notices"),
]
