# ruff: noqa: E501
{#- The answers this module forks on, and the mail service's Anymail wiring: its page
    in the Anymail documentation, the email backend, and the ANYMAIL settings it reads
    from the environment as (setting, variable, default). Adding a service is adding a row. #}
{%- set aws = cookiecutter.cloud_provider == 'AWS' %}
{%- set whitenoise = cookiecutter.use_whitenoise == 'y' %}
{%- set channels = cookiecutter.realtime == 'channels' %}
{%- set sentry = cookiecutter.use_sentry == 'y' %}
{%- set headless = cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
{%- set mail = {
    'Mailgun': {
        'docs': 'https://anymail.readthedocs.io/en/stable/esps/mailgun/',
        'backend': 'anymail.backends.mailgun.EmailBackend',
        'settings': [
            ('MAILGUN_API_KEY', 'MAILGUN_API_KEY', none),
            ('MAILGUN_SENDER_DOMAIN', 'MAILGUN_DOMAIN', none),
            ('MAILGUN_API_URL', 'MAILGUN_API_URL', 'https://api.mailgun.net/v3'),
        ],
    },
    'Amazon SES': {
        'docs': 'https://anymail.readthedocs.io/en/stable/esps/amazon_ses/',
        'backend': 'anymail.backends.amazon_ses.EmailBackend',
        'settings': [],
    },
    'Other SMTP': {
        'docs': 'https://anymail.readthedocs.io/en/stable/esps',
        'backend': 'django.core.mail.backends.smtp.EmailBackend',
        'settings': [],
    },
}[cookiecutter.mail_service] %}
{%- if sentry %}
import logging
{%- endif %}
{%- if not mail.settings %}
from typing import Any
{%- endif %}
{%- if sentry or not mail.settings %}
{% endif %}
from .base import *  # noqa: F403
from .base import DATABASES
from .base import INSTALLED_APPS
from .base import REDIS_URL
from .base import SECURE_CSP
{%- if cookiecutter.rest_api == 'DRF' %}
from .base import SPECTACULAR_SETTINGS
{%- endif %}
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["{{ cookiecutter.domain_name }}"])

# DATABASES
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

# CACHES
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Mimicking memcache behavior.
            # https://github.com/jazzband/django-redis#memcached-exceptions-behavior
            "IGNORE_EXCEPTIONS": True,
        },
    },
}

# TASKS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#tasks
# https://github.com/RealOrangeOne/django-tasks-db
# Tasks are stored in PostgreSQL and run by ``python manage.py db_worker``, the
# ``taskworker`` Compose service / worker process. With ATOMIC_REQUESTS the task
# row is committed together with the request, so a worker never sees a task whose
# data was rolled back. Code that enqueues inside its own transaction.atomic()
# block should defer with transaction.on_commit(partial(task.enqueue, ...)).
TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
{% if channels %}
# CHANNELS
# ------------------------------------------------------------------------------
# https://channels.readthedocs.io/en/latest/topics/channel_layers.html#redis-channel-layer
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}
{% endif %}
# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-name
SESSION_COOKIE_NAME = "__Secure-sessionid"
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-name
CSRF_COOKIE_NAME = "__Secure-csrftoken"
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF",
    default=True,
)
# https://docs.djangoproject.com/en/dev/ref/csp/
{%- if channels %}
# 'self' does not cover websocket schemes in every browser
SECURE_CSP["connect-src"] = [*SECURE_CSP["connect-src"], "wss:"]
{%- endif %}
# Browsers POST violation reports to this URL
# (Sentry and most CSP services provide one)
if csp_report_uri := env("DJANGO_CSP_REPORT_URI", default=None):
    SECURE_CSP["report-uri"] = [csp_report_uri]
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-csp-report-only
# Roll the policy out safely: report violations without blocking anything
if env.bool("DJANGO_CSP_REPORT_ONLY", default=False):
    SECURE_CSP_REPORT_ONLY = SECURE_CSP
    SECURE_CSP = {}

