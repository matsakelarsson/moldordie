"""The single-page application's login: app-issued JWTs from allauth's headless API."""

from __future__ import annotations

import time
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from allauth.mfa import app_settings as mfa_settings
from allauth.mfa.totp.internal.auth import TOTP
from allauth.mfa.totp.internal.auth import format_hotp_value
from allauth.mfa.totp.internal.auth import hotp_value

from {{ cookiecutter.project_slug }}.identity.tests.headless import LOGIN_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import MFA_AUTHENTICATE_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import REFRESH_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import SESSION_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user
from {{ cookiecutter.project_slug }}.identity.tests.headless import credentials
from {{ cookiecutter.project_slug }}.identity.tests.headless import password_login

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # noqa: S105 - a test authenticator's secret
JSON = "application/json"


@pytest.fixture
def user() -> User:
    return create_verified_user()


def totp_code() -> str:
    counter = int(time.time()) // mfa_settings.TOTP_PERIOD
    code: str = format_hotp_value(hotp_value(TOTP_SECRET, counter))
    return code


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_a_password_login_returns_both_tokens(client: Client, user: User):
    meta = password_login(client, user)

    assert meta["is_authenticated"] is True
    assert meta["access_token"]
    assert meta["refresh_token"]
    # The app client keeps no cookie: the tokens are the credentials
    assert not client.cookies


def test_a_wrong_password_is_refused(client: Client, user: User):
    wrong = {**credentials(user), "password": "wrong"}

    response = client.post(LOGIN_URL, wrong, content_type=JSON)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "access_token" not in response.json().get("meta", {})


def test_the_access_token_authenticates(client: Client, user: User):
    meta = password_login(client, user)

    response = client.get(SESSION_URL, headers=bearer(meta["access_token"]))

    assert response.status_code == HTTPStatus.OK
    assert response.json()["data"]["user"]["id"] == user.pk


def test_a_second_factor_is_a_pending_stage_first(client: Client, user: User):
    TOTP.activate(user, TOTP_SECRET)

    response = client.post(LOGIN_URL, credentials(user), content_type=JSON)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    body = response.json()
    assert "access_token" not in body["meta"]
    pending = [flow for flow in body["data"]["flows"] if flow.get("is_pending")]
    assert pending == [
        {"id": "mfa_authenticate", "is_pending": True, "types": ["totp"]},
    ]

    # The pending login lives in a session the app client carries as a token
    completed = client.post(
        MFA_AUTHENTICATE_URL,
        {"code": totp_code()},
        content_type=JSON,
        headers={"X-Session-Token": body["meta"]["session_token"]},
    )

    assert completed.status_code == HTTPStatus.OK
    assert completed.json()["meta"]["access_token"]
    assert completed.json()["meta"]["refresh_token"]


def test_a_refresh_rotates_the_refresh_token(client: Client, user: User):
    meta = password_login(client, user)
    refresh = {"refresh_token": meta["refresh_token"]}

    refreshed = client.post(REFRESH_URL, refresh, content_type=JSON)

    assert refreshed.status_code == HTTPStatus.OK
    tokens = refreshed.json()["data"]
    assert tokens["access_token"] != meta["access_token"]
    assert tokens["refresh_token"] != meta["refresh_token"]

    reused = client.post(REFRESH_URL, refresh, content_type=JSON)

    assert reused.status_code == HTTPStatus.BAD_REQUEST


def test_a_logout_invalidates_the_access_token(client: Client, user: User):
    meta = password_login(client, user)
    headers = bearer(meta["access_token"])

    logged_out = client.delete(SESSION_URL, headers=headers)

    assert logged_out.status_code == HTTPStatus.UNAUTHORIZED
    afterwards = client.get(SESSION_URL, headers=headers)
    assert afterwards.status_code == HTTPStatus.UNAUTHORIZED


def test_a_configured_frontend_origin_may_call_the_api(client: Client):
    """A preflight from the SPA: the origin is allowed, X-Session-Token may be sent."""
    response = client.options(
        LOGIN_URL,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-session-token",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "x-session-token" in response["Access-Control-Allow-Headers"].lower()


def test_an_unconfigured_origin_gets_no_cors_headers(client: Client):
    response = client.options(
        LOGIN_URL,
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "Access-Control-Allow-Origin" not in response
