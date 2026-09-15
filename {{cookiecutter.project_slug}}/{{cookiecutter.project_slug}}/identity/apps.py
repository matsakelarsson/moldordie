"""The identity app: the guards of the single-page application's tokens.

Generated for Django Ninja with an identity provider. ``config/settings/base.py``
configures allauth's headless API; this app refuses to start with settings that would
issue bad tokens, without touching the database or the network, so that every process
that populates the app registry checks them.
"""

from __future__ import annotations

from typing import Protocol

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

LIFETIMES = (
    "HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN",
    "HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN",
)


class TokenSettings(Protocol):
    """The settings the guard reads."""

    HEADLESS_JWT_PRIVATE_KEY: str
    HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN: int
    HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN: int


def validate_token_settings(token_settings: TokenSettings) -> None:
    """Refuse a signing key allauth would replace with ``SECRET_KEY``, and a lifetime
    that would issue tokens already expired or never expiring."""
    if not token_settings.HEADLESS_JWT_PRIVATE_KEY.strip():
        msg = (
            "DJANGO_HEADLESS_JWT_PRIVATE_KEY is empty: allauth would sign the app's "
            "tokens with SECRET_KEY"
        )
        raise ImproperlyConfigured(msg)
    for name in LIFETIMES:
        if getattr(token_settings, name) <= 0:
            msg = f"{name} must be a positive number of seconds"
            raise ImproperlyConfigured(msg)


class IdentityConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.identity"
    verbose_name = _("Identity")

    def ready(self) -> None:
        validate_token_settings(settings)
