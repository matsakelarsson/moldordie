{% if cookiecutter.rest_api == 'DRF' -%}
from rest_framework.viewsets import ModelViewSet

from {{ cookiecutter.project_slug }}.scaffold.app_template.api.serializers import ItemSerializer
from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.typedefs import AuthenticatedApiRequest


class ItemViewSet(ModelViewSet[Item]):
    serializer_class = ItemSerializer
    queryset = Item.objects.all()
    # ``IsAuthenticated`` is the default permission class (config/settings/base.py).
    request: AuthenticatedApiRequest
{%- elif cookiecutter.rest_api == 'Django Ninja' -%}
# Annotations stay evaluated at runtime (no ``from __future__ import annotations``)
# because django-ninja reads them to build the OpenAPI schema and validate input.
from http import HTTPStatus

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja import Status

from {{ cookiecutter.project_slug }}.scaffold.app_template.api.schema import ItemInputSchema
from {{ cookiecutter.project_slug }}.scaffold.app_template.api.schema import ItemPatchSchema
from {{ cookiecutter.project_slug }}.scaffold.app_template.api.schema import ItemSchema
from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.typedefs import AuthenticatedHttpRequest

router = Router(tags=["items"])


@router.get("/", response=list[ItemSchema])
def list_items(request: AuthenticatedHttpRequest) -> QuerySet[Item]:
    return Item.objects.all()


@router.post("/", response={HTTPStatus.CREATED: ItemSchema})
def create_item(
    request: AuthenticatedHttpRequest,
    data: ItemInputSchema,
) -> Status[Item]:
    return Status(HTTPStatus.CREATED, Item.objects.create(**data.dict()))


@router.get("/{pk}/", response=ItemSchema)
def retrieve_item(request: AuthenticatedHttpRequest, pk: int) -> Item:
    return get_object_or_404(Item, pk=pk)


@router.patch("/{pk}/", response=ItemSchema)
def update_item(
    request: AuthenticatedHttpRequest,
    pk: int,
    data: ItemPatchSchema,
) -> Item:
    item = get_object_or_404(Item, pk=pk)
    # A null leaves the field as it is: none of them is nullable
    for field, value in data.dict(exclude_unset=True, exclude_none=True).items():
        setattr(item, field, value)
    item.save()
    return item


@router.delete("/{pk}/", response={HTTPStatus.NO_CONTENT: None})
def delete_item(request: AuthenticatedHttpRequest, pk: int) -> Status[None]:
    get_object_or_404(Item, pk=pk).delete()
    return Status(HTTPStatus.NO_CONTENT, None)
{%- endif %}
