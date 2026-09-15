{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Calling services: {% if entra %}Microsoft Entra ID{% else %}Google{% endif %} tokens on the principal endpoint."""

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
from {{ cookiecutter.project_slug }}.identity.tests.services import KID
from {{ cookiecutter.project_slug }}.identity.tests.services import LIFETIME
from {{ cookiecutter.project_slug }}.identity.tests.services import SUBJECT
{%- if entra %}
from {{ cookiecutter.project_slug }}.identity.tests.services import TENANT
{%- endif %}
from {{ cookiecutter.project_slug }}.identity.tests.services import service_claims
from {{ cookiecutter.project_slug }}.identity.tests.services import sign

if TYPE_CHECKING:
    from django.test import Client

pytestmark = pytest.mark.django_db

REMOVE = object()
{%- if entra %}
ANOTHER_ISSUER = "https://login.microsoftonline.com/another/v2.0"
V1_ISSUER = f"https://sts.windows.net/{TENANT}/"
ANOTHER_AUDIENCE = "another-registration"
{%- else %}
ANOTHER_ISSUER = "https://accounts.example.com"
ANOTHER_AUDIENCE = "https://another.example.com"
{%- endif %}


@pytest.fixture(autouse=True)
def keys(settings, monkeypatch: pytest.MonkeyPatch) -> services.StaticKeys:
    return services.configure(settings, monkeypatch)


@pytest.fixture
def registration() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject=SUBJECT)


def token_with(**changes: Any) -> str:
    """A signed token whose claims differ from the valid ones by ``changes``."""
    claims = service_claims()
    for name, value in changes.items():
        if value is REMOVE:
            del claims[name]
        else:
            claims[name] = value
    return sign(claims)


def get_principal(client: Client, token: str) -> Any:
    return client.get(reverse("api:principal"), headers=bearer(token))


def rejections(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The verifier's own records, without Django's note of the 401."""
    return [record for record in caplog.records if record.name == verification.__name__]


def test_a_registered_service_reaches_the_principal_endpoint(client, registration):
    response = get_principal(client, sign(service_claims()))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "service", "name": "Billing"}


