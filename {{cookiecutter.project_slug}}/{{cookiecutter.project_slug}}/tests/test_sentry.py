"""Tests for the Sentry wiring in ``{{ cookiecutter.project_slug }}/sentry/apps.py``."""

from __future__ import annotations

import logging
from typing import Any

import sentry_sdk
from django.apps import AppConfig
{%- if cookiecutter.use_celery == 'y' %}
from sentry_sdk.integrations.celery import CeleryIntegration
{%- endif %}
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from {{ cookiecutter.project_slug }}.sentry import apps

DSN = "https://key@sentry.example.com/1"


class RecordingLoggingIntegration(LoggingIntegration):
    """The logging integration, remembering how it was configured."""

    def __init__(self, **kwargs: Any) -> None:
        self.configured_with = kwargs
        super().__init__(**kwargs)


def test_ready_initialises_the_sdk_from_the_settings(settings, monkeypatch):
    settings.SENTRY_DSN = DSN
    settings.SENTRY_ENVIRONMENT = "staging"
    settings.SENTRY_TRACES_SAMPLE_RATE = 0.25
    settings.SENTRY_LOG_LEVEL = logging.WARNING
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(apps, "LoggingIntegration", RecordingLoggingIntegration)

    AppConfig.create("{{ cookiecutter.project_slug }}.sentry").ready()

    (init,) = calls
    assert init["dsn"] == DSN
    assert init["environment"] == "staging"
    assert init["traces_sample_rate"] == settings.SENTRY_TRACES_SAMPLE_RATE
    assert {type(integration) for integration in init["integrations"]} == {
        RecordingLoggingIntegration,
        DjangoIntegration,
{%- if cookiecutter.use_celery == 'y' %}
        CeleryIntegration,
{%- endif %}
        RedisIntegration,
    }
    (logging_integration,) = [
        integration
        for integration in init["integrations"]
        if isinstance(integration, RecordingLoggingIntegration)
    ]
    # Records at SENTRY_LOG_LEVEL and above become breadcrumbs, errors become events
    assert logging_integration.configured_with == {
        "level": logging.WARNING,
        "event_level": logging.ERROR,
    }