{% if aws %}
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_QUERYSTRING_AUTH = False
# DO NOT change these unless you know what you're doing.
_AWS_EXPIRY = 60 * 60 * 24 * 7
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate",
}
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_MAX_MEMORY_SIZE = env.int(
    "DJANGO_AWS_S3_MAX_MEMORY_SIZE",
    default=100_000_000,  # 100MB
)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#cloudfront
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)
aws_s3_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
{% endif -%}
# STATIC & MEDIA
# ------------------------
{#- The cloud provider decides where uploads go, WhiteNoise whether the app serves the
    static files itself; without it the provider serves them (no provider without
    WhiteNoise is refused when the project is generated). #}
STORAGES = {
    "default": {
{%- if aws %}
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "location": "media",
            "file_overwrite": False,
        },
{%- else %}
        "BACKEND": "django.core.files.storage.FileSystemStorage",
{%- endif %}
    },
    "staticfiles": {
{%- if whitenoise %}
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
{%- else %}
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "location": "static",
        },
{%- endif %}
    },
}

{%- if aws %}
MEDIA_URL = f"https://{aws_s3_domain}/media/"
{%- if not whitenoise %}
COLLECTFASTA_STRATEGY = "collectfasta.strategies.boto3.Boto3Strategy"
STATIC_URL = f"https://{aws_s3_domain}/static/"
{%- endif %}
{%- endif %}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="{{ cookiecutter.project_name | string_escape }} <noreply@{{ cookiecutter.domain_name }}>",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[{{ cookiecutter.project_name | string_escape }}] ",
)
ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL regex.
ADMIN_URL = env("DJANGO_ADMIN_URL")
{%- if headless %}

# django-allauth headless
# ------------------------------------------------------------------------------
# The key allauth signs the single-page application's tokens with, and the origins
# the application is served from: required here, defaulted in development
HEADLESS_JWT_PRIVATE_KEY = env("DJANGO_HEADLESS_JWT_PRIVATE_KEY")
FRONTEND_ORIGINS = env.list("DJANGO_FRONTEND_ORIGINS")
CORS_ALLOWED_ORIGINS = FRONTEND_ORIGINS
{%- endif %}

# Anymail
# ------------------------------------------------------------------------------
# https://anymail.readthedocs.io/en/stable/installation/#installing-anymail
INSTALLED_APPS += ["anymail"]
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# https://anymail.readthedocs.io/en/stable/installation/#anymail-settings-reference
# {{ mail.docs }}
EMAIL_BACKEND = "{{ mail.backend }}"
{%- if mail.settings %}
ANYMAIL = {
{%- for setting, variable, default in mail.settings %}
    "{{ setting }}": env("{{ variable }}"{% if default is not none %}, default="{{ default }}"{% endif %}),
{%- endfor %}
}
{%- else %}
ANYMAIL: dict[str, Any] = {}
{%- endif %}

{% if aws and not whitenoise -%}
# Collectfasta
# ------------------------------------------------------------------------------
# https://github.com/jasongi/collectfasta#installation
INSTALLED_APPS = ["collectfasta", *INSTALLED_APPS]
{% endif %}
# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
{#- Without Sentry, errors are mailed to the admins; with it, the SDK reports them,
    and the loggers the SDK itself uses stay on the console. #}
{%- if not sentry %}
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
{%- endif %}
LOGGING = {
    "version": 1,
{%- if sentry %}
    "disable_existing_loggers": True,
{%- else %}
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
{%- endif %}
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
{%- if not sentry %}
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
{%- endif %}
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
{%- if sentry %}
        "django.db.backends": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        # Errors logged by the SDK itself
        "sentry_sdk": {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
{%- else %}
        "django.request": {
            "handlers": ["mail_admins"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console", "mail_admins"],
            "propagate": True,
        },
{%- endif %}
    },
}
{% if sentry %}
# Sentry
# ------------------------------------------------------------------------------
# https://docs.sentry.io/platforms/python/integrations/django/
# The SDK is initialised from these settings once the app registry is ready, by
# {{ cookiecutter.project_slug }}/sentry/apps.py, so that importing this module has no side effects.
INSTALLED_APPS += ["{{ cookiecutter.project_slug }}.sentry"]
SENTRY_DSN = env("SENTRY_DSN")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="production")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
# Log records at this level and above become breadcrumbs; errors become events
SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.INFO)
{% endif %}
{% if cookiecutter.rest_api == 'DRF' -%}

# django-rest-framework
# -------------------------------------------------------------------------------
# Tools that generate code samples can use SERVERS to point to the correct domain
SPECTACULAR_SETTINGS["SERVERS"] = [
    {"url": "https://{{ cookiecutter.domain_name }}", "description": "Production server"},
]

{%- endif %}
# Your stuff...
# ------------------------------------------------------------------------------
