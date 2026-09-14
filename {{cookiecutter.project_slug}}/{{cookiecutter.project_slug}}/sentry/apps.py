"""Error reporting to Sentry, wired once the app registry is ready.

``config/settings/production.py`` holds the configuration and installs this app. The SDK
is initialised here rather than there so that the settings can be imported without side
effects.
"""

import logging
from typing import Protocol
from typing import cast

import sentry_sdk
from django.apps import AppConfig
from django.conf import settings
{%- if cookiecutter.use_celery == 'y' %}
from sentry_sdk.integrations.celery import CeleryIntegration
{%- endif %}
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration


class SentrySettings(Protocol):
    """The settings this app reads; the production settings define them."""

    SENTRY_DSN: str
    SENTRY_ENVIRONMENT: str
    SENTRY_TRACES_SAMPLE_RATE: float
    # Log records at this level and above become breadcrumbs
    SENTRY_LOG_LEVEL: int


class SentryConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.sentry"

    def ready(self) -> None:
        # mypy resolves settings against the test settings, which define none of these
        sentry_settings = cast("SentrySettings", settings)
        sentry_sdk.init(
            dsn=sentry_settings.SENTRY_DSN,
            integrations=[
                LoggingIntegration(
                    level=sentry_settings.SENTRY_LOG_LEVEL,
                    event_level=logging.ERROR,  # Errors become events
                ),
                DjangoIntegration(),
{%- if cookiecutter.use_celery == 'y' %}
                CeleryIntegration(),
{%- endif %}
                RedisIntegration(),
            ],
            environment=sentry_settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=sentry_settings.SENTRY_TRACES_SAMPLE_RATE,
        )
