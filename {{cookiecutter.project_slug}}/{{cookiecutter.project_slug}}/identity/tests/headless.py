"""Driving allauth's headless API as the single-page application does."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

from allauth.account.models import EmailAddress

from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

# The app client's endpoints: JWTs in the answers, no cookies
APP = "/_allauth/app/v1"
LOGIN_URL = f"{APP}/auth/login"
SESSION_URL = f"{APP}/auth/session"
REFRESH_URL = f"{APP}/tokens/refresh"
MFA_AUTHENTICATE_URL = f"{APP}/auth/2fa/authenticate"
PASSWORD = "correct horse battery staple"  # noqa: S105 - a test user's password


def create_verified_user(**fields: Any) -> User:
    """A user who can sign in: the password is known and the address verified."""
    user = UserFactory.create(password=PASSWORD, **fields)
    EmailAddress.objects.create(
        user=user,
        email=user.email,
        verified=True,
        primary=True,
    )
    return user


def credentials(user: User) -> dict[str, str]:
    """The login input: the login method the project uses, and the password."""
    {%- if cookiecutter.username_type == "email" %}
    return {"email": user.email, "password": PASSWORD}
    {%- else %}
    return {"username": user.username, "password": PASSWORD}
    {%- endif %}


def password_login(client: Client, user: User) -> dict[str, Any]:
    """Sign in as ``user`` through the app client; the answer's tokens."""
    response = client.post(
        LOGIN_URL,
        credentials(user),
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.OK, response.json()
    meta: dict[str, Any] = response.json()["meta"]
    return meta
