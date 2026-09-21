{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""The verifier around its key source, its provider's rules, and what it tells the logs.

The verifier is called here as its callers call it, rather than through one of them:
what it accepts and refuses is the same wherever the token arrived.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClientError

from {{ cookiecutter.project_slug }}.identity import verification
from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration
from {{ cookiecutter.project_slug }}.identity.tests import services
from {{ cookiecutter.project_slug }}.identity.tests.services import KID
from {{ cookiecutter.project_slug }}.identity.tests.services import LIFETIME
from {{ cookiecutter.project_slug }}.identity.tests.services import SUBJECT
from {{ cookiecutter.project_slug }}.identity.tests.services import service_claims
from {{ cookiecutter.project_slug }}.identity.tests.services import sign
from {{ cookiecutter.project_slug }}.identity.verification import DiscoveredKeys

pytestmark = pytest.mark.django_db

DISCOVERY_URL = "https://issuer.example.com/.well-known/openid-configuration"
JWKS_URI = "https://issuer.example.com/keys"
FOREIGN_ISSUER = "https://issuer.example.com"
NEW_KID = "2026-10"
NEW_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
# How many callers arrive at once in the test that they share one discovery
CALLERS = 4
REMOVE = object()
{%- if entra %}
ANOTHER_ISSUER = "https://login.microsoftonline.com/another/v2.0"
V1_ISSUER = f"https://sts.windows.net/{services.TENANT}/"
ANOTHER_AUDIENCE = "another-registration"
{%- else %}
ANOTHER_ISSUER = "https://accounts.example.com"
ANOTHER_AUDIENCE = "https://another.example.com"
{%- endif %}


class FakeClient:
    """PyJWT's JWKS client, without the key set behind it."""

    def __init__(self, uri: str, **kwargs: Any) -> None:
        self.uri = uri

    def get_signing_key(self, kid: str) -> Any:
        if kid != KID:
            raise PyJWKClientError(kid)
        return type("Key", (), {"key": services.PUBLIC_KEY})()


@pytest.fixture(autouse=True)
def keys(settings, monkeypatch: pytest.MonkeyPatch) -> services.StaticKeys:
    """The in-memory key source; the real ``DiscoveredKeys`` stays bound above."""
    return services.configure(settings, monkeypatch)


@pytest.fixture
def registration() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject=SUBJECT)


def verify(token: str) -> ServiceRegistration:
    return verification.service_verifier().verify(token)


def refuse(token: str) -> str:
    """Verify a token that must be refused, and answer the reason code it carried."""
    with pytest.raises(verification.Rejected) as refused:
        verify(token)
    return refused.value.reason


def rejections(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == verification.__name__]


def token_with(**changes: Any) -> str:
    """A signed token whose claims differ from the valid ones by ``changes``."""
    claims = service_claims()
    for name, value in changes.items():
        if value is REMOVE:
            del claims[name]
        else:
            claims[name] = value
    return sign(claims)


# (the case, the claims that differ from a valid token's, the reason it is refused for).
# The verifier holds each of these on its own, so they hold for whichever caller of it
# this project generated: the endpoints route a token here, they do not re-decide it.
BROKEN = [
    {%- if entra %}
    (
        "unregistered subject",
        {"oid": "someone", "sub": "someone"},
        verification.UNREGISTERED,
    ),
    ("wrong issuer", {"iss": ANOTHER_ISSUER}, verification.BAD_ISSUER),
    ("v1 issuer", {"iss": V1_ISSUER}, verification.BAD_ISSUER),
    ("wrong tenant", {"tid": "another-tenant"}, verification.BAD_TENANT),
    ("wrong audience", {"aud": ANOTHER_AUDIENCE}, verification.BAD_AUDIENCE),
    ("missing idtyp", {"idtyp": REMOVE}, verification.NOT_AN_APP),
    ("user token", {"idtyp": "user"}, verification.NOT_AN_APP),
    ("missing role", {"roles": ["Other.Role"]}, verification.MISSING_ROLE),
    ("no roles claim", {"roles": REMOVE}, verification.MISSING_ROLE),
    {%- else %}
    ("unregistered subject", {"sub": "someone"}, verification.UNREGISTERED),
    ("wrong issuer", {"iss": ANOTHER_ISSUER}, verification.BAD_ISSUER),
    ("wrong audience", {"aud": ANOTHER_AUDIENCE}, verification.BAD_AUDIENCE),
    (
        "a user's login token",
        {"aud": "login-client", "sub": "110248495921238986420"},
        verification.BAD_AUDIENCE,
    ),
    {%- endif %}
    ("expired", {"exp": service_claims()["iat"] - 2 * LIFETIME}, verification.EXPIRED),
    ("no exp", {"exp": REMOVE}, verification.MISSING_CLAIM),
]


