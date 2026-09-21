{%- set headless = cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' -%}
from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
{%- if cookiecutter.realtime == 'channels' %}
from .base import SECURE_CSP
{%- endif %}
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="!!!SET DJANGO_SECRET_KEY!!!",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
{%- if cookiecutter.observability == 'prometheus' and cookiecutter.use_docker == 'y' %}
# The scrape dials the application by its Compose service name, and a name the
# application does not answer to is refused before any view runs
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1", "django"]  # noqa: S104
{%- else %}
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104
{%- endif %}
{%- if headless %}
# https://docs.allauth.org/en/latest/headless/configuration.html
# The key allauth signs the single-page application's tokens with
HEADLESS_JWT_PRIVATE_KEY = env(
    "DJANGO_HEADLESS_JWT_PRIVATE_KEY",
    default="!!!SET DJANGO_HEADLESS_JWT_PRIVATE_KEY!!!",
)
{%- endif %}

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
{%- if cookiecutter.observability == 'prometheus' %}
        # The instrumented backend, a subclass of Django's, counts hits and misses
        "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
{%- else %}
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
{%- endif %}
        "LOCATION": "",
    },
}

# TASKS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#tasks
# Tasks run inline, in the request that enqueues them, so no worker is needed while
# developing. Switch BACKEND to "django_tasks_db.DatabaseBackend" and run
# ``python manage.py db_worker`` to try the production queue.
TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}
{% if cookiecutter.realtime == 'channels' %}
# CHANNELS
# ------------------------------------------------------------------------------
# https://channels.readthedocs.io/en/latest/topics/channel_layers.html#in-memory-channel-layer
# The in-memory layer is enough for the single development process. Switch to the
# Redis layer from production.py to try messaging across several processes.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
# https://docs.djangoproject.com/en/dev/ref/csp/
# 'self' does not cover websocket schemes in every browser
SECURE_CSP["connect-src"] = [*SECURE_CSP["connect-src"], "ws:"]
{% endif %}
# EMAIL
# ------------------------------------------------------------------------------
{#- The mail catchers: the Compose service that runs each, and the port it listens on #}
{%- set catcher = {
    'Mailpit': {'service': 'mailpit', 'port': 1025},
    'Mailtrap Local': {'service': 'mailtrap-local', 'port': 3535},
}.get(cookiecutter.mail_catcher) %}
{% if catcher -%}
# https://docs.djangoproject.com/en/dev/ref/settings/#email-host
{%- if cookiecutter.use_docker == 'y' %}
EMAIL_HOST = env("EMAIL_HOST", default="{{ catcher.service }}")
{%- else %}
EMAIL_HOST = "localhost"
{%- endif %}
# https://docs.djangoproject.com/en/dev/ref/settings/#email-port
EMAIL_PORT = {{ catcher.port }}
{%- else -%}
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
{%- endif %}

{%- if cookiecutter.use_whitenoise == 'y' %}

# WhiteNoise
# ------------------------------------------------------------------------------
# http://whitenoise.evans.io/en/latest/django.html#using-whitenoise-in-development
INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]
{% endif %}

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        # Disable profiling panel due to an issue with Python 3.12+:
        # https://github.com/jazzband/django-debug-toolbar/issues/1875
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
{% if cookiecutter.use_docker == 'y' -%}
if env("USE_DOCKER") == "yes":
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join([*ip.split(".")[:-1], "1"]) for ip in ips]
{%- endif %}

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# django-browser-reload
# ------------------------------------------------------------------------------
# https://github.com/adamchainz/django-browser-reload
# Reloads the page when the server restarts, which it does whenever a module, a
# template or the built stylesheet changes (docs/frontend.rst). Its middleware writes
# the listener into every HTML page, with the policy's nonce, and nothing into a
# fragment, which has no body element to write before
INSTALLED_APPS += ["django_browser_reload"]
# https://github.com/adamchainz/django-browser-reload#usage
# After the policy's middleware, so its response is built before the header that
# has to carry the nonce of the script it just wrote
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]
{% if cookiecutter.use_celery == 'y' -%}

# Celery
# ------------------------------------------------------------------------------
{% if cookiecutter.use_docker == 'n' -%}
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager
CELERY_TASK_ALWAYS_EAGER = True
{%- endif %}
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True

{%- endif %}
# Your stuff...
# ------------------------------------------------------------------------------
