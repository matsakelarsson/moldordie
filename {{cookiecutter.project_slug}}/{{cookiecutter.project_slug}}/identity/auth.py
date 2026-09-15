"""The API's authentication policies, for Django Ninja.

Three policies, each one branch that verifies and never falls through to another
verifier or the session (``docs/authentication.rst``):

- ``user_auth`` authenticates a user. With an ``Authorization`` header the credential is
  an app-issued JWT and nothing else: a failure is 401. Without one, Ninja's session
  authenticator runs, which keeps Django's CSRF check for the session cookie.
- ``service_auth`` authenticates a registered service by the token its identity
  provider issued; the request's user is anonymous, whatever cookie came along.
- ``either_auth`` routes by the token's unverified ``iss`` claim: absent means an app
  token, a configured provider issuer means a service, anything else is 401.

Each hands the principal to the route as ``request.auth``: the ``User``, or the
``ServiceRegistration``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import cast

from allauth.headless.contrib.ninja.security import JWTTokenAuth
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from jwt.utils import base64url_decode
from ninja.security import SessionAuth
from ninja.security.base import AuthBase

from .verification import BAD_ISSUER
from .verification import ROUTER
from .verification import Rejected
from .verification import log_rejection
from .verification import service_verifier

if TYPE_CHECKING:
    from django.http import HttpRequest

    from {{ cookiecutter.project_slug }}.users.models import User

    from .models import ServiceRegistration

MISSING = object()
# An Authorization header is a scheme and a credential
SCHEME_AND_CREDENTIAL = 2
# A JWS in compact serialisation: header, payload, signature
JWS_SEGMENTS = 3


def bearer_token(request: HttpRequest) -> str | None:
    """The credential of an ``Authorization: Bearer`` header; None for any other."""
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != SCHEME_AND_CREDENTIAL or parts[0].lower() != "bearer":
        return None
    return parts[1]


def unverified_issuer(token: str) -> object:
    """The token's ``iss`` claim as the token states it; ``MISSING`` without one."""
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


class UserAuth(AuthBase):
    """An app-issued JWT with an ``Authorization`` header, else the session."""

    openapi_type = "http"
    openapi_scheme = "bearer"

    def __init__(self) -> None:
        super().__init__()
        # allauth's authenticator returns the token's payload and binds the user it
        # validated to the request; the policy hands out the user
        self.token_auth = JWTTokenAuth()
        self.session_auth = SessionAuth()

    def __call__(self, request: HttpRequest) -> User | None:
        if "Authorization" in request.headers:
            return self.authenticate_token(request)
        return self.authenticate_session(request)

    def authenticate_token(self, request: HttpRequest) -> User | None:
        if self.token_auth(request) is None:
            return None
        return cast("User", request.user)

    def authenticate_session(self, request: HttpRequest) -> User | None:
        return cast("User | None", self.session_auth(request))


class ServiceAuth(AuthBase):
    """A token the identity provider issued to a registered service."""

    openapi_type = "http"
    openapi_scheme = "bearer"

    def __call__(self, request: HttpRequest) -> ServiceRegistration | None:
        token = bearer_token(request)
        if token is None:
            return None
        try:
            registration = service_verifier().verify(token)
        except Rejected:
            return None
        # A service is never a user, whatever session cookie came along
        request.user = AnonymousUser()
        return registration


class EitherAuth(AuthBase):
    """A user or a service, told apart by the token's unverified issuer."""

    openapi_type = "http"
    openapi_scheme = "bearer"

    def __call__(self, request: HttpRequest) -> User | ServiceRegistration | None:
        if "Authorization" not in request.headers:
            return user_auth.authenticate_session(request)
        token = bearer_token(request)
        if token is None:
            return None
        issuer = unverified_issuer(token)
        if issuer is MISSING:
            return user_auth.authenticate_token(request)
        if isinstance(issuer, str) and issuer in settings.IDENTITY_SERVICE_ISSUERS:
            return service_auth(request)
        # Null, empty or another issuer: no branch verifies it
        log_rejection(ROUTER, BAD_ISSUER)
        return None


user_auth = UserAuth()
service_auth = ServiceAuth()
either_auth = EitherAuth()
