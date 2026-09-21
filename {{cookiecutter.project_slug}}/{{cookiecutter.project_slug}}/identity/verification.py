{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Verification of the provider-issued tokens of calling services.

A calling service presents a token its identity provider issued for this API. The
verifier decodes it with PyJWT against the provider's published keys, applies the
provider's rules and resolves the registered service (``models.ServiceRegistration``).
Every refusal is a ``Rejected`` carrying one of the fixed reason codes, logged with the
branch that refused and without token material (``docs/authentication.rst``).

The keys come from a key source. In production it is ``DiscoveredKeys``, which reads
the provider's discovery document at first use and wraps PyJWT's JWKS client; the tests
inject an in-memory one. Nothing in a token's header or claims chooses where the keys
come from.
"""

from __future__ import annotations

import functools
import json
import logging
import threading
import urllib.request
from time import monotonic
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

import jwt
from django.conf import settings
from jwt import PyJWKClient
from jwt import PyJWKClientConnectionError
from jwt import PyJWKClientError
from jwt.utils import base64url_decode

from .models import ServiceRegistration

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection

    from jwt.algorithms import AllowedPublicKeys

logger = logging.getLogger(__name__)

# The production key source: how long a fetched key set serves (an unknown key id
# forces a refresh sooner), how long a request to the provider may take, and how long
# after a refresh the next unknown key id waits before forcing another
KEY_SET_TTL = 3600.0
REQUEST_TIMEOUT = 5.0
REFRESH_COOLDOWN = 60.0
# How long a discovery that failed is left failed. Discovery is a request made while
# an unauthenticated caller waits, so what it costs has to be bounded by something
# other than how often a caller asks: within this, the answer is the one already given.
DISCOVERY_COOLDOWN = 60.0

# The reason codes of a refusal: what the logs carry, never token material
MALFORMED = "malformed"
BAD_ALGORITHM = "bad_algorithm"
UNKNOWN_KEY = "unknown_key"
KEY_LOOKUP_FAILED = "key_lookup_failed"
EXPIRED = "expired"
NOT_YET_VALID = "not_yet_valid"
BAD_ISSUER = "bad_issuer"
BAD_AUDIENCE = "bad_audience"
MISSING_CLAIM = "missing_claim"
BAD_SIGNATURE = "bad_signature"
BAD_TENANT = "bad_tenant"
NOT_AN_APP = "not_an_app"
MISSING_ROLE = "missing_role"
UNREGISTERED = "unregistered"
DISABLED = "disabled"
NOT_CONFIGURED = "not_configured"
# The routine ones, logged at info; the rest is suspicious and logged at warning, once
# per reason and LOG_COOLDOWN seconds, the repeats counted into the next record
ROUTINE = frozenset({EXPIRED})
LOG_COOLDOWN = 60.0
# The branch codes of a refusal: the service verifier, or the router of either_auth,
# which refuses a token no branch verifies
SERVICE = "service"
ROUTER = "router"
# What PyJWT's errors mean, the specific ones before the general
PYJWT_REASONS = (
    (jwt.ExpiredSignatureError, EXPIRED),
    (jwt.ImmatureSignatureError, NOT_YET_VALID),
    (jwt.InvalidIssuerError, BAD_ISSUER),
    (jwt.InvalidAudienceError, BAD_AUDIENCE),
    (jwt.MissingRequiredClaimError, MISSING_CLAIM),
    (jwt.InvalidSignatureError, BAD_SIGNATURE),
    (jwt.InvalidTokenError, MALFORMED),
)

# A JWS in compact serialisation: header, payload, signature
JWS_SEGMENTS = 3
# What ``unverified_issuer`` answers for a credential that names no issuer
MISSING = object()


def unverified_issuer(token: str) -> object:
    """The token's ``iss`` claim as the token states it; ``MISSING`` without one.

    Nothing is trusted here: a caller reads the issuer to pick which branch verifies the
    token, and that branch checks the issuer itself against the settings.
    """
    segments = token.split(".")
    if len(segments) != JWS_SEGMENTS:
        return MISSING
    try:
        claims = json.loads(base64url_decode(segments[1].encode()))
    except ValueError:
        return MISSING
    if not isinstance(claims, dict):
        return MISSING
    return claims.get("iss", MISSING)


class Rejected(Exception):  # noqa: N818 - an adjective, as the policies read it
    """The token was refused: ``reason`` is one of the fixed codes, the message too."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WarningCooldown:
    """Admits one warning per key and cooldown, counting the repeats it swallows."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._lock = threading.Lock()
        self._last_admitted: dict[str, float] = {}
        self._swallowed: dict[str, int] = {}

    def admit(self, key: str) -> int | None:
        """The repeats swallowed since the last admitted warning for ``key``; None
        when this one is swallowed too."""
        with self._lock:
            now = monotonic()
            last = self._last_admitted.get(key)
            if last is not None and now - last < self.seconds:
                self._swallowed[key] = self._swallowed.get(key, 0) + 1
                return None
            self._last_admitted[key] = now
            return self._swallowed.pop(key, 0)

    def reset(self) -> None:
        with self._lock:
            self._last_admitted.clear()
            self._swallowed.clear()


warnings = WarningCooldown(LOG_COOLDOWN)


def log_rejection(branch: str, reason: str) -> None:
    """Record a refusal by its codes: routine ones at info, the rest at warning.

    A warning repeats for the same codes at most once per ``LOG_COOLDOWN`` seconds; the
    next one says how many the cooldown swallowed, so a burst is one record.
    """
    if reason in ROUTINE:
        logger.info("token rejected: branch=%s reason=%s", branch, reason)
        return
    repeats = warnings.admit(f"{branch}:{reason}")
    if repeats is None:
        return
    if repeats:
        logger.warning(
            "token rejected: branch=%s reason=%s "
            "(and %d more in the last %.0f seconds)",
            branch,
            reason,
            repeats,
            LOG_COOLDOWN,
        )
    else:
        logger.warning("token rejected: branch=%s reason=%s", branch, reason)


def reset_rate_limits() -> None:
    """Forget the warnings' cooldowns, for the tests."""
    warnings.reset()


class KeySource(Protocol):
    def signing_key(self, kid: str) -> AllowedPublicKeys:
        """The provider's public key with id ``kid``; ``LookupError`` without one."""


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    """The JSON document at ``url``, an https URL from the settings."""
    if not url.startswith("https://"):
        msg = "discovery needs an https URL"
        raise ValueError(msg)
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - https, checked above
        document = json.load(response)
    if not isinstance(document, dict):
        msg = "the discovery document is not a JSON object"
        raise TypeError(msg)
    return document


class NotConfigured(RuntimeError):  # noqa: N818 - a state, as the key sources read
    """No provider to discover keys from, so no token could have come from one."""


class Unavailable(RuntimeError):  # noqa: N818 - a state, as the key sources read
    """The provider was asked recently and could not answer; not asked again yet."""


class UnconfiguredKeys:
    """The key source of a deployment that named no provider.

    Reaching a provider is a request this application makes while a caller that has
    not been authenticated waits for it, and the settings decide who that provider is.
    Where they name nobody, no token can verify whatever is fetched, so nothing is
    fetched: an issuer built from an empty tenant names no tenant, and is a value a
    caller writes into a token rather than one that identifies anyone.
    """

    def signing_key(self, kid: str) -> AllowedPublicKeys:
        raise NotConfigured(kid)


class DiscoveredKeys:
    """The provider's keys, found through its discovery document at first use.

    Discovery happens on the first lookup, not when the settings load or the checks
    run. One lookup discovers however many arrive at once, and a discovery that failed
    is not attempted again for ``DISCOVERY_COOLDOWN``: the caller it is done for is
    unauthenticated, so a token naming a configured issuer would otherwise be enough
    to put every worker of the deployment in an outbound request of its own.

    The key set itself is fetched through PyJWT's JWKS client: cached for
    ``KEY_SET_TTL``, refreshed at most once per ``REFRESH_COOLDOWN`` for an unknown key
    id, with no cache of single keys.
    """

    def __init__(
        self,
        discovery_url: str,
        *,
        fetch: Callable[[str, float], dict[str, Any]] = fetch_json,
    ) -> None:
        self.discovery_url = discovery_url
        self.fetch = fetch
        self.client: PyJWKClient | None = None
        self.lock = threading.Lock()
        self.failed_at: float | None = None

    def signing_key(self, kid: str) -> AllowedPublicKeys:
        client = self.discovered()
        try:
            key: AllowedPublicKeys = client.get_signing_key(kid).key
        except PyJWKClientConnectionError:
            raise
        except PyJWKClientError as e:
            raise LookupError(kid) from e
        return key

    def discovered(self) -> PyJWKClient:
        """The client, discovered once however many callers arrive together.

        The lock is what makes concurrent callers share one request rather than make
        one each; ``failed_at`` is what makes the caller after a failure share its
        answer rather than ask again. Both are held for the same reason: what is on
        the other side of this is the provider, and what is on this side is a token
        nothing has verified yet.
        """
        with self.lock:
            if self.client is not None:
                return self.client
            failed = self.failed_at
            if failed is not None and monotonic() - failed < DISCOVERY_COOLDOWN:
                raise Unavailable(self.discovery_url)
            try:
                self.client = self.discover()
            except Exception:
                self.failed_at = monotonic()
                raise
            self.failed_at = None
            return self.client

    def discover(self) -> PyJWKClient:
        document = self.fetch(self.discovery_url, REQUEST_TIMEOUT)
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str):
            msg = "the discovery document names no jwks_uri"
            raise TypeError(msg)
        return PyJWKClient(
            jwks_uri,
            cache_keys=False,
            cache_jwk_set=True,
            lifespan=KEY_SET_TTL,
            timeout=REQUEST_TIMEOUT,
            cooldown_duration=REFRESH_COOLDOWN,
        )


