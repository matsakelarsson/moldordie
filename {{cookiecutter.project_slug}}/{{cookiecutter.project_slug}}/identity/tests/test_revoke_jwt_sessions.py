"""Key rotation as forced re-authentication: ``revoke_jwt_sessions`` after a new key."""

from __future__ import annotations

from http import HTTPStatus
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from allauth.mfa.totp.internal.auth import TOTP
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.urls import reverse

from {{ cookiecutter.project_slug }}.identity.tests.headless import LOGIN_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import REFRESH_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import SESSION_URL
from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user
from {{ cookiecutter.project_slug }}.identity.tests.headless import credentials
from {{ cookiecutter.project_slug }}.identity.tests.headless import password_login

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

JSON = "application/json"
NEW_KEY = "a-new-signing-key-for-every-process"


@pytest.fixture
def user() -> User:
    return create_verified_user()


def revoke() -> str:
    out = StringIO()
    call_command("revoke_jwt_sessions", stdout=out)
    return out.getvalue()


def test_rotation_signs_every_app_client_out(settings, client: Client, user: User):
    meta = password_login(client, user)
    settings.HEADLESS_JWT_PRIVATE_KEY = NEW_KEY

    revoke()

    bearer = {"Authorization": f"Bearer {meta['access_token']}"}
    session = client.get(SESSION_URL, headers=bearer)
    assert session.status_code == HTTPStatus.UNAUTHORIZED
    api = client.get(reverse("api:retrieve_current_user"), headers=bearer)
    assert api.status_code == HTTPStatus.UNAUTHORIZED
    refresh = {"refresh_token": meta["refresh_token"]}
    refreshed = client.post(REFRESH_URL, refresh, content_type=JSON)
    assert refreshed.status_code == HTTPStatus.BAD_REQUEST
    session_token = {"X-Session-Token": meta["session_token"]}
    retained = client.get(SESSION_URL, headers=session_token)
    assert retained.status_code != HTTPStatus.OK


def test_a_new_key_alone_leaves_the_session_tokens_working(settings, client, user):
    """The command is what makes a retained session token fail, not the key."""
    meta = password_login(client, user)
    settings.HEADLESS_JWT_PRIVATE_KEY = NEW_KEY

    session_token = {"X-Session-Token": meta["session_token"]}
    assert client.get(SESSION_URL, headers=session_token).status_code == HTTPStatus.OK


def test_the_pages_sessions_survive(client: Client, user: User):
    client.force_login(user)

    revoke()

    assert client.get(user.get_absolute_url()).status_code == HTTPStatus.OK
    assert Session.objects.count() == 1


def test_the_command_reports_the_sessions_it_removed(client: Client, user: User):
    password_login(client, user)
    password_login(client, user)
    client.force_login(user)

    assert revoke() == "Removed 2 sessions behind app-issued tokens.\n"
    assert revoke() == "Removed 0 sessions behind app-issued tokens.\n"


def test_a_pending_login_is_not_identified(client: Client, user: User):
    """A session without tokens yet, a second factor pending, is not the command's."""
    TOTP.activate(user, "JBSWY3DPEHPK3PXP")
    client.post(LOGIN_URL, credentials(user), content_type=JSON)

    assert revoke() == "Removed 0 sessions behind app-issued tokens.\n"
    assert Session.objects.count() == 1
