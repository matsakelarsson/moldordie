{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""The API's routing of a calling service's token: the policies of ``identity/auth.py``
on the principal endpoint, around the verifier.

What a token has to satisfy is the verifier's rule and is tested with it, in
``test_verification.py``, whichever caller this project generated. Here is what the
policies decide on their own: which branch a token goes to, that a refusal is the
answer, and who the route then sees.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.identity import verification
from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration
from {{ cookiecutter.project_slug }}.identity.tests import services
from {{ cookiecutter.project_slug }}.identity.tests.headless import bearer
from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user
from {{ cookiecutter.project_slug }}.identity.tests.headless import password_login
from {{ cookiecutter.project_slug }}.identity.tests.services import SUBJECT
{%- if entra %}
from {{ cookiecutter.project_slug }}.identity.tests.services import TENANT
{%- endif %}
from {{ cookiecutter.project_slug }}.identity.tests.services import service_claims
from {{ cookiecutter.project_slug }}.identity.tests.services import sign

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db

# Issuers the settings do not name, so no branch verifies a token carrying one
{%- if entra %}
ANOTHER_ISSUER = "https://login.microsoftonline.com/another/v2.0"
V1_ISSUER = f"https://sts.windows.net/{TENANT}/"
{%- else %}
ANOTHER_ISSUER = "https://accounts.example.com"
{%- endif %}


@pytest.fixture(autouse=True)
def keys(settings, monkeypatch: pytest.MonkeyPatch) -> services.StaticKeys:
    return services.configure(settings, monkeypatch)


@pytest.fixture
def registration() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject=SUBJECT)


def get_principal(client: Client, token: str) -> Any:
    return client.get(reverse("api:principal"), headers=bearer(token))


def rejections(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The verifier module's own records, without Django's note of the 401."""
    return [record for record in caplog.records if record.name == verification.__name__]


def test_a_registered_service_reaches_the_principal_endpoint(client, registration):
    response = get_principal(client, sign(service_claims()))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "service", "name": "Billing"}


def test_a_token_the_verifier_refuses_is_refused(client, registration, caplog):
    """The verifier's refusal is the answer: 401, its one record, no other branch."""
    caplog.set_level(logging.INFO, logger=verification.__name__)
    token = sign(service_claims(sub="someone"{% if entra %}, oid="someone"{% endif %}))

    response = get_principal(client, token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    (record,) = rejections(caplog)
    assert record.getMessage() == "token rejected: branch=service reason=unregistered"


@pytest.mark.parametrize(
    "issuer",
    {%- if entra %}
    [None, "", ANOTHER_ISSUER, V1_ISSUER],
    ids=["null", "empty", "another tenant", "v1"],
    {%- else %}
    [None, "", ANOTHER_ISSUER, "accounts.example.com"],
    ids=["null", "empty", "another issuer", "without a scheme"],
    {%- endif %}
)
def test_an_issuer_no_branch_verifies_is_refused_by_the_router(
    client,
    registration,
    caplog,
    issuer,
):
    """The unverified issuer picks the branch, and one it names no branch for is
    refused there: beside a valid session, nothing else is tried, and the verifier
    never sees the token."""
    caplog.set_level(logging.INFO, logger=verification.__name__)
    client.force_login(create_verified_user())
    token = sign(service_claims(iss=issuer))

    response = get_principal(client, token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    (record,) = rejections(caplog)
    assert record.getMessage() == "token rejected: branch=router reason=bad_issuer"
    assert token[-20:] not in record.getMessage()
{%- if not entra %}


def test_the_issuer_without_a_scheme_is_accepted(client, registration):
    """Google names itself with or without the scheme, depending on the token's age."""
    response = get_principal(client, sign(service_claims(iss="accounts.google.com")))

    assert response.status_code == HTTPStatus.OK
{%- endif %}


def test_a_service_token_does_not_open_the_users_routes(client, registration):
    response = client.get(
        reverse("api:retrieve_current_user"),
        headers=bearer(sign(service_claims())),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_a_user_token_reaches_the_principal_endpoint_as_a_user(client):
    user = create_verified_user(name="Ada Lovelace")
    meta = password_login(client, user)

    response = get_principal(client, meta["access_token"])

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "user", "name": "Ada Lovelace"}


def test_a_session_reaches_the_principal_endpoint_as_a_user(client):
    user = create_verified_user(name="Ada Lovelace")
    client.force_login(user)

    response = client.get(reverse("api:principal"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "user", "name": "Ada Lovelace"}


def test_a_service_token_beside_a_session_is_the_service(client, registration):
    client.force_login(create_verified_user())

    response = get_principal(client, sign(service_claims()))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "service", "name": "Billing"}
    assert response.wsgi_request.user.is_anonymous
    assert response.wsgi_request.auth == registration
