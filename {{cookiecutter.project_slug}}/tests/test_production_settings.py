"""The production settings, loaded under the environment ``.envs/.production`` declares.

A deployment provides these variables. The values the files leave blank are filled with
stand-ins here, so loading the settings shows that the files declare every variable the
settings require, and the loaded values are what the tests check.
"""

from __future__ import annotations

{% if cookiecutter.use_sentry == 'y' -%}
import logging
{% endif -%}
import sys

import pytest
from django.apps import AppConfig
from django.conf import Settings
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
from django.core.exceptions import ImproperlyConfigured
{%- endif %}
from django.utils.csp import CSP

from merge_production_dotenvs_in_dotenv import PRODUCTION_DOTENV_FILES
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
from {{ cookiecutter.project_slug }}.identity.apps import validate_token_settings
{%- endif %}

# production.py extends lists and dicts it imports from base.py, so both are imported
# afresh and the settings the tests run on keep their own objects
SETTINGS_MODULES = ("config.settings.base", "config.settings.production")
{%- if cookiecutter.cloud_provider == 'AWS' %}
S3_STORAGE = "storages.backends.s3.S3Storage"
{%- else %}
FILESYSTEM_STORAGE = "django.core.files.storage.FileSystemStorage"
{%- endif %}
{%- if cookiecutter.use_whitenoise == 'y' %}
WHITENOISE_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}
TRACES_SAMPLE_RATE = 0.5
{%- endif %}


def declared_environment() -> dict[str, str]:
    """The variables the production env files declare, with stand-ins for blanks."""
    environment = {}
    for path in PRODUCTION_DOTENV_FILES:
        for line in path.read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            name, _, value = line.partition("=")
            environment[name] = value or f"{name.lower()}-stand-in"
    return environment


@pytest.fixture
def environment():
    return declared_environment()


@pytest.fixture
def production_settings(environment, monkeypatch):
    """Load the production settings under the declared environment and overrides."""

    def load(**overrides: str) -> Settings:
        for name, value in {**environment, **overrides}.items():
            monkeypatch.setenv(name, value)
        cached = {
            name: sys.modules.pop(name)
            for name in SETTINGS_MODULES
            if name in sys.modules
        }
        try:
            return Settings("config.settings.production")
        finally:
            for name in SETTINGS_MODULES:
                sys.modules.pop(name, None)
            sys.modules.update(cached)

    return load


def test_the_declared_environment_is_enough(production_settings, environment):
    """The env files declare everything required, and their values are the ones read."""
    settings = production_settings()

    assert settings.DEBUG is False
    assert environment["DJANGO_SECRET_KEY"] == settings.SECRET_KEY
    assert environment["DJANGO_ADMIN_URL"] == settings.ADMIN_URL
    assert [environment["DJANGO_ALLOWED_HOSTS"]] == settings.ALLOWED_HOSTS
    assert settings.CACHES["default"]["LOCATION"] == environment["REDIS_URL"]
    assert settings.TASKS["default"]["BACKEND"] == "django_tasks_db.DatabaseBackend"
{%- if cookiecutter.realtime == 'channels' %}
    channel_layer = settings.CHANNEL_LAYERS["default"]
    assert channel_layer["CONFIG"]["hosts"] == [environment["REDIS_URL"]]
{%- endif %}


def test_every_installed_app_can_be_loaded(production_settings):
    """The apps production adds are importable, so the app registry would populate."""
    settings = production_settings()

    for entry in settings.INSTALLED_APPS:
        AppConfig.create(entry)


def test_csp_reports_violations_to_the_configured_endpoint(production_settings):
    enforced = production_settings()
    assert "report-uri" not in enforced.SECURE_CSP

    reporting = production_settings(
        DJANGO_CSP_REPORT_URI="https://csp.example.com/report",
    )
    assert reporting.SECURE_CSP["report-uri"] == ["https://csp.example.com/report"]


