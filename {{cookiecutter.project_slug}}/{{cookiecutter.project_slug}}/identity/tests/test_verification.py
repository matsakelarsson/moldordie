"""The verifier around its key source, and what it tells the logs."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.urls import reverse
from jwt import PyJWKClientError

from {{ cookiecutter.project_slug }}.identity import verification
from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration
from {{ cookiecutter.project_slug }}.identity.tests import services
from {{ cookiecutter.project_slug }}.identity.tests.headless import bearer
from {{ cookiecutter.project_slug }}.identity.tests.services import KID
from {{ cookiecutter.project_slug }}.identity.tests.services import LIFETIME
from {{ cookiecutter.project_slug }}.identity.tests.services import SUBJECT
from {{ cookiecutter.project_slug }}.identity.tests.services import service_claims
from {{ cookiecutter.project_slug }}.identity.tests.services import sign
from {{ cookiecutter.project_slug }}.identity.verification import DiscoveredKeys

pytestmark = pytest.mark.django_db

DISCOVERY_URL = "https://issuer.example.com/.well-known/openid-configuration"
JWKS_URI = "https://issuer.example.com/keys"
NEW_KID = "2026-10"
NEW_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def keys(settings, monkeypatch: pytest.MonkeyPatch) -> services.StaticKeys:
    """The in-memory key source; the real ``DiscoveredKeys`` stays bound above."""
    return services.configure(settings, monkeypatch)


@pytest.fixture
def registration() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject=SUBJECT)


def get_principal(client, token: str) -> Any:
    return client.get(reverse("api:principal"), headers=bearer(token))


def rejections(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == verification.__name__]


class TestKeySource:
    def test_a_replaced_provider_key_is_accepted(self, client, registration, keys):
        """The provider rotates: a new key id in its key set signs the next tokens."""
        keys.keys[NEW_KID] = NEW_PRIVATE_KEY.public_key()
        token = sign(service_claims(), kid=NEW_KID, key=NEW_PRIVATE_KEY)

        assert get_principal(client, token).status_code == HTTPStatus.OK

    def test_a_retired_key_is_unknown(self, client, registration, keys, caplog):
        caplog.set_level(logging.WARNING, logger=verification.__name__)
        del keys.keys[KID]

        response = get_principal(client, sign(service_claims()))

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        (record,) = rejections(caplog)
        assert "reason=unknown_key" in record.getMessage()

    def test_a_key_lookup_failure_fails_closed(
        self,
        client,
        registration,
        monkeypatch,
        caplog,
    ):
        caplog.set_level(logging.WARNING, logger=verification.__name__)
        services.use_keys(monkeypatch, services.FailingKeys())

        response = get_principal(client, sign(service_claims()))

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        (record,) = rejections(caplog)
        assert "reason=key_lookup_failed" in record.getMessage()
        assert "could not be reached" not in record.getMessage()


class TestDiscoveredKeys:
    def test_the_client_is_built_as_agreed(self):
        keys = DiscoveredKeys(
            DISCOVERY_URL,
            fetch=lambda url, timeout: {"jwks_uri": JWKS_URI},
        )

        client = keys.discover()

        assert client.uri == JWKS_URI
        assert client.jwk_set_cache is not None
        assert client.jwk_set_cache.lifespan == verification.KEY_SET_TTL
        assert client.timeout == verification.REQUEST_TIMEOUT
        assert client.cooldown_duration == verification.REFRESH_COOLDOWN
        # No cache of single keys: the method is not wrapped in one
        assert not hasattr(client.get_signing_key, "cache_info")

    def test_discovery_uses_the_configured_url_and_timeout(self):
        seen: list[tuple[str, float]] = []

        def fetch(url: str, timeout: float) -> dict[str, Any]:
            seen.append((url, timeout))
            return {"jwks_uri": JWKS_URI}

        DiscoveredKeys(DISCOVERY_URL, fetch=fetch).discover()

        assert seen == [(DISCOVERY_URL, verification.REQUEST_TIMEOUT)]

    def test_a_failed_discovery_is_retried_on_the_next_lookup(self, monkeypatch):
        attempts: list[int] = []

        def fetch(url: str, timeout: float) -> dict[str, Any]:
            first = not attempts
            attempts.append(1)
            if first:
                msg = "the provider is down"
                raise ConnectionError(msg)
            return {"jwks_uri": JWKS_URI}

        served: dict[str, object] = {}

        class FakeClient:
            def __init__(self, uri: str, **kwargs: Any) -> None:
                served["uri"] = uri

            def get_signing_key(self, kid: str) -> Any:
                if kid != KID:
                    raise PyJWKClientError(kid)
                return type("Key", (), {"key": services.PUBLIC_KEY})()

        monkeypatch.setattr(verification, "PyJWKClient", FakeClient)
        keys = DiscoveredKeys(DISCOVERY_URL, fetch=fetch)

        with pytest.raises(ConnectionError):
            keys.signing_key(KID)
        assert keys.client is None

        assert keys.signing_key(KID) is services.PUBLIC_KEY
        assert served == {"uri": JWKS_URI}
        assert attempts == [1, 1]
        with pytest.raises(LookupError):
            keys.signing_key("unknown")

    def test_discovery_needs_https(self):
        with pytest.raises(ValueError, match="https"):
            verification.fetch_json("http://issuer.example.com/config", 1.0)


class TestLogging:
    def test_an_expired_token_is_routine(self, client, registration, caplog):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)
        expired = service_claims(exp=service_claims()["iat"] - 2 * LIFETIME)

        get_principal(client, sign(expired))

        (record,) = rejections(caplog)
        assert record.levelno == logging.INFO
        assert "reason=expired" in record.getMessage()

    def test_a_wrong_issuer_is_suspicious(self, client, registration, caplog):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)

        get_principal(client, sign(service_claims(iss="https://issuer.example.com")))

        (record,) = rejections(caplog)
        assert record.levelno == logging.WARNING
        assert "reason=bad_issuer" in record.getMessage()

    def test_a_burst_of_identical_warnings_is_collapsed(
        self,
        client,
        registration,
        caplog,
        monkeypatch,
    ):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)
        clock = [1000.0]
        monkeypatch.setattr(verification, "monotonic", lambda: clock[0])
        token = sign(service_claims(iss="https://issuer.example.com"))

        for _ in range(5):
            get_principal(client, token)

        assert [record.getMessage() for record in rejections(caplog)] == [
            "token rejected: branch=router reason=bad_issuer",
        ]

        clock[0] += verification.LOG_COOLDOWN
        get_principal(client, token)

        cooldown = f"{verification.LOG_COOLDOWN:.0f}"
        assert rejections(caplog)[-1].getMessage() == (
            "token rejected: branch=router reason=bad_issuer "
            f"(and 4 more in the last {cooldown} seconds)"
        )

    def test_different_reasons_are_not_collapsed_together(
        self,
        client,
        registration,
        caplog,
    ):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)

        get_principal(client, sign(service_claims(iss="https://issuer.example.com")))
        get_principal(client, sign(service_claims(aud="https://another.example.com")))

        assert [record.getMessage() for record in rejections(caplog)] == [
            "token rejected: branch=router reason=bad_issuer",
            "token rejected: branch=service reason=bad_audience",
        ]
