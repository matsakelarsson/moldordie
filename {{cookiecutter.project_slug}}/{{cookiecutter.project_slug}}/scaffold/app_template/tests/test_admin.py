"""The model in the admin: its list, its search and its form."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.scaffold.app_template.tests.factories import ItemFactory

pytestmark = pytest.mark.django_db


def test_the_list_shows_and_searches_the_records(admin_client):
    ItemFactory.create(name="Apple")
    ItemFactory.create(name="Pear")
    url = reverse("admin:app_template_item_changelist")

    whole = admin_client.get(url).content.decode()
    searched = admin_client.get(url, {"q": "pea"}).content.decode()

    assert "Apple" in whole
    assert "Pear" in searched
    assert "Apple" not in searched


def test_a_record_is_added(admin_client):
    url = reverse("admin:app_template_item_add")

    assert admin_client.get(url).status_code == HTTPStatus.OK
    response = admin_client.post(url, {"name": "Apple", "notes": ""})

    assert response.status_code == HTTPStatus.FOUND
    assert Item.objects.get().name == "Apple"
