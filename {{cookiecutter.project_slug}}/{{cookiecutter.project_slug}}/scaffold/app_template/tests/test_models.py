"""The model: how a record is shown and addressed, and the order of the records."""

import pytest
from django.urls import resolve

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.scaffold.app_template.tests.factories import ItemFactory


def test_a_record_is_shown_by_its_name():
    item = ItemFactory.build(name="Apple")

    assert str(item) == "Apple"


@pytest.mark.django_db
def test_a_record_is_addressed_by_its_key():
    item = ItemFactory.create()

    match = resolve(item.get_absolute_url())

    assert match.view_name == "app_template:detail"
    assert match.kwargs == {"pk": item.pk}


@pytest.mark.django_db
def test_the_newest_record_comes_first():
    older = ItemFactory.create()
    newer = ItemFactory.create()

    assert list(Item.objects.all()) == [newer, older]
