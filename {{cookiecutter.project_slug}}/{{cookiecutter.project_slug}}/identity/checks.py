"""System checks of the identity app: the frontend settings agree with each other."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core import checks

from .frontend import origin

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig


def check_frontend_url(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    """The pages the mails link to must be on an origin the application calls from."""
    origins = {origin(configured) for configured in settings.FRONTEND_ORIGINS}
    if origin(settings.FRONTEND_URL) in origins:
        return []
    return [
        checks.Error(
            "DJANGO_FRONTEND_URL is not one of DJANGO_FRONTEND_ORIGINS, so the pages "
            "the mails link to could not call the API.",
            hint="List the frontend URL's origin in DJANGO_FRONTEND_ORIGINS.",
            id="identity.E001",
        ),
    ]
