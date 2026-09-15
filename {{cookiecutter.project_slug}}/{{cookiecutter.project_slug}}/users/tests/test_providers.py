"""The Entra provider in ``users/providers.py``: a token needs a usable object id."""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from allauth.socialaccount.adapter import get_adapter
from django.core.exceptions import ValidationError

from {{ cookiecutter.project_slug }}.users.adapters import SocialAccountAdapter
from {{ cookiecutter.project_slug }}.users.models import User
from {{ cookiecutter.project_slug }}.users.providers import EntraProvider
from {{ cookiecutter.project_slug }}.users.tests import social
from {{ cookiecutter.project_slug }}.users.tests.social import CLAIMS
from {{ cookiecutter.project_slug }}.users.tests.social import PROVIDER

if TYPE_CHECKING:
    from django.test import Client
    from django.test import RequestFactory

pytestmark = pytest.mark.django_db

MISSING = object()
# The forms of oid a token is refused for, and the claims that carry each
BAD_OIDS = pytest.mark.parametrize(
    "oid",
    [MISSING, None, "", 123],
    ids=["missing", "null", "empty", "not a string"],
)


def claims_with_oid(oid: object) -> dict[str, object]:
    claims = {key: value for key, value in CLAIMS.items() if key != "oid"}
    if oid is not MISSING:
        claims["oid"] = oid
    return claims


@pytest.fixture
def provider_login(client: Client, monkeypatch: pytest.MonkeyPatch):
    return partial(social.provider_login, client, monkeypatch)


@pytest.fixture
def provider(rf: RequestFactory) -> EntraProvider:
    """The provider as the adapter hands it out for the Entra app."""
    provider = get_adapter().get_provider(rf.get("/"), PROVIDER)
    assert isinstance(provider, EntraProvider)
    return provider


def test_the_adapter_hands_out_the_subclass_for_the_entra_app(rf: RequestFactory):
    request = rf.get("/")

    by_app = SocialAccountAdapter().get_provider(request, PROVIDER)
    by_provider = SocialAccountAdapter().get_provider(request, "openid_connect")

    assert type(by_app) is EntraProvider
    assert type(by_provider) is EntraProvider
    assert by_app.app.provider_id == PROVIDER


@BAD_OIDS
def test_the_callback_answers_with_the_authentication_error(provider_login, oid):
    response = provider_login(claims_with_oid(oid))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert b"Third-Party Login Failure" in response.content
    assert not User.objects.exists()


@BAD_OIDS
def test_verify_token_raises_the_invalid_token_error(rf, monkeypatch, provider, oid):
    """The headless token endpoint catches validation errors and nothing else."""
    social.patch_provider(monkeypatch, claims_with_oid(oid))

    with pytest.raises(ValidationError) as excinfo:
        provider.verify_token(rf.get("/"), {"id_token": "id"})

    assert excinfo.value.code == "invalid_token"
    assert not User.objects.exists()


def test_a_valid_token_resolves_to_the_account_keyed_by_the_object_id(
    rf,
    monkeypatch,
    provider,
):
    social.patch_provider(monkeypatch, CLAIMS)

    login = provider.verify_token(rf.get("/"), {"id_token": "id"})

    assert (login.account.provider, login.account.uid) == (PROVIDER, CLAIMS["oid"])
    assert login.user.email == "ada@example.com"


def test_the_callback_resolves_to_the_account_keyed_by_the_object_id(provider_login):
    """UserInfo is not fetched on the way: the driver refuses the request."""
    response = provider_login(CLAIMS)

    assert response.status_code == HTTPStatus.FOUND
    account = response.wsgi_request.user.socialaccount_set.get()
    assert (account.provider, account.uid) == (PROVIDER, CLAIMS["oid"])