def test_csp_can_be_rolled_out_without_blocking(production_settings):
    enforced = production_settings()
    assert enforced.SECURE_CSP["default-src"] == [CSP.SELF]
    assert enforced.SECURE_CSP_REPORT_ONLY == {}

    report_only = production_settings(DJANGO_CSP_REPORT_ONLY="True")
    assert report_only.SECURE_CSP == {}
    assert report_only.SECURE_CSP_REPORT_ONLY["default-src"] == [CSP.SELF]
{%- if cookiecutter.realtime == 'channels' %}
    assert "wss:" in report_only.SECURE_CSP_REPORT_ONLY["connect-src"]
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' %}


def test_uploads_go_to_the_bucket(production_settings, environment):
    settings = production_settings()

    bucket = environment["DJANGO_AWS_STORAGE_BUCKET_NAME"]
    assert bucket == settings.AWS_STORAGE_BUCKET_NAME
    assert environment["DJANGO_AWS_ACCESS_KEY_ID"] == settings.AWS_ACCESS_KEY_ID
    assert settings.STORAGES["default"]["BACKEND"] == S3_STORAGE
    assert settings.STORAGES["default"]["OPTIONS"]["location"] == "media"
    assert f"https://{bucket}.s3.amazonaws.com/media/" == settings.MEDIA_URL


def test_a_custom_domain_serves_the_bucket(production_settings):
    settings = production_settings(DJANGO_AWS_S3_CUSTOM_DOMAIN="cdn.example.com")

    assert settings.MEDIA_URL == "https://cdn.example.com/media/"
{%- if cookiecutter.use_whitenoise == 'n' %}
    assert settings.STATIC_URL == "https://cdn.example.com/static/"
{%- endif %}
{%- else %}


def test_uploads_stay_on_the_server(production_settings):
    settings = production_settings()

    assert settings.STORAGES["default"]["BACKEND"] == FILESYSTEM_STORAGE
    assert settings.MEDIA_URL == "/media/"
{%- endif %}
{%- if cookiecutter.use_whitenoise == 'y' %}


def test_static_files_are_served_by_whitenoise(production_settings):
    settings = production_settings()

    assert settings.STORAGES["staticfiles"]["BACKEND"] == WHITENOISE_STORAGE
    assert settings.STATIC_URL == "/static/"
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE
{%- else %}


def test_static_files_are_served_from_the_bucket(production_settings, environment):
    settings = production_settings()

    bucket = environment["DJANGO_AWS_STORAGE_BUCKET_NAME"]
    assert settings.STORAGES["staticfiles"]["BACKEND"] == S3_STORAGE
    assert settings.STORAGES["staticfiles"]["OPTIONS"]["location"] == "static"
    assert f"https://{bucket}.s3.amazonaws.com/static/" == settings.STATIC_URL
    # Collectfasta uploads in parallel; it must come before staticfiles
    assert settings.INSTALLED_APPS[0] == "collectfasta"
{%- endif %}


def test_mail_is_sent_through_anymail(production_settings, environment):
    settings = production_settings()

    assert "anymail" in settings.INSTALLED_APPS
{%- if cookiecutter.mail_service == 'Mailgun' %}
    assert settings.EMAIL_BACKEND == "anymail.backends.mailgun.EmailBackend"
    assert {
        "MAILGUN_API_KEY": environment["MAILGUN_API_KEY"],
        "MAILGUN_SENDER_DOMAIN": environment["MAILGUN_DOMAIN"],
        "MAILGUN_API_URL": "https://api.mailgun.net/v3",
    } == settings.ANYMAIL
{%- elif cookiecutter.mail_service == 'Amazon SES' %}
    assert settings.EMAIL_BACKEND == "anymail.backends.amazon_ses.EmailBackend"
    assert settings.ANYMAIL == {}
{%- else %}
    assert settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    assert settings.ANYMAIL == {}
{%- endif %}
    assert settings.DEFAULT_FROM_EMAIL.endswith("<noreply@{{ cookiecutter.domain_name }}>")
    assert environment["DJANGO_SERVER_EMAIL"] == settings.SERVER_EMAIL
    assert settings.ACCOUNT_EMAIL_SUBJECT_PREFIX == settings.EMAIL_SUBJECT_PREFIX
{%- if cookiecutter.use_sentry == 'y' %}


