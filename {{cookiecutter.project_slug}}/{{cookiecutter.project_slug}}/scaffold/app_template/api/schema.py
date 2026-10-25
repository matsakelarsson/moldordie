from django.urls import reverse
from ninja import ModelSchema

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item


class ItemSchema(ModelSchema):
    url: str

    class Meta:
        model = Item
        fields = ["id", "name", "notes", "created"]

    @staticmethod
    def resolve_url(obj: Item) -> str:
        return reverse("api:retrieve_item", kwargs={"pk": obj.pk})


class ItemInputSchema(ModelSchema):
    """What a request sends to create a record."""

    # Declared explicitly so the fields are visible to the type checker; the
    # annotations mirror what ``ModelSchema`` derives from the model.
    name: str
    notes: str = ""

    class Meta:
        model = Item
        fields = ["name", "notes"]


class ItemPatchSchema(ModelSchema):
    """What a request sends to change a record: any of its fields, the rest kept."""

    name: str | None = None
    notes: str | None = None

    class Meta:
        model = Item
        fields = ["name", "notes"]