class TestTheProvidersRules:
    """What the provider has to have said about a token before it names a service."""

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [(changes, reason) for _, changes, reason in BROKEN],
        ids=[name for name, _, _ in BROKEN],
    )
    def test_a_token_breaking_a_rule_is_refused(self, registration, changes, reason):
        assert refuse(token_with(**changes)) == reason

    def test_a_disabled_registration_is_refused(self, registration):
        registration.enabled = False
        registration.save()

        assert refuse(sign(service_claims())) == verification.DISABLED

    def test_another_algorithm_never_asks_for_a_key(self, registration, monkeypatch):
        """The algorithm is pinned before the key id is looked up, so a token this
        application could never verify costs it no request to the provider: the
        header is the caller's to write, and this is decided before anything is."""
        asked: list[str] = []

        class Counting:
            def signing_key(self, kid: str) -> Any:
                asked.append(kid)
                raise LookupError(kid)

        services.use_keys(monkeypatch, Counting())
        secret = "a shared secret of at least thirty-two bytes"  # noqa: S105 - a test key
        token = sign(service_claims(), key=secret, algorithm="HS256")

        assert refuse(token) == verification.BAD_ALGORITHM
        assert asked == []

    def test_a_token_signed_by_an_unknown_key_is_refused(self, registration):
        assert refuse(sign(service_claims(), kid="unknown")) == verification.UNKNOWN_KEY


class TestKeySource:
    def test_a_replaced_provider_key_is_accepted(self, registration, keys):
        """The provider rotates: a new key id in its key set signs the next tokens."""
        keys.keys[NEW_KID] = NEW_PRIVATE_KEY.public_key()
        token = sign(service_claims(), kid=NEW_KID, key=NEW_PRIVATE_KEY)

        assert verify(token) == registration

    def test_a_retired_key_is_unknown(self, registration, keys, caplog):
        caplog.set_level(logging.WARNING, logger=verification.__name__)
        del keys.keys[KID]

        assert refuse(sign(service_claims())) == verification.UNKNOWN_KEY
        (record,) = rejections(caplog)
        assert "reason=unknown_key" in record.getMessage()

    def test_a_key_lookup_failure_fails_closed(self, registration, monkeypatch, caplog):
        caplog.set_level(logging.WARNING, logger=verification.__name__)
        services.use_keys(monkeypatch, services.FailingKeys())

        assert refuse(sign(service_claims())) == verification.KEY_LOOKUP_FAILED
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

    def test_a_failed_discovery_is_not_asked_again_at_once(self, monkeypatch):
        """Discovery is a request made while a caller nothing has verified waits, so
        what it costs cannot be decided by how often that caller asks. Inside the
        cooldown the answer is the one already given, without asking again."""
        attempts: list[int] = []

        def fetch(url: str, timeout: float) -> dict[str, Any]:
            attempts.append(1)
            msg = "the provider is down"
            raise ConnectionError(msg)

        keys = DiscoveredKeys(DISCOVERY_URL, fetch=fetch)

        with pytest.raises(ConnectionError):
            keys.signing_key(KID)
        with pytest.raises(verification.Unavailable):
            keys.signing_key(KID)

        assert attempts == [1]
        assert keys.client is None

    def test_a_failed_discovery_is_asked_again_after_the_cooldown(self, monkeypatch):
        """Failing closed for a minute is the bound; failing closed for good would
        make one unreachable moment a deployment that needs restarting."""
        attempts: list[int] = []

        def fetch(url: str, timeout: float) -> dict[str, Any]:
            first = not attempts
            attempts.append(1)
            if first:
                msg = "the provider is down"
                raise ConnectionError(msg)
            return {"jwks_uri": JWKS_URI}

        monkeypatch.setattr(verification, "PyJWKClient", FakeClient)
        keys = DiscoveredKeys(DISCOVERY_URL, fetch=fetch)

        with pytest.raises(ConnectionError):
            keys.signing_key(KID)
        stale: float | None = time.monotonic() - verification.DISCOVERY_COOLDOWN - 1
        keys.failed_at = stale

        assert keys.signing_key(KID) is services.PUBLIC_KEY
        assert attempts == [1, 1]
        assert keys.failed_at is None
        with pytest.raises(LookupError):
            keys.signing_key("unknown")

    def test_one_discovery_serves_the_callers_that_arrive_together(self, monkeypatch):
        """A token naming a configured issuer is all it takes to reach this, so the
        callers that arrive while a discovery is in flight wait for its answer rather
        than open a request of their own: otherwise each worker holds one."""
        attempts: list[int] = []
        together = threading.Barrier(CALLERS)

        def fetch(url: str, timeout: float) -> dict[str, Any]:
            attempts.append(1)
            time.sleep(0.05)
            return {"jwks_uri": JWKS_URI}

        monkeypatch.setattr(verification, "PyJWKClient", FakeClient)
        keys = DiscoveredKeys(DISCOVERY_URL, fetch=fetch)
        found: list[Any] = []

        def ask() -> None:
            together.wait()
            found.append(keys.signing_key(KID))

        callers = [threading.Thread(target=ask) for _ in range(CALLERS)]
        for caller in callers:
            caller.start()
        for caller in callers:
            caller.join()

        assert attempts == [1]
        assert found == [services.PUBLIC_KEY] * CALLERS

    def test_discovery_needs_https(self):
        with pytest.raises(ValueError, match="https"):
            verification.fetch_json("http://issuer.example.com/config", 1.0)


