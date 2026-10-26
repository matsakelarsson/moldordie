from factory import Sequence
from factory.django import DjangoModelFactory

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item


class ItemFactory(DjangoModelFactory[Item]):
    name = Sequence(lambda n: f"Item {n}")

    class Meta:
        model = Item
