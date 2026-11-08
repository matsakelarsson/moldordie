Background tasks
======================================================================

Background work goes through Django's `Tasks framework`_. Django provides the API for defining, enqueuing and inspecting tasks, and `django-tasks-db`_ provides the production backend: a queue table in PostgreSQL and a worker process.

What the project has
----------------------------------------------------------------------

* ``django_tasks_db`` in ``INSTALLED_APPS``, so ``migrate`` creates the task tables in every environment.
* A backend per environment in the ``TASKS`` setting. ``local.py`` and ``test.py`` use ``ImmediateBackend``, which runs a task inline in the process that enqueues it, so developing and testing need no worker. ``production.py`` uses ``django_tasks_db.DatabaseBackend``.
{%- if cookiecutter.use_docker == 'y' %}
* A worker process for production, the ``taskworker`` service in ``docker-compose.production.yml``.
{%- else %}
* A worker process for production, ``python manage.py db_worker``, which you run under your own process manager.
{%- endif %}
* An example task in ``{{ cookiecutter.project_slug }}/users/tasks.py``, with a test in ``{{ cookiecutter.project_slug }}/users/tests/test_tasks.py``.

Defining a task
----------------------------------------------------------------------

Decorate a module-level function with ``django.tasks.task``. Arguments and return values must survive a JSON round trip::

    from django.tasks import task

    @task
    def get_users_count() -> int:
        return User.objects.count()

``@task(priority=10, queue_name="emails")`` sets defaults, and ``get_users_count.using(run_after=...)`` adjusts them per call. By convention tasks live in the ``tasks.py`` of their app.

Enqueuing and results
----------------------------------------------------------------------

::

    result = get_users_count.enqueue()
    result.id          # store this to look the task up later
    result.status      # TaskResultStatus.READY / RUNNING / SUCCESSFUL / FAILED
    result.refresh()   # re-read the row written by the worker
    result.return_value

``enqueue()`` inside a view takes part in the request's transaction, because the settings enable ``ATOMIC_REQUESTS``, so a worker never sees a task whose data was rolled back. Code that enqueues inside its own ``transaction.atomic()`` block should defer the call::

    from functools import partial
    from django.db import transaction

    with transaction.atomic():
        thing = Thing.objects.create(...)
        transaction.on_commit(partial(process_thing.enqueue, thing_id=thing.pk))

Async views use ``await get_users_count.aenqueue()`` and ``await result.arefresh()``.

Running the worker
----------------------------------------------------------------------

In production the database backend only stores tasks, and a worker has to run them.
{% if cookiecutter.use_docker == 'y' %}
The ``taskworker`` service starts with the stack. Several workers are safe, because each row is claimed with ``SELECT ... FOR UPDATE SKIP LOCKED``::

    docker compose -f docker-compose.production.yml up --scale taskworker=2

To try the real queue locally, point ``TASKS["default"]["BACKEND"]`` in ``config/settings/local.py`` at ``"django_tasks_db.DatabaseBackend"`` and run a worker::

    docker compose -f docker-compose.local.yml run --rm django python manage.py db_worker

Finished task results are kept until you delete them. Schedule this command, for example daily, to apply a retention policy::

    docker compose -f docker-compose.production.yml run --rm django python manage.py prune_db_task_results
{% else %}
Run this under your process manager. Several workers are safe, because each row is claimed with ``SELECT ... FOR UPDATE SKIP LOCKED``::

    uv run --no-dev python manage.py db_worker

``--queue-name``, ``--interval``, ``--batch`` and ``--max-tasks`` tune it. ``--reload``, on by default when ``DEBUG`` is true, restarts the worker when the code changes.

To try the real queue locally, point ``TASKS["default"]["BACKEND"]`` in ``config/settings/local.py`` at ``"django_tasks_db.DatabaseBackend"`` and run ``uv run python manage.py db_worker``.

Finished task results are kept until you delete them. Schedule this command, for example daily, to apply a retention policy::

    uv run --no-dev python manage.py prune_db_task_results
{% endif %}
Testing
----------------------------------------------------------------------

The test settings use the immediate backend, so a test calls ``enqueue()`` and asserts on the returned ``TaskResult``::

    result = get_users_count.enqueue()
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == 3

An exception in the task does not propagate. The result ends up ``FAILED``, with the traceback in ``result.errors``. Django 6.0 does not reset the task backends when settings change, so prefer the test settings over overriding ``TASKS`` inside a test.
{%- if cookiecutter.use_celery == 'y' %}

Relation to Celery
----------------------------------------------------------------------

This project runs Celery_ next to the Tasks framework, with its own API, its own worker and its own example in ``users/tasks.py``. Celery is not a backend of the Tasks framework, and the framework's API has no periodic schedules, automatic retries, chains, groups or chords.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - Django Tasks
     - Celery
   * - Example
     - ``get_users_count.enqueue()``
     - ``cache_users_count.delay()``
   * - For
     - Running a function later, outside the request
     - The same, plus schedules, retry policies and workflows
   * - Infrastructure
     - The project's PostgreSQL and the ``taskworker`` process
     - Redis, a worker, beat, and Flower to watch them
   * - Trade-off
     - No scheduler, no retries, no monitoring UI
     - A broker and three more processes to run and pay for

Use Celery when the work needs a schedule, a retry policy or a workflow, and the Tasks framework otherwise. Both decorate a plain function, so moving a task from one to the other means swapping the decorator and the call.

.. _Celery: https://docs.celeryq.dev
{%- endif %}

.. _Tasks framework: https://docs.djangoproject.com/en/6.0/topics/tasks/
.. _django-tasks-db: https://github.com/RealOrangeOne/django-tasks-db
