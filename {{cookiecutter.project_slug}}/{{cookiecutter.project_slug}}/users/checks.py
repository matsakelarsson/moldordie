"""System checks of the users app: the credentials of the identity provider."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core import checks

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig

{%- if cookiecutter.identity_provider == 'entra' %}

PROVIDER = "Microsoft Entra ID"
CREDENTIALS = ("ENTRA_TENANT_ID", "ENTRA_LOGIN_CLIENT_ID", "ENTRA_LOGIN_CLIENT_SECRET")
{%- else %}

PROVIDER = "Google"
CREDENTIALS = ("GOOGLE_LOGIN_CLIENT_ID", "GOOGLE_LOGIN_CLIENT_SECRET")
{%- endif %}


def check_provider_credentials(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    """Sign-in through the provider needs every credential; an empty one is reported."""
    return [
        checks.Warning(
            f"{name} is empty, so sign-in through {PROVIDER} cannot work.",
            hint=f"Set {name} in the environment (docs/authentication.rst).",
            id="users.W001",
        )
        for name in CREDENTIALS
        if not getattr(settings, name).strip()
    ]