def test_sentry_is_configured_from_the_environment(production_settings, environment):
    settings = production_settings()

    assert "{{ cookiecutter.project_slug }}.sentry" in settings.INSTALLED_APPS
    assert environment["SENTRY_DSN"] == settings.SENTRY_DSN
    assert settings.SENTRY_ENVIRONMENT == "production"
    assert settings.SENTRY_TRACES_SAMPLE_RATE == 0
    assert settings.SENTRY_LOG_LEVEL == logging.INFO

    tuned = production_settings(
        SENTRY_ENVIRONMENT="staging",
        SENTRY_TRACES_SAMPLE_RATE=str(TRACES_SAMPLE_RATE),
        DJANGO_SENTRY_LOG_LEVEL=str(logging.WARNING),
    )
    assert tuned.SENTRY_ENVIRONMENT == "staging"
    assert tuned.SENTRY_TRACES_SAMPLE_RATE == TRACES_SAMPLE_RATE
    assert tuned.SENTRY_LOG_LEVEL == logging.WARNING
{%- endif %}
{%- if cookiecutter.identity_provider == 'entra' %}


def test_entra_login_reads_the_environment(production_settings, environment):
    settings = production_settings()

    (app,) = settings.SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"]
    assert environment["ENTRA_LOGIN_CLIENT_ID"] == app["client_id"]
    assert environment["ENTRA_LOGIN_CLIENT_SECRET"] == app["secret"]
    tenant = environment["ENTRA_TENANT_ID"]
    server_url = f"https://login.microsoftonline.com/{tenant}/v2.0"
    assert server_url == app["settings"]["server_url"]
{%- elif cookiecutter.identity_provider == 'google' %}


def test_google_login_reads_the_environment(production_settings, environment):
    settings = production_settings()

    (app,) = settings.SOCIALACCOUNT_PROVIDERS["google"]["APPS"]
    assert environment["GOOGLE_LOGIN_CLIENT_ID"] == app["client_id"]
    assert environment["GOOGLE_LOGIN_CLIENT_SECRET"] == app["secret"]
{%- endif %}
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}


def test_the_app_tokens_use_the_declared_key(production_settings, environment):
    settings = production_settings()

    key = environment["DJANGO_HEADLESS_JWT_PRIVATE_KEY"]
    assert key == settings.HEADLESS_JWT_PRIVATE_KEY
    assert settings.HEADLESS_JWT_PRIVATE_KEY != settings.SECRET_KEY
    assert settings.HEADLESS_JWT_ALGORITHM == "HS256"
    assert settings.HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED is True
    assert [environment["DJANGO_FRONTEND_ORIGINS"]] == settings.CORS_ALLOWED_ORIGINS
    validate_token_settings(settings)


@pytest.mark.parametrize("key", ["", "   "])
def test_identity_refuses_an_empty_signing_key(production_settings, key):
    settings = production_settings(DJANGO_HEADLESS_JWT_PRIVATE_KEY=key)

    with pytest.raises(ImproperlyConfigured, match="DJANGO_HEADLESS_JWT_PRIVATE_KEY"):
        validate_token_settings(settings)


def test_identity_refuses_a_non_positive_lifetime(production_settings):
    lifetime = "HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN"
    settings = production_settings(**{f"DJANGO_{lifetime}": "0"})

    with pytest.raises(ImproperlyConfigured, match=lifetime):
        validate_token_settings(settings)
{%- endif %}
{%- if cookiecutter.rest_api == 'DRF' %}


def test_api_docs_name_the_production_server(production_settings):
    settings = production_settings()

    assert settings.SPECTACULAR_SETTINGS["SERVERS"] == [
        {"url": "https://{{ cookiecutter.domain_name }}", "description": "Production server"},
    ]
{%- endif %}