class ServiceVerifier:
    """The core: PyJWT's decoder with a fixed algorithm, the required claims and the
    issuers and audience of the settings; the provider's rules pick the subject."""

    algorithm = "RS256"
    required_claims = ("exp", "iat", "iss", "aud", "sub")
    leeway = 60

    def __init__(
        self,
        keys: KeySource,
        *,
        issuers: Collection[str],
        audience: str,
    ) -> None:
        self.keys = keys
        self.issuers = list(issuers)
        self.audience = audience

    def verify(self, token: str) -> ServiceRegistration:
        """The registered, enabled service the token names; ``Rejected`` otherwise."""
        try:
            return self.resolve(self.decode(token))
        except Rejected as rejected:
            log_rejection(SERVICE, rejected.reason)
            raise

    def decode(self, token: str) -> dict[str, Any]:
        """The token's claims, once its signature and the required claims check out."""
        key = self.signing_key(token)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[self.algorithm],
                issuer=self.issuers,
                audience=self.audience,
                leeway=self.leeway,
                options={"require": list(self.required_claims)},
            )
        except jwt.InvalidTokenError as e:
            raise Rejected(reason_of(e)) from e
        return claims

    def signing_key(self, token: str) -> AllowedPublicKeys:
        """The key the token's header names, for the fixed algorithm."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as e:
            raise Rejected(MALFORMED) from e
        if header.get("alg") != self.algorithm:
            raise Rejected(BAD_ALGORITHM)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise Rejected(UNKNOWN_KEY)
        try:
            return self.keys.signing_key(kid)
        except LookupError as e:
            raise Rejected(UNKNOWN_KEY) from e
        except NotConfigured as e:
            raise Rejected(NOT_CONFIGURED) from e
        except Exception as e:
            raise Rejected(KEY_LOOKUP_FAILED) from e

    def subject(self, claims: dict[str, Any]) -> str:
        """The registered subject the claims name, once the provider's rules hold."""
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise Rejected(MISSING_CLAIM)
        return subject

    def resolve(self, claims: dict[str, Any]) -> ServiceRegistration:
        registrations = ServiceRegistration.objects.filter(subject=self.subject(claims))
        registration = registrations.first()
        if registration is None:
            raise Rejected(UNREGISTERED)
        if not registration.enabled:
            raise Rejected(DISABLED)
        return registration


