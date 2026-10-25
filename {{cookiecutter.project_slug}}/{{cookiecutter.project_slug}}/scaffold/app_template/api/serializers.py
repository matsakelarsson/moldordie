from rest_framework import serializers

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item


class ItemSerializer(serializers.ModelSerializer[Item]):
    class Meta:
        model = Item
        fields = ["id", "name", "notes", "created", "url"]
        extra_kwargs = {"url": {"view_name": "api:item-detail"}}
