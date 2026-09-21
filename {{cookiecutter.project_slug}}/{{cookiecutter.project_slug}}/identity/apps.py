{%- set headless = cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' -%}
{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""The identity app: the calling services the project knows and what they may do.

A calling service is a row of ``models.ServiceRegistration``; ``verification.py`` turns
a token its identity provider issued into one, and the permissions the registration
holds say what it may then do.
{%- if headless %}

With Django Ninja the app also guards the single-page application's own tokens:
``config/settings/base.py`` configures allauth's headless API, and this app refuses to
start with settings that would issue bad tokens, without touching the database or the
network, so that every process that populates the app registry checks them.
{%- endif %}
"""

from __future__ import annotations
{% if headless %}
from typing import Protocol
{% endif %}
from django.apps import AppConfig
{%- if headless %}
from django.conf import settings
{%- endif %}
{%- if headless or entra %}
from django.core import checks
{%- endif %}
{%- if headless %}
from django.core.exceptions import ImproperlyConfigured
{%- endif %}
from django.utils.translation import gettext_lazy as _
{%- if headless and entra %}

from .checks import check_frontend_url
from .checks import check_service_settings
{%- elif headless %}

from .checks import check_frontend_url
{%- elif entra %}

from .checks import check_service_settings
{%- endif %}
{%- if headless %}

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
{%- endif %}


class IdentityConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.identity"
    verbose_name = _("Identity")
{%- if headless or entra %}

    def ready(self) -> None:
{%- if headless %}
        validate_token_settings(settings)
        checks.register(check_frontend_url)
{%- endif %}
{%- if entra %}
        checks.register(check_service_settings)
{%- endif %}
{%- endif %}