def reason_of(error: jwt.InvalidTokenError) -> str:
    return next(reason for cls, reason in PYJWT_REASONS if isinstance(error, cls))
{%- if entra %}


class EntraServiceVerifier(ServiceVerifier):
    """Entra's rules: the tenant's token for an application holding the service role."""

    def __init__(
        self,
        keys: KeySource,
        *,
        issuers: Collection[str],
        audience: str,
        tenant: str,
        role: str,
    ) -> None:
        super().__init__(keys, issuers=issuers, audience=audience)
        self.tenant = tenant
        self.role = role

    def subject(self, claims: dict[str, Any]) -> str:
        if claims.get("tid") != self.tenant:
            raise Rejected(BAD_TENANT)
        if claims.get("idtyp") != "app":
            raise Rejected(NOT_AN_APP)
        roles = claims.get("roles")
        if not isinstance(roles, list) or self.role not in roles:
            raise Rejected(MISSING_ROLE)
        # The service principal's object id, the subject the registration names
        oid = claims.get("oid")
        if not isinstance(oid, str) or not oid:
            raise Rejected(MISSING_CLAIM)
        return oid
{%- endif %}


def configured() -> bool:
    """Whether the settings name a provider a calling service's token could name.

    An audience is what a token names this application by, and without one nothing a
    provider signed is addressed here.{% if entra %} A tenant is what its issuer names, and
    without one the issuer identifies no tenant.{% endif %} Neither is a system check's
    business: a check reports, and this decides whether anything is asked of the
    network on behalf of a caller nothing has verified.
    """
    named = [settings.IDENTITY_SERVICE_AUDIENCE]
    {%- if entra %}
    named.append(settings.ENTRA_TENANT_ID)
    {%- endif %}
    return all(value.strip() for value in named)


def key_source() -> KeySource:
    """Where the provider's keys come from, or nowhere if there is no provider."""
    if not configured():
        return UnconfiguredKeys()
    return DiscoveredKeys(settings.IDENTITY_SERVICE_DISCOVERY_URL)


@functools.cache
def service_verifier() -> ServiceVerifier:
    """The verifier of the configured provider, built once at first use: discovery
    happens then, outside the settings and the system checks."""
    keys = key_source()
    {%- if entra %}
    return EntraServiceVerifier(
        keys,
        issuers=settings.IDENTITY_SERVICE_ISSUERS,
        audience=settings.IDENTITY_SERVICE_AUDIENCE,
        tenant=settings.ENTRA_TENANT_ID,
        role=settings.ENTRA_SERVICE_ROLE,
    )
    {%- else %}
    # Google's rules are the core's: the issuer allowlist and the audience of the
    # settings, then the service account's unique id as the subject
    return ServiceVerifier(
        keys,
        issuers=settings.IDENTITY_SERVICE_ISSUERS,
        audience=settings.IDENTITY_SERVICE_AUDIENCE,
    )
    {%- endif %}
