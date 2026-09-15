"""The frontend contract: where the single-page application's pages are, and what a
login may return to."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from allauth.core import context
from django.core import checks
from django.core import mail

from {{ cookiecutter.project_slug }}.identity.checks import check_frontend_url
from {{ cookiecutter.project_slug }}.identity.tests.headless import APP
from {{ cookiecutter.project_slug }}.identity.tests.headless import PASSWORD
from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user
from {{ cookiecutter.project_slug }}.users.adapters import AccountAdapter

if TYPE_CHECKING:
    from django.test import Client
    from django.test import RequestFactory

pytestmark = pytest.mark.django_db

FRONTEND = "http://localhost:5173"
JSON = "application/json"
# The five pages, with the key allauth fills in
PAGES = {
    "account_confirm_email": "/account/verify-email/{key}",
    "account_reset_password": "/account/password/reset",
    "account_reset_password_from_key": "/account/password/reset/key/{key}",
    "account_signup": "/account/signup",
    "socialaccount_login_error": "/account/provider/callback",
}


def test_the_five_pages_of_the_contract(settings):
    expected = {name: FRONTEND + path for name, path in PAGES.items()}

    assert expected == settings.HEADLESS_FRONTEND_URLS


def test_the_verification_mail_links_to_the_frontend(client: Client):
    response = client.post(
        f"{APP}/auth/signup",
        {
            {%- if cookiecutter.username_type == "username" %}
            "username": "newcomer",
            {%- endif %}
            "email": "newcomer@example.com",
            "password": PASSWORD,
        },
        content_type=JSON,
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED  # verification pending
    (message,) = mail.outbox
    assert re.search(rf"{FRONTEND}/account/verify-email/\S+", str(message.body))


def test_the_password_reset_mail_links_to_the_frontend(client: Client):
    user = create_verified_user()

    response = client.post(
        f"{APP}/auth/password/request",
        {"email": user.email},
        content_type=JSON,
    )

    assert response.status_code == HTTPStatus.OK
    (message,) = mail.outbox
    assert re.search(rf"{FRONTEND}/account/password/reset/key/\S+", str(message.body))


@pytest.mark.parametrize(
    ("url", "safe"),
    [
        (f"{FRONTEND}/account/provider/callback", True),
        (f"{FRONTEND}/account/provider/callback?next=/dashboard", True),
        ("http://LOCALHOST:5173/", True),
        # Another port, scheme or host on the same name is another origin
        ("http://localhost:9999/account/provider/callback", False),
        ("https://localhost:5173/account/provider/callback", False),
        ("http://localhost.example.com:5173/", False),
        ("http://localhost/", False),
        ("//localhost:5173/", False),
        # The backend's own origin and relative URLs keep working for the pages
        ("http://testserver/users/~redirect/", True),
        ("/users/~redirect/", True),
        ("///evil.example.com/", False),
    ],
)
def test_a_return_destination_needs_a_configured_origin(rf: RequestFactory, url, safe):
    request = rf.get("/")

    with context.request_context(request):
        assert AccountAdapter().is_safe_url(url) is safe


def test_the_frontend_url_must_be_a_configured_origin(settings):
    settings.FRONTEND_URL = "http://localhost:5173"
    settings.FRONTEND_ORIGINS = ["http://localhost:5173", "https://app.example.com"]
    assert check_frontend_url(None) == []

    settings.FRONTEND_URL = "https://app.example.com:8443"
    (message,) = check_frontend_url(None)
    assert message.id == "identity.E001"
    assert message.level == checks.ERROR
    assert "DJANGO_FRONTEND_URL" in message.msg


def test_the_frontend_check_runs_with_the_system_checks(settings):
    settings.FRONTEND_URL = "http://elsewhere.example.com"

    assert "identity.E001" in [message.id for message in checks.run_checks()]