# (the case, the claims that differ from a valid token's, the refusal as the log
# records it): a foreign issuer never reaches the verifier, the router refuses it
REJECTED = [
    {%- if entra %}
    (
        "unregistered subject",
        {"oid": "someone", "sub": "someone"},
        "service:unregistered",
    ),
    ("wrong issuer", {"iss": ANOTHER_ISSUER}, "router:bad_issuer"),
    ("v1 issuer", {"iss": V1_ISSUER}, "router:bad_issuer"),
    ("wrong tenant", {"tid": "another-tenant"}, "service:bad_tenant"),
    ("wrong audience", {"aud": ANOTHER_AUDIENCE}, "service:bad_audience"),
    ("missing idtyp", {"idtyp": REMOVE}, "service:not_an_app"),
    ("user token", {"idtyp": "user"}, "service:not_an_app"),
    ("missing role", {"roles": ["Other.Role"]}, "service:missing_role"),
    ("no roles claim", {"roles": REMOVE}, "service:missing_role"),
    {%- else %}
    ("unregistered subject", {"sub": "someone"}, "service:unregistered"),
    ("wrong issuer", {"iss": ANOTHER_ISSUER}, "router:bad_issuer"),
    ("wrong audience", {"aud": ANOTHER_AUDIENCE}, "service:bad_audience"),
    {%- endif %}
    ("expired", {"exp": service_claims()["iat"] - 2 * LIFETIME}, "service:expired"),
    ("no exp", {"exp": REMOVE}, "service:missing_claim"),
]


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [(changes, refusal) for _, changes, refusal in REJECTED],
    ids=[name for name, _, _ in REJECTED],
)
def test_a_token_breaking_a_rule_is_refused(
    client,
    registration,
    caplog,
    changes,
    refusal,
):
    caplog.set_level(logging.INFO, logger=verification.__name__)
    token = token_with(**changes)

    response = get_principal(client, token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    (record,) = rejections(caplog)
    branch, reason = refusal.split(":")
    assert record.getMessage() == f"token rejected: branch={branch} reason={reason}"
    assert token[-20:] not in record.getMessage()
    assert record.exc_info is None


@pytest.mark.parametrize(
    "issuer",
    {%- if entra %}
    [ANOTHER_ISSUER, V1_ISSUER],
    ids=["another tenant", "v1"],
    {%- else %}
    [ANOTHER_ISSUER, "accounts.example.com"],
    ids=["with scheme", "without scheme"],
    {%- endif %}
)
def test_the_verifier_itself_refuses_another_issuer(registration, issuer):
    """The policy routes by the issuer first; the verifier holds the rule on its own."""
    with pytest.raises(verification.Rejected) as refused:
        verification.service_verifier().verify(token_with(iss=issuer))

    assert refused.value.reason == "bad_issuer"
{%- if not entra %}


def test_the_issuer_without_a_scheme_is_accepted(client, registration):
    """Google names itself with or without the scheme, depending on the token's age."""
    response = get_principal(client, token_with(iss="accounts.google.com"))

    assert response.status_code == HTTPStatus.OK


def test_a_token_without_an_email_claim_is_accepted(client, registration):
    """A token from the metadata server in the standard format carries no email."""
    response = get_principal(client, token_with(email=REMOVE, email_verified=REMOVE))

    assert response.status_code == HTTPStatus.OK


def test_a_user_login_token_is_refused(client, registration):
    """A user's ID token names the login client and an unregistered subject."""
    login_client = "login-client.apps.googleusercontent.com"
    user = "110248495921238986420"

    user_token = token_with(aud=login_client, sub=user)
    assert get_principal(client, user_token).status_code == HTTPStatus.UNAUTHORIZED

    right_audience = token_with(sub=user)
    assert get_principal(client, right_audience).status_code == HTTPStatus.UNAUTHORIZED
{%- endif %}


def test_a_disabled_registration_is_refused(client, registration):
    registration.enabled = False
    registration.save()

    response = get_principal(client, sign(service_claims()))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_another_algorithm_is_refused(client, registration):
    secret = "a shared secret of at least thirty-two bytes"  # noqa: S105 - a test key
    token = sign(service_claims(), key=secret, algorithm="HS256")

    assert get_principal(client, token).status_code == HTTPStatus.UNAUTHORIZED


def test_a_token_signed_by_an_unknown_key_is_refused(client, registration):
    token = sign(service_claims(), kid="unknown")

    assert get_principal(client, token).status_code == HTTPStatus.UNAUTHORIZED


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


@pytest.mark.parametrize(
    "issuer",
    [None, "", "https://issuer.example.com"],
    ids=["null", "empty", "foreign"],
)
def test_an_unusable_issuer_is_refused_beside_a_session(client, issuer):
    """The unverified issuer picks the branch, and nothing else is tried."""
    client.force_login(create_verified_user())
    token = sign(service_claims(iss=issuer))

    response = get_principal(client, token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_a_service_token_beside_a_session_is_the_service(client, registration):
    client.force_login(create_verified_user())

    response = get_principal(client, sign(service_claims()))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"kind": "service", "name": "Billing"}
    assert response.wsgi_request.user.is_anonymous
    assert response.wsgi_request.auth == registration


def test_no_token_material_reaches_the_logs(client, registration, caplog):
    caplog.set_level(logging.DEBUG, logger=verification.__name__)
    token = sign(service_claims(sub="unknown-service"{% if entra %}, oid="unknown-service"{% endif %}))

    get_principal(client, token)

    records = rejections(caplog)
    assert records
    for record in records:
        assert "unknown-service" not in record.getMessage()
        assert KID not in record.getMessage()
