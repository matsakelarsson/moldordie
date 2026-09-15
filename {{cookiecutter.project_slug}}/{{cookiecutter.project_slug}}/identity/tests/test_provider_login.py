{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Provider login from the single-page application: the ID token the provider's browser
library obtained, posted to allauth's provider-token endpoint."""

from __future__ import annotations

import copy
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from allauth.socialaccount.models import SocialAccount
from django.urls import reverse

from {{ cookiecutter.project_slug }}.identity.tests.headless import APP
from {{ cookiecutter.project_slug }}.users.models import User
from {{ cookiecutter.project_slug }}.users.tests import social
from {{ cookiecutter.project_slug }}.users.tests.social import CLAIMS
from {{ cookiecutter.project_slug }}.users.tests.social import PROVIDER
from {{ cookiecutter.project_slug }}.users.tests.social import SUBJECT_CLAIM

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db

PROVIDER_TOKEN_URL = f"{APP}/auth/provider/token"
JSON = "application/json"
CLIENT_ID = "login-registration"
{%- if entra %}
PROVIDER_KEY = "openid_connect"
{%- else %}
PROVIDER_KEY = "google"
{%- endif %}


@pytest.fixture
def login_client_id(settings) -> str:
    """The login registration's client id, which the SPA names with the token."""
    providers = copy.deepcopy(settings.SOCIALACCOUNT_PROVIDERS)
    providers[PROVIDER_KEY]["APPS"][0]["client_id"] = CLIENT_ID
    settings.SOCIALACCOUNT_PROVIDERS = providers
    return CLIENT_ID


def exchange(
    client: Client,
    claims: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    client_id: str,
):
    """Post the ID token as the SPA does; the provider answers ``claims``."""
    social.patch_provider(monkeypatch, claims)
    return client.post(
        PROVIDER_TOKEN_URL,
        {
            "provider": PROVIDER,
            "process": "login",
            "token": {"client_id": client_id, "id_token": "id"},
        },
        content_type=JSON,
    )


def test_the_id_token_signs_in_with_app_tokens(client, monkeypatch, login_client_id):
    response = exchange(client, CLAIMS, monkeypatch, login_client_id)

    assert response.status_code == HTTPStatus.OK, response.json()
    meta = response.json()["meta"]
    assert meta["is_authenticated"] is True
    assert meta["access_token"]
    assert meta["refresh_token"]
    user = User.objects.get(email="ada@example.com")
    account = SocialAccount.objects.get(user=user)
    assert (account.provider, account.uid) == (PROVIDER, CLAIMS[SUBJECT_CLAIM])


def test_the_spa_and_the_pages_share_the_account(client, monkeypatch, login_client_id):
    exchange(client, CLAIMS, monkeypatch, login_client_id)

    response = social.provider_login(client, monkeypatch, CLAIMS)

    assert response.status_code == HTTPStatus.FOUND
    assert User.objects.count() == 1
    assert SocialAccount.objects.count() == 1
    profile = client.get(reverse("users:redirect"))
    assert profile["Location"] == User.objects.get().get_absolute_url()


def test_another_client_id_is_refused(client, monkeypatch, login_client_id):
    response = exchange(client, CLAIMS, monkeypatch, "another-registration")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not User.objects.exists()
{%- if entra %}


@pytest.mark.parametrize("oid", [None, "", 123], ids=["null", "empty", "not a string"])
def test_a_token_without_a_usable_object_id_is_a_validation_error(
    client,
    monkeypatch,
    login_client_id,
    oid,
):
    claims = {**CLAIMS, "oid": oid}

    response = exchange(client, claims, monkeypatch, login_client_id)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    (error,) = response.json()["errors"]
    assert (error["code"], error["param"]) == ("invalid_token", "token")
    assert not User.objects.exists()


def test_a_token_missing_the_object_id_is_a_validation_error(
    client,
    monkeypatch,
    login_client_id,
):
    claims = {key: value for key, value in CLAIMS.items() if key != "oid"}

    response = exchange(client, claims, monkeypatch, login_client_id)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["errors"][0]["code"] == "invalid_token"
{%- endif %}
