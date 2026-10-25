{% if cookiecutter.rest_api == 'DRF' -%}
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db


def serialized(user: User) -> dict[str, str]:
    """``user`` as the API presents it, the URL absolute as the serializer builds it."""
    return {
        {%- if cookiecutter.username_type == "email" %}
        "name": user.name,
        "url": f"http://testserver/api/users/{user.pk}/",
        {%- else %}
        "username": user.username,
        "name": user.name,
        "url": f"http://testserver/api/users/{user.username}/",
        {%- endif %}
    }


def detail_url(user: User) -> str:
    {%- if cookiecutter.username_type == "email" %}
    return reverse("api:user-detail", kwargs={"pk": user.pk})
    {%- else %}
    return reverse("api:user-detail", kwargs={"username": user.username})
    {%- endif %}


def test_list_users_as_anonymous_user(client: Client):
    response = client.get(reverse("api:user-list"))

    # Session authentication comes first, and it names no scheme to challenge with
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_list_users_as_authenticated_user(client: Client, user: User):
    client.force_login(user)
    # Another user, excluded from the response
    UserFactory.create()

    response = client.get(reverse("api:user-list"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [serialized(user)]


def test_retrieve_current_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(reverse("api:user-me"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == serialized(user)


def test_retrieve_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(detail_url(user))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == serialized(user)
{%- if cookiecutter.username_type == "username" %}


def test_retrieve_a_user_named_me(client: Client):
    user = UserFactory.create(username="me")
    client.force_login(user)

    response = client.get("/api/users/me/")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == serialized(user)
{%- endif %}


def test_retrieve_another_user(client: Client, user: User):
    client.force_login(user)
    user_2 = UserFactory.create()

    response = client.get(detail_url(user_2))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "No User matches the given query."}


def test_update_current_user(client: Client):
    user = UserFactory.create(name="Old")
    client.force_login(user)

    response = client.patch(
        detail_url(user),
        data={"name": "New Name"},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json()["name"] == "New Name"
    user.refresh_from_db()
    assert user.name == "New Name"
{%- elif cookiecutter.rest_api == 'Django Ninja' -%}
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db


def test_list_users_as_anonymous_user(client: Client):
    response = client.get(reverse("api:list_users"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_list_users_as_authenticated_user(client: Client, user: User):
    client.force_login(user)
    # Another user, excluded from the response
    UserFactory.create()

    response = client.get(reverse("api:list_users"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {
            "email": user.email,
            "name": user.name,
            {%- if cookiecutter.username_type == "email" %}
            "url": f"/api/users/{user.pk}/",
            {%- else %}
            "url": f"/api/users/{user.username}/",
            "username": user.username,
            {%- endif %}
        },
    ]
{%- if cookiecutter.username_type == "email" %}


def test_retrieve_current_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_current_user"),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "email": user.email,
        "name": user.name,
        "url": f"/api/users/{user.pk}/",
    }


def test_retrieve_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_user", kwargs={"pk": user.pk}),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "email": user.email,
        "name": user.name,
        "url": f"/api/users/{user.pk}/",
    }
{%- else %}


def test_retrieve_current_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_current_user"),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "email": user.email,
        "name": user.name,
        "url": f"/api/users/{user.username}/",
        "username": user.username,
    }


def test_retrieve_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_user", kwargs={"username": user.username}),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "email": user.email,
        "name": user.name,
        "url": f"/api/users/{user.username}/",
        "username": user.username,
    }


def test_retrieve_a_user_named_me(client: Client):
    user = UserFactory.create(username="me")
    client.force_login(user)

    response = client.get("/api/users/me/")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["username"] == "me"
    assert response.json()["url"] == "/api/users/me/"
{%- endif %}


def test_retrieve_another_user(client: Client, user: User):
    client.force_login(user)
    user_2 = UserFactory.create()

    response = client.get(
        {%- if cookiecutter.username_type == "email" %}
        reverse("api:retrieve_user", kwargs={"pk": user_2.pk}),
        {%- else %}
        reverse("api:retrieve_user", kwargs={"username": user_2.username}),
        {%- endif %}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Not Found"}


def test_update_current_user(client: Client):
    user = UserFactory.create(name="Old")
    client.force_login(user)

    response = client.patch(
        reverse("api:update_current_user"),
        {%- if cookiecutter.username_type == "email" %}
        data='{"name": "New Name"}',
        {%- else %}
        data='{"name": "New Name", "username": "old"}',
        {%- endif %}
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == {
        "email": user.email,
        "name": "New Name",
        {%- if cookiecutter.username_type == "email" %}
        "url": f"/api/users/{user.pk}/",
        {%- else %}
        "username": "old",
        "url": "/api/users/old/",
        {%- endif %}
    }


{%- if cookiecutter.username_type == "email" %}


def test_update_user(client: Client):
    user = UserFactory.create(name="Old")
    client.force_login(user)

    response = client.patch(
        reverse("api:update_user", kwargs={"pk": user.pk}),
        data='{"name": "New Name"}',
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == {
        "email": user.email,
        "name": "New Name",
        "url": f"/api/users/{user.pk}/",
    }
{%- else %}


def test_update_user(client: Client):
    user = UserFactory.create(name="Old", username="old")
    client.force_login(user)

    response = client.patch(
        reverse("api:update_user", kwargs={"username": "old"}),
        data='{"name": "New Name", "username": "old"}',
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == {
        "email": user.email,
        "name": "New Name",
        "url": "/api/users/old/",
        "username": "old",
    }
{%- endif %}
{%- endif %}
