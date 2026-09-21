{%- set opentelemetry = cookiecutter.observability == 'opentelemetry' -%}
import os
from typing import Any

from celery import Celery
{%- if opentelemetry %}
from celery.signals import beat_init
{%- endif %}
from celery.signals import setup_logging
{%- if opentelemetry %}
from celery.signals import worker_process_init
from celery.signals import worker_process_shutdown

from {{ cookiecutter.project_slug }}.telemetry import configure as telemetry
{%- endif %}

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("{{cookiecutter.project_slug}}")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def config_loggers(*args: Any, **kwargs: Any) -> None:
    from logging.config import dictConfig  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)
{%- if opentelemetry %}


@worker_process_init.connect
def start_worker_telemetry(*args: Any, **kwargs: Any) -> None:
    """Export this worker process's traces and metrics.

    The prefork pool forks its worker processes from the parent, and the exporters'
    threads do not survive a fork, so they are started here rather than anywhere the
    parent reaches: this signal fires in the child (``docs/adr/0020``).
    """
    telemetry.configure("celeryworker")


@worker_process_shutdown.connect
def stop_worker_telemetry(*args: Any, **kwargs: Any) -> None:
    """Send what this worker process is still holding before the pool ends it.

    The pool ends its children itself, so the exporters are stopped where they were
    started rather than where a process that exits on its own would stop them. Under
    the same deadline as every other process: the pool waits for this handler, and a
    collector that is not there would otherwise hold the worker past whatever its
    container allows it to take to stop.
    """
    telemetry.flush()


@beat_init.connect
def start_beat_telemetry(*args: Any, **kwargs: Any) -> None:
    """Export the scheduler's traces and metrics; it is one process and forks none.

    Nothing stops them here: the scheduler exits on its own, and the SDK flushes
    from the ``atexit`` hook it registered when the providers were built.
    """
    telemetry.configure("celerybeat")
{%- endif %}


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
