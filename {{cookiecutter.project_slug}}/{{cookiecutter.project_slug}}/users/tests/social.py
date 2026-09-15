{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Sign-in through {% if entra %}Microsoft Entra ID{% else %}Google{% endif %} without contacting it.

``provider_login`` starts the login as the login page's button does and drives
allauth's callback with an authorization code. The code exchange and the cryptographic
verification of the ID token are patched, so that the given claims reach allauth as if
decoded from a valid token, and the provider's claim extraction and the adapter hooks
run as they do in production.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import urlsplit

from allauth.socialaccount.internal import jwtkit
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
{%- if entra %}
from allauth.socialaccount.providers.openid_connect.views import (
    OpenIDConnectOAuth2Adapter,
)
{%- endif %}
from django.urls import reverse

if TYPE_CHECKING:
    import pytest
    from django.http import HttpResponseBase
    from django.test import Client
{%- if entra %}

PROVIDER = "entra"
# The account is keyed by the object id, not the pairwise subject
SUBJECT_CLAIM = "oid"
CLAIMS: dict[str, object] = {
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
CLAIMS: dict[str, object] = {
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


def patch_provider(monkeypatch: pytest.MonkeyPatch, claims: dict[str, object]) -> None:
    """Make the provider's token exchange and verification answer with ``claims``."""
    {%- if entra %}
    monkeypatch.setattr(
        OpenIDConnectOAuth2Adapter,
        "openid_config",
        OPENID_CONFIGURATION,
    )
    monkeypatch.setattr(OpenIDConnectOAuth2Adapter, "_fetch_user_info", refuse_userinfo)
    {%- endif %}
    monkeypatch.setattr(
        OAuth2Client,
        "get_access_token",
        lambda *args, **kwargs: {"access_token": "access", "id_token": "id"},
    )
    monkeypatch.setattr(jwtkit, "verify_and_decode", lambda **kwargs: claims)


def provider_login(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> HttpResponseBase:
    """Sign in through the provider as if it had answered with ``claims``."""
    {%- if entra %}
    login_url = reverse("openid_connect_login", kwargs={"provider_id": PROVIDER})
    callback_url = reverse("openid_connect_callback", kwargs={"provider_id": PROVIDER})
    {%- else %}
    login_url = reverse("google_login")
    callback_url = reverse("google_callback")
    {%- endif %}
    patch_provider(monkeypatch, claims)
    started = client.post(login_url, {"process": "login"})
    assert started.status_code == HTTPStatus.FOUND
    state = parse_qs(urlsplit(started["Location"]).query)["state"][0]
    return client.get(callback_url, {"code": "authorization-code", "state": state})
