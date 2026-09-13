import pytest
{%- if cookiecutter.use_celery == 'y' %}
from celery.result import EagerResult
from django.core.cache import cache
{%- endif %}
from django.tasks import TaskResultStatus

{% if cookiecutter.use_celery == 'y' -%}
from {{ cookiecutter.project_slug }}.users.tasks import USERS_COUNT_CACHE_KEY
from {{ cookiecutter.project_slug }}.users.tasks import cache_users_count
{% endif -%}
from {{ cookiecutter.project_slug }}.users.tasks import get_users_count
from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_get_users_count():
    """The example task runs inline under the ImmediateBackend of the test settings."""
    batch_size = 3
    UserFactory.create_batch(batch_size)
    result = get_users_count.enqueue()
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == batch_size
{%- if cookiecutter.use_celery == 'y' %}


def test_cache_users_count(settings):
    """The Celery example runs eagerly and caches what it counted."""
    batch_size = 3
    UserFactory.create_batch(batch_size)
    settings.CELERY_TASK_ALWAYS_EAGER = True
    task_result = cache_users_count.delay()
    assert isinstance(task_result, EagerResult)
    assert task_result.result == batch_size
    assert cache.get(USERS_COUNT_CACHE_KEY) == batch_size
{%- endif %}
