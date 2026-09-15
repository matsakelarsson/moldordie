{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""Verification of the provider-issued tokens of calling services.

A calling service presents a token its identity provider issued for this API. The
verifier decodes it with PyJWT against the provider's published keys, applies the
provider's rules and resolves the registered service (``models.ServiceRegistration``).
Every refusal is a ``Rejected`` carrying one of the fixed reason codes, logged without
token material (``docs/authentication.rst``).

The keys come from a key source. In production it is ``DiscoveredKeys``, which reads
the provider's discovery document at first use and wraps PyJWT's JWKS client; the tests
inject an in-memory one. Nothing in a token's header or claims chooses where the keys
come from.
"""

from __future__ import annotations

import functools
import json
import logging
import urllib.request
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

import jwt
from django.conf import settings
from jwt import PyJWKClient
from jwt import PyJWKClientConnectionError
from jwt import PyJWKClientError

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
# The routine ones, logged at info; the rest is suspicious and logged at warning
ROUTINE = frozenset({EXPIRED})
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


class Rejected(Exception):  # noqa: N818 - an adjective, as the policies read it
    """The token was refused: ``reason`` is one of the fixed codes, the message too."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def log_rejection(reason: str) -> None:
    """Record a refusal by its code: routine ones at info, the rest at warning."""
    level = logging.INFO if reason in ROUTINE else logging.WARNING
    logger.log(level, "service token rejected: reason=%s", reason)


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


class DiscoveredKeys:
    """The provider's keys, found through its discovery document at first use.

    Discovery happens on the first lookup, not when the settings load or the checks
    run, and a failed discovery is retried on the next lookup. The key set is fetched
    through PyJWT's JWKS client: cached for ``KEY_SET_TTL``, refreshed at most once per
    ``REFRESH_COOLDOWN`` for an unknown key id, with no cache of single keys.
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

    def signing_key(self, kid: str) -> AllowedPublicKeys:
        if self.client is None:
            self.client = self.discover()
        try:
            key: AllowedPublicKeys = self.client.get_signing_key(kid).key
        except PyJWKClientConnectionError:
            raise
        except PyJWKClientError as e:
            raise LookupError(kid) from e
        return key

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
            log_rejection(rejected.reason)
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

    def subject(self, claims: dict[str, Any]) -> str:
        if claims.get("tid") != settings.ENTRA_TENANT_ID:
            raise Rejected(BAD_TENANT)
        if claims.get("idtyp") != "app":
            raise Rejected(NOT_AN_APP)
        roles = claims.get("roles")
        if not isinstance(roles, list) or settings.ENTRA_SERVICE_ROLE not in roles:
            raise Rejected(MISSING_ROLE)
        # The service principal's object id, the subject the registration names
        oid = claims.get("oid")
        if not isinstance(oid, str) or not oid:
            raise Rejected(MISSING_CLAIM)
        return oid
{%- else %}


class GoogleServiceVerifier(ServiceVerifier):
    """Google's rules: the issuer allowlist and the audience of the settings, then the
    service account's unique id."""
{%- endif %}


@functools.cache
def service_verifier() -> ServiceVerifier:
    """The verifier of the configured provider, built once at first use: discovery
    happens then, outside the settings and the system checks."""
    keys = DiscoveredKeys(settings.IDENTITY_SERVICE_DISCOVERY_URL)
    {%- if entra %}
    return EntraServiceVerifier(
    {%- else %}
    return GoogleServiceVerifier(
    {%- endif %}
        keys,
        issuers=settings.IDENTITY_SERVICE_ISSUERS,
        audience=settings.IDENTITY_SERVICE_AUDIENCE,
    )
