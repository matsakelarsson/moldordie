from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.users.models import User


def test_user_get_absolute_url(user: User):
    {%- if cookiecutter.username_type == "email" %}
    assert user.get_absolute_url() == f"/users/{user.pk}/"
    {%- else %}
    assert user.get_absolute_url() == f"/users/{user.username}/"
    {%- endif %}


def test_display_name_is_the_stripped_name():
    user = UserFactory.build(name="  Ann Lee  ")

    assert user.display_name == "Ann Lee"
{%- if cookiecutter.username_type == "email" %}


@pytest.mark.parametrize("name", ["", "   "])
def test_display_name_never_falls_back_to_the_email(name: str):
    user = UserFactory.build(email="hidden@example.com", name=name)

    assert user.display_name == "User"
{%- else %}


@pytest.mark.parametrize("name", ["", "   "])
def test_display_name_falls_back_to_the_username(name: str):
    user = UserFactory.build(username="ann", name=name)

    assert user.display_name == "ann"
{%- endif %}
