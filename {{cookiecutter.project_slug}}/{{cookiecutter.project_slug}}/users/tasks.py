{% if cookiecutter.use_celery == 'y' -%}
"""Background tasks of the users app, in both of the project's task frameworks.

``get_users_count`` is the Django Tasks example: run a function later, outside the
request. ``cache_users_count`` is the Celery one, and shows what Celery adds on top
of that: a schedule and automatic retries.
"""

from celery import shared_task
from django.core.cache import cache
from django.db import OperationalError
{% else -%}
"""Background tasks of the users app, run through Django's Tasks framework."""

{% endif -%}
from django.tasks import task

from .models import User
{%- if cookiecutter.use_celery == 'y' %}

USERS_COUNT_CACHE_KEY = "users.count"
{%- endif %}


@task
def get_users_count() -> int:
    """A pointless task to demonstrate Django's Tasks framework."""
    return User.objects.count()
{%- if cookiecutter.use_celery == 'y' %}


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def cache_users_count() -> int:
    """Count the users and cache the number, the way a Celery job is usually written.

    Meant to run on a schedule (add one under Periodic Tasks in the admin, which
    django-celery-beat provides) and to retry itself with a growing delay when the
    database is briefly unavailable. Django's Tasks framework has neither a
    scheduler nor retries, so work that needs them stays with Celery.
    """
    count = User.objects.count()
    cache.set(USERS_COUNT_CACHE_KEY, count, timeout=None)
    return count
{%- endif %}
