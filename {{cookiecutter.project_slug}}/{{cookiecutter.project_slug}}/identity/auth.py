"""The API's authentication policies, for Django Ninja.

``user_auth`` authenticates a user. With an ``Authorization`` header the credential is
an app-issued JWT (``docs/authentication.rst``) and nothing else: a failure is 401,
never a fall-through to the session. Without one, Ninja's session authenticator runs,
which keeps Django's CSRF check for the session cookie. Both hand the ``User`` to the
route, as ``request.auth`` and as ``request.user``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from allauth.headless.contrib.ninja.security import JWTTokenAuth
from ninja.security import SessionAuth
from ninja.security.base import AuthBase

if TYPE_CHECKING:
    from django.http import HttpRequest

    from {{ cookiecutter.project_slug }}.users.models import User


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
            if self.token_auth(request) is None:
                return None
            return cast("User", request.user)
        return cast("User | None", self.session_auth(request))


user_auth = UserAuth()
