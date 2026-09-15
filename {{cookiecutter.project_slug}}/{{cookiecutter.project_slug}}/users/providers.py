"""The Entra provider: allauth's OpenID Connect provider, keyed by a usable object id.

The social account adapter hands it out for the ``entra`` app (``users/adapters.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.providers.base import ProviderException
from allauth.socialaccount.providers.openid_connect.provider import (
    OpenIDConnectProvider,
)

if TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

ENTRA = "entra"


class EntraProvider(OpenIDConnectProvider):
    """Entra through OpenID Connect, refusing a token without a usable object id.

    allauth keys the account by ``oid`` (``uid_field`` in the settings) but would key
    it by the text ``None`` for a null claim and raise a server error for a missing one.
    A token whose ``oid`` is missing, null, empty or not a string is refused with
    allauth's provider exception, which the callback view answers with its
    authentication error.
    The token endpoint gets the adapter's ``invalid_token`` validation error, the only
    kind its input catches. UserInfo stays off (``config/settings/base.py``), so the
    claims are the ID token's.
    """

    def extract_uid(self, data: dict[str, Any]) -> str:
        # The callback hands over {"id_token": claims}, the token endpoint the claims
        claims = data.get("id_token", data)
        oid = claims.get("oid")
        if not isinstance(oid, str) or not oid:
            msg = "The token carries no usable oid claim"
            raise ProviderException(msg)
        return oid

    def verify_token(self, request: HttpRequest, token: dict[str, Any]) -> SocialLogin:
        try:
            login: SocialLogin = super().verify_token(request, token)
        except ProviderException as e:
            code = "invalid_token"
            raise get_adapter().validation_error(code) from e
        return login