class TestAnUnnamedProvider:
    """A deployment whose settings name no provider asks nothing of the network.

    Everything above this is reached by a caller that has presented a token and
    nothing more. Where the settings identify nobody, no token can verify against
    whatever a request would return, so the request is not made.
    """

    def test_a_named_provider_is_discovered(self):
        assert verification.configured() is True

    def test_nothing_is_asked_where_the_audience_is_empty(self, settings, registration):
        settings.IDENTITY_SERVICE_AUDIENCE = ""
        verification.service_verifier.cache_clear()

        assert verification.configured() is False
        assert isinstance(verification.key_source(), verification.UnconfiguredKeys)
        assert refuse(sign(service_claims())) == verification.NOT_CONFIGURED
{%- if entra %}

    def test_nothing_is_asked_where_the_tenant_is_empty(self, settings, registration):
        """An issuer built from an empty tenant names no tenant, and is a value a
        caller writes into a token rather than one that identifies anyone."""
        settings.ENTRA_TENANT_ID = ""
        verification.service_verifier.cache_clear()

        assert verification.configured() is False
        assert isinstance(verification.key_source(), verification.UnconfiguredKeys)
        assert refuse(sign(service_claims())) == verification.NOT_CONFIGURED
{%- endif %}


class TestLogging:
    def test_an_expired_token_is_routine(self, registration, caplog):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)
        expired = service_claims(exp=service_claims()["iat"] - 2 * LIFETIME)

        refuse(sign(expired))

        (record,) = rejections(caplog)
        assert record.levelno == logging.INFO
        assert "reason=expired" in record.getMessage()

    def test_a_wrong_issuer_is_suspicious(self, registration, caplog):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)

        refuse(sign(service_claims(iss=FOREIGN_ISSUER)))

        (record,) = rejections(caplog)
        assert record.levelno == logging.WARNING
        assert "reason=bad_issuer" in record.getMessage()

    def test_a_burst_of_identical_warnings_is_collapsed(
        self,
        registration,
        caplog,
        monkeypatch,
    ):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)
        clock = [1000.0]
        monkeypatch.setattr(verification, "monotonic", lambda: clock[0])
        token = sign(service_claims(iss=FOREIGN_ISSUER))

        for _ in range(5):
            refuse(token)

        assert [record.getMessage() for record in rejections(caplog)] == [
            "token rejected: branch=service reason=bad_issuer",
        ]

        clock[0] += verification.LOG_COOLDOWN
        refuse(token)

        cooldown = f"{verification.LOG_COOLDOWN:.0f}"
        assert rejections(caplog)[-1].getMessage() == (
            "token rejected: branch=service reason=bad_issuer "
            f"(and 4 more in the last {cooldown} seconds)"
        )

    def test_different_reasons_are_not_collapsed_together(self, registration, caplog):
        caplog.set_level(logging.DEBUG, logger=verification.__name__)

        refuse(sign(service_claims(iss=FOREIGN_ISSUER)))
        refuse(sign(service_claims(aud="https://another.example.com")))

        assert [record.getMessage() for record in rejections(caplog)] == [
            "token rejected: branch=service reason=bad_issuer",
            "token rejected: branch=service reason=bad_audience",
        ]
