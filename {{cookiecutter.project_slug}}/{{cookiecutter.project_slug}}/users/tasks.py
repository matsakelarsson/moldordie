"""Background tasks of the users app, run through Django's Tasks framework."""

{% if cookiecutter.use_celery == 'y' -%}
from celery import shared_task
{% endif -%}
from django.tasks import task

from .models import User


@task
def get_users_count() -> int:
    """A pointless task to demonstrate Django's Tasks framework."""
    return User.objects.count()
{%- if cookiecutter.use_celery == 'y' %}


@shared_task()
def get_users_count_with_celery() -> int:
    """The same example as a Celery task."""
    return User.objects.count()
{%- endif %}
