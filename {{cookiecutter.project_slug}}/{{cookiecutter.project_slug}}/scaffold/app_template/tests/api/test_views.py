{% if cookiecutter.rest_api == 'DRF' -%}
"""The records over the REST API: listed, created, changed and deleted by a signed-in
user."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.scaffold.app_template.tests.factories import ItemFactory

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db

JSON = "application/json"


def detail_url(item: Item) -> str:
    return reverse("api:item-detail", kwargs={"pk": item.pk})


def test_the_api_needs_a_signed_in_user(client: Client):
    response = client.get(reverse("api:item-list"))

    # Session authentication comes first, and it names no scheme to challenge with
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_records_are_listed(signed_in: Client):
    item = ItemFactory.create(name="Apple")

    response = signed_in.get(reverse("api:item-list"))

    assert response.status_code == HTTPStatus.OK
    (listed,) = response.json()
    assert listed["name"] == "Apple"
    assert listed["url"] == f"http://testserver{detail_url(item)}"


def test_a_record_is_created(signed_in: Client):
    data = {"name": "Apple"}

    response = signed_in.post(reverse("api:item-list"), data, content_type=JSON)

    assert response.status_code == HTTPStatus.CREATED, response.json()
    assert Item.objects.get().name == "Apple"


def test_a_record_is_changed(signed_in: Client):
    item = ItemFactory.create(name="Apple")
    data = {"notes": "Ripe"}

    response = signed_in.patch(detail_url(item), data, content_type=JSON)

    assert response.status_code == HTTPStatus.OK, response.json()
    item.refresh_from_db()
    assert (item.name, item.notes) == ("Apple", "Ripe")


def test_a_record_is_deleted(signed_in: Client):
    item = ItemFactory.create()

    response = signed_in.delete(detail_url(item))

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not Item.objects.filter(pk=item.pk).exists()


def test_a_missing_record_is_not_found(signed_in: Client):
    url = reverse("api:item-detail", kwargs={"pk": 0})

    assert signed_in.get(url).status_code == HTTPStatus.NOT_FOUND
{%- elif cookiecutter.rest_api == 'Django Ninja' -%}
"""The records over the REST API: listed, created, changed and deleted by a signed-in
user."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.scaffold.app_template.tests.factories import ItemFactory

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db

JSON = "application/json"


def detail_url(item: Item) -> str:
    return reverse("api:retrieve_item", kwargs={"pk": item.pk})


def test_the_api_needs_a_signed_in_user(client: Client):
    response = client.get(reverse("api:list_items"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_the_records_are_listed(signed_in: Client):
    item = ItemFactory.create(name="Apple")

    response = signed_in.get(reverse("api:list_items"))

    assert response.status_code == HTTPStatus.OK
    (listed,) = response.json()
    assert listed["name"] == "Apple"
    assert listed["url"] == detail_url(item)


def test_a_record_is_created(signed_in: Client):
    url = reverse("api:create_item")

    response = signed_in.post(url, '{"name": "Apple"}', content_type=JSON)

    assert response.status_code == HTTPStatus.CREATED, response.json()
    assert Item.objects.get().name == "Apple"


def test_a_record_is_changed(signed_in: Client):
    item = ItemFactory.create(name="Apple")
    url = reverse("api:update_item", kwargs={"pk": item.pk})

    response = signed_in.patch(url, '{"notes": "Ripe"}', content_type=JSON)

    assert response.status_code == HTTPStatus.OK, response.json()
    item.refresh_from_db()
    assert (item.name, item.notes) == ("Apple", "Ripe")


def test_a_null_leaves_a_field_as_it_is(signed_in: Client):
    item = ItemFactory.create(name="Apple")
    url = reverse("api:update_item", kwargs={"pk": item.pk})
    data = '{"name": null, "notes": "Ripe"}'

    response = signed_in.patch(url, data, content_type=JSON)

    assert response.status_code == HTTPStatus.OK, response.json()
    item.refresh_from_db()
    assert (item.name, item.notes) == ("Apple", "Ripe")


def test_a_record_is_deleted(signed_in: Client):
    item = ItemFactory.create()
    url = reverse("api:delete_item", kwargs={"pk": item.pk})

    response = signed_in.delete(url)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not Item.objects.filter(pk=item.pk).exists()


def test_a_missing_record_is_not_found(signed_in: Client):
    url = reverse("api:retrieve_item", kwargs={"pk": 0})

    assert signed_in.get(url).status_code == HTTPStatus.NOT_FOUND
{%- endif %}
