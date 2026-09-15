{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Sign-in through {% if entra %}Microsoft Entra ID{% else %}Google{% endif %} on the server-rendered pages.

The provider is never contacted: ``social.provider_login`` patches the code exchange
and the token verification, so the claims below reach allauth as if decoded from a
valid token.
"""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core import mail
from django.urls import reverse

from {{ cookiecutter.project_slug }}.users.models import User
from {{ cookiecutter.project_slug }}.users.tests import social
from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory
from {{ cookiecutter.project_slug }}.users.tests.social import CLAIMS
from {{ cookiecutter.project_slug }}.users.tests.social import PROVIDER
from {{ cookiecutter.project_slug }}.users.tests.social import SUBJECT_CLAIM

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def provider_login(client: Client, monkeypatch: pytest.MonkeyPatch):
    return partial(social.provider_login, client, monkeypatch)


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
