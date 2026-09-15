{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Sign-in through {% if entra %}Microsoft Entra ID{% else %}Google{% endif %} through allauth's server-rendered callback.

The provider is never contacted: the code exchange and the cryptographic verification of
the ID token are patched, so that the claims below reach allauth as if decoded from a
valid token, and the provider's claim extraction and the adapter hooks run as they do in
production.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.internal import jwtkit
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
{%- if entra %}
from allauth.socialaccount.providers.openid_connect.views import (
    OpenIDConnectOAuth2Adapter,
)
{%- endif %}
from django.core import mail
from django.urls import reverse

from {{ cookiecutter.project_slug }}.users.models import User
from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpResponseBase
    from django.test import Client

pytestmark = pytest.mark.django_db
{%- if entra %}

PROVIDER = "entra"
# The account is keyed by the object id, not the pairwise subject
SUBJECT_CLAIM = "oid"
CLAIMS = {
    "oid": "5a5b0f5e-3b0b-4c7e-9a1f-2f3d4e5f6a7b",
    "sub": "AAAAAAAAAAAAAAAAAAAAAG3yn4aQ7Yq2p8v1mX5UeHo",
    "tid": "72f988bf-86f1-41af-91ab-2d7cd011db47",
    "name": "Ada Lovelace",
    "preferred_username": "ada@example.com",
    "email": "ada@example.com",
}
OPENID_CONFIGURATION = {
    "issuer": "https://login.microsoftonline.com/tenant/v2.0",
    "authorization_endpoint": "https://login.microsoftonline.com/tenant/oauth2/v2.0/authorize",
    "token_endpoint": "https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
    "userinfo_endpoint": "https://graph.microsoft.com/oidc/userinfo",
    "jwks_uri": "https://login.microsoftonline.com/tenant/discovery/v2.0/keys",
}
{%- else %}

PROVIDER = "google"
SUBJECT_CLAIM = "sub"
CLAIMS = {
    "sub": "110248495921238986420",
    "name": "Ada Lovelace",
    "given_name": "Ada",
    "family_name": "Lovelace",
    "email": "ada@example.com",
    "email_verified": True,
}
{%- endif %}


def refuse_userinfo(*args: object, **kwargs: object) -> dict[str, object]:
    msg = "UserInfo must not be fetched: its answer would lack the account's id"
    raise AssertionError(msg)


@pytest.fixture
def provider_login(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, object]], HttpResponseBase]:
    """Sign in through the provider as if it had answered with the given claims.

    Starts the login as the login page's button does, then drives the callback with an
    authorization code.
    """
    {%- if entra %}
    login_url = reverse("openid_connect_login", kwargs={"provider_id": PROVIDER})
    callback_url = reverse("openid_connect_callback", kwargs={"provider_id": PROVIDER})
    monkeypatch.setattr(
        OpenIDConnectOAuth2Adapter,
        "openid_config",
        OPENID_CONFIGURATION,
    )
    monkeypatch.setattr(OpenIDConnectOAuth2Adapter, "_fetch_user_info", refuse_userinfo)
    {%- else %}
    login_url = reverse("google_login")
    callback_url = reverse("google_callback")
    {%- endif %}
    monkeypatch.setattr(
        OAuth2Client,
        "get_access_token",
        lambda *args, **kwargs: {"access_token": "access", "id_token": "id"},
    )

    def login(claims: dict[str, object]) -> HttpResponseBase:
        monkeypatch.setattr(jwtkit, "verify_and_decode", lambda **kwargs: claims)
        started = client.post(login_url, {"process": "login"})
        assert started.status_code == HTTPStatus.FOUND
        state = parse_qs(urlsplit(started["Location"]).query)["state"][0]
        return client.get(callback_url, {"code": "authorization-code", "state": state})

    return login


def test_the_login_page_offers_the_provider(client: Client):
    response = client.get(reverse("account_login"))

    assert response.status_code == HTTPStatus.OK
    {%- if entra %}
    assert b"Microsoft Entra ID" in response.content
    assert (
        reverse("openid_connect_login", kwargs={"provider_id": PROVIDER}).encode()
        in response.content
    )
    {%- else %}
    assert b"Google" in response.content
    assert reverse("google_login").encode() in response.content
    {%- endif %}


def test_the_first_login_creates_the_account_from_the_claims(provider_login):
    response = provider_login(CLAIMS)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == reverse("users:redirect")
    user = User.objects.get(email="ada@example.com")
    assert user.name == "Ada Lovelace"
    assert not user.has_usable_password()
    account = SocialAccount.objects.get(user=user)
    assert (account.provider, account.uid) == (PROVIDER, CLAIMS[SUBJECT_CLAIM])
    assert response.wsgi_request.user == user


def test_a_verified_address_needs_no_verification_mail(provider_login):
    {%- if entra %}
    """The tenant's address is trusted: Entra's tokens carry no verified flag."""
    {%- else %}
    """Google says the address is verified, so no mail is sent."""
    {%- endif %}
    provider_login(CLAIMS)

    assert EmailAddress.objects.get(email="ada@example.com").verified is True
    assert mail.outbox == []
{%- if not entra %}


def test_an_unverified_address_is_verified_by_mail(provider_login):
    response = provider_login({**CLAIMS, "email_verified": False})

    assert response["Location"] == reverse("account_email_verification_sent")
    assert EmailAddress.objects.get(email="ada@example.com").verified is False
    assert len(mail.outbox) == 1
    assert not response.wsgi_request.user.is_authenticated
{%- endif %}


def test_a_returning_user_gets_the_same_account(client: Client, provider_login):
    provider_login(CLAIMS)
    client.logout()

    response = provider_login({**CLAIMS, "name": "Ada King"})

    assert response.wsgi_request.user == User.objects.get()
    assert SocialAccount.objects.count() == 1


def test_a_login_without_an_email_claim_collects_one(provider_login):
    claims = {key: value for key, value in CLAIMS.items() if key != "email"}
    response = provider_login(claims)

    assert response["Location"] == reverse("socialaccount_signup")
    assert not User.objects.exists()


def test_an_existing_account_with_the_address_is_not_linked(provider_login):
    """Linking stays explicit: a provider claim does not sign in to a local account."""
    existing = UserFactory.create(email="ada@example.com")

    response = provider_login(CLAIMS)

    assert not response.wsgi_request.user.is_authenticated
    assert not SocialAccount.objects.filter(user=existing).exists()


def test_signup_follows_the_registration_setting(settings, provider_login):
    settings.ACCOUNT_ALLOW_REGISTRATION = False

    response = provider_login(CLAIMS)

    assert response.status_code == HTTPStatus.OK
    assert not response.wsgi_request.user.is_authenticated
    assert not User.objects.exists()
