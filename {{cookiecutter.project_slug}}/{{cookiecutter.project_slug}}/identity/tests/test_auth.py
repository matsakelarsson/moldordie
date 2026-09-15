"""The API's user policy in ``identity/auth.py``: an app-issued JWT or the session."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from django.urls import reverse

from {{ cookiecutter.project_slug }}.identity.tests.headless import JSON
from {{ cookiecutter.project_slug }}.identity.tests.headless import bearer
from {{ cookiecutter.project_slug }}.identity.tests.headless import password_login

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

# The update the current-user route accepts
{%- if cookiecutter.username_type == "email" %}
UPDATE = '{"name": "New Name"}'
{%- else %}
UPDATE = '{"name": "New Name", "username": "renamed"}'
{%- endif %}


def test_an_app_token_calls_the_users_api(client: Client, user: User):
    meta = password_login(client, user)

    response = client.get(
        reverse("api:retrieve_current_user"),
        headers=bearer(meta["access_token"]),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["email"] == user.email


def test_an_app_token_needs_no_csrf_token(user: User):
    client = Client(enforce_csrf_checks=True)
    meta = password_login(client, user)

    response = client.patch(
        reverse("api:update_current_user"),
        UPDATE,
        content_type=JSON,
        headers=bearer(meta["access_token"]),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "New Name"


@pytest.mark.parametrize(
    "authorization",
    ["", "Bearer", "Bearer not-a-token", "Basic dXNlcjpwYXNz"],
    ids=["empty", "scheme only", "malformed", "another scheme"],
)
def test_a_bad_header_is_refused_beside_a_valid_session(
    client: Client,
    user: User,
    authorization: str,
):
    """Any Authorization header is a token attempt: a failure never falls through."""
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_current_user"),
        headers={"Authorization": authorization},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_an_expired_token_is_refused_beside_a_valid_session(
    settings,
    client: Client,
    user: User,
):
    settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = -60
    expired = password_login(client, user)["access_token"]
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_current_user"),
        headers=bearer(expired),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_the_session_authenticates_without_a_header(client: Client, user: User):
    client.force_login(user)

    response = client.get(reverse("api:retrieve_current_user"))

    assert response.status_code == HTTPStatus.OK
    assert response.json()["email"] == user.email


def test_no_credentials_is_refused(client: Client):
    response = client.get(reverse("api:retrieve_current_user"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_a_session_request_on_an_unsafe_method_keeps_the_csrf_check(user: User):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get(reverse("home"))  # sets the CSRF cookie

    refused = client.patch(
        reverse("api:update_current_user"),
        UPDATE,
        content_type=JSON,
    )
    accepted = client.patch(
        reverse("api:update_current_user"),
        UPDATE,
        content_type=JSON,
        headers={"X-CSRFToken": client.cookies["csrftoken"].value},
    )

    assert refused.status_code == HTTPStatus.FORBIDDEN
    assert accepted.status_code == HTTPStatus.OK


def test_the_openapi_schema_declares_the_bearer_scheme(admin_client: Client):
    schema = admin_client.get(reverse("api:openapi-json")).json()

    assert schema["components"]["securitySchemes"]["UserAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    current_user = schema["paths"]["/api/users/~me/"]["get"]
    assert current_user["security"] == [{"UserAuth": []}]
