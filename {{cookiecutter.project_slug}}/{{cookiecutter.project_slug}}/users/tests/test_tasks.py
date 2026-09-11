import pytest
{%- if cookiecutter.use_celery == 'y' %}
from celery.result import EagerResult
{%- endif %}
from django.tasks import TaskResultStatus

from {{ cookiecutter.project_slug }}.users.tasks import get_users_count
{%- if cookiecutter.use_celery == 'y' %}
from {{ cookiecutter.project_slug }}.users.tasks import get_users_count_with_celery
{%- endif %}
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


def test_get_users_count_with_celery(settings):
    """The Celery variant runs eagerly."""
    batch_size = 3
    UserFactory.create_batch(batch_size)
    settings.CELERY_TASK_ALWAYS_EAGER = True
    task_result = get_users_count_with_celery.delay()
    assert isinstance(task_result, EagerResult)
    assert task_result.result == batch_size
{%- endif %}
