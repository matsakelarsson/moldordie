"""Minting the provider-issued tokens of calling services for the tests.

The tokens are genuinely RS256-signed with a key pair generated here, and the verifier
is pointed at an in-memory key source holding the public key, so that the real PyJWT
decoder runs on them; nothing is fetched.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from {{ cookiecutter.project_slug }}.identity import verification

if TYPE_CHECKING:
    import pytest
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

KID = "2026-09"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = PRIVATE_KEY.public_key()
LIFETIME = 300
{%- if cookiecutter.identity_provider == 'entra' %}
TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"
API_CLIENT_ID = "api-registration"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
AUDIENCE = API_CLIENT_ID
# The calling service's service principal, as registered in the admin
SUBJECT = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
{%- else %}
ISSUER = "https://accounts.google.com"
AUDIENCE = "https://{{ cookiecutter.domain_name }}"
# The calling service account's unique id, as registered in the admin
SUBJECT = "104735692813427650912"
{%- endif %}


class StaticKeys:
    """An in-memory key source: the keys a provider would publish, by key id."""

    def __init__(self, keys: dict[str, RSAPublicKey]) -> None:
        self.keys = dict(keys)

    def signing_key(self, kid: str) -> RSAPublicKey:
        try:
            return self.keys[kid]
        except KeyError:
            raise LookupError(kid) from None


class FailingKeys:
    """A key source whose lookup fails altogether, as an unreachable provider does."""

    def signing_key(self, kid: str) -> RSAPublicKey:
        msg = "the provider could not be reached"
        raise ConnectionError(msg)


def use_keys(monkeypatch: pytest.MonkeyPatch, keys: object) -> None:
    """Build the verifier on ``keys`` instead of the provider's discovered ones.

    The verifier is built afresh, and the warnings' cooldowns are forgotten so that
    each test sees its own records.
    """
    monkeypatch.setattr(verification, "DiscoveredKeys", lambda url: keys)
    verification.service_verifier.cache_clear()
    verification.reset_rate_limits()


def configure(settings: Any, monkeypatch: pytest.MonkeyPatch) -> StaticKeys:
    """Point the verifier at the test tenant and a key source holding the public key."""
    {%- if cookiecutter.identity_provider == 'entra' %}
    settings.ENTRA_TENANT_ID = TENANT
    settings.ENTRA_API_CLIENT_ID = API_CLIENT_ID
    settings.IDENTITY_SERVICE_ISSUERS = [ISSUER]
    {%- endif %}
    settings.IDENTITY_SERVICE_AUDIENCE = AUDIENCE
    keys = StaticKeys({KID: PUBLIC_KEY})
    use_keys(monkeypatch, keys)
    return keys


def service_claims(**overrides: Any) -> dict[str, Any]:
    """The claims of a valid token for the registered service, some overridden."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + LIFETIME,
        "sub": SUBJECT,
        {%- if cookiecutter.identity_provider == 'entra' %}
        "oid": SUBJECT,
        "tid": TENANT,
        "idtyp": "app",
        "roles": ["Service.Access"],
        "azp": "caller-registration",
        "ver": "2.0",
        {%- else %}
        "azp": SUBJECT,
        "email": "billing@project.iam.gserviceaccount.com",
        "email_verified": True,
        {%- endif %}
    }
    claims.update(overrides)
    return claims


def sign(
    claims: dict[str, Any],
    *,
    kid: str = KID,
    key: RSAPrivateKey | str = PRIVATE_KEY,
    algorithm: str = "RS256",
) -> str:
    """A signed token of ``claims``, whatever they hold: JWS checks no claim."""
    payload = json.dumps(claims).encode()
    return jwt.PyJWS().encode(payload, key, algorithm=algorithm, headers={"kid": kid})
