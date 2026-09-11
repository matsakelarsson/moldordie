.. _tasks:

Background tasks
================

Every generated project uses Django's built-in `Tasks framework`_ for background work. Django provides the API (defining, enqueuing and inspecting tasks) and `django-tasks-db`_ provides the production backend: a queue table in PostgreSQL and a worker process.

What you get
------------

- ``django_tasks_db`` in ``INSTALLED_APPS``, so ``migrate`` creates the task tables in every environment.
- A backend per environment in the ``TASKS`` setting: ``ImmediateBackend`` in ``local.py`` and ``test.py`` (tasks run inline, in the process that enqueues them, so no worker is needed while developing or testing) and ``django_tasks_db.DatabaseBackend`` in ``production.py``.
- A worker process for production: the ``taskworker`` service in ``docker-compose.production.yml`` and the ``taskworker`` process type in the ``Procfile``, both running ``python manage.py db_worker``.
- An example task in ``<project_slug>/users/tasks.py`` with a test in ``<project_slug>/users/tests/test_tasks.py``.

Defining a task
---------------

Decorate a module-level function with ``django.tasks.task``. Arguments and return values must survive a JSON round trip::

    from django.tasks import task

    @task
    def get_users_count() -> int:
        return User.objects.count()

``@task(priority=10, queue_name="emails")`` sets defaults; ``get_users_count.using(run_after=...)`` adjusts them per call. By convention tasks live in ``tasks.py`` of their app.

Enqueuing and results
---------------------

::

    result = get_users_count.enqueue()
    result.id          # store this to look the task up later
    result.status      # TaskResultStatus.READY / RUNNING / SUCCESSFUL / FAILED
    result.refresh()   # re-read the row written by the worker
    result.return_value

``enqueue()`` inside a view takes part in the request's transaction (the settings enable ``ATOMIC_REQUESTS``), so a worker never sees a task whose data was rolled back. Code that enqueues inside its own ``transaction.atomic()`` block should defer the call::

    from functools import partial
    from django.db import transaction

    with transaction.atomic():
        thing = Thing.objects.create(...)
        transaction.on_commit(partial(process_thing.enqueue, thing_id=thing.pk))

Async views use ``await get_users_count.aenqueue()`` and ``await result.arefresh()``.

Running the worker
------------------

In production the database backend only stores tasks; a worker has to run them:

- Docker: the ``taskworker`` service starts with the stack. Several workers are safe (rows are claimed with ``SELECT ... FOR UPDATE SKIP LOCKED``), so ``docker compose -f docker-compose.production.yml up --scale taskworker=2`` works.
- Heroku: ``heroku ps:scale taskworker=1``. This is a second dyno with its own cost; without it enqueued tasks stay in the ``READY`` state forever.
- Bare metal: ``python manage.py db_worker`` under your process manager. ``--queue-name``, ``--interval``, ``--batch`` and ``--max-tasks`` tune it; ``--reload`` (on by default when ``DEBUG`` is true) restarts the worker when code changes.

Locally the immediate backend needs no worker. To try the real queue, point ``TASKS["default"]["BACKEND"]`` in ``config/settings/local.py`` at ``"django_tasks_db.DatabaseBackend"`` and run ``uv run python manage.py db_worker`` (``docker compose -f docker-compose.local.yml run --rm django python manage.py db_worker`` with Docker).

Finished task results are kept until you delete them. Schedule ``python manage.py prune_db_task_results`` (for example daily) to apply a retention policy.

Testing
-------

The test settings use the immediate backend, so a test calls ``enqueue()`` and asserts on the returned ``TaskResult``::

    result = get_users_count.enqueue()
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == 3

An exception in the task does not propagate: the result ends up ``FAILED`` with the traceback in ``result.errors``. Django 6.0 does not reset the task backends when settings change, so prefer the test settings over overriding ``TASKS`` inside a test.

Relation to Celery
------------------

Django Tasks covers the common case: run a function later, outside the request. It has no scheduler, no retries and no monitoring UI. Generating the project with ``use_celery`` set to ``y`` adds Celery_ (a Redis broker, the beat scheduler and Flower) for workloads that need those; both can be used side by side, and ``users/tasks.py`` then contains both variants of the example.

.. _Tasks framework: https://docs.djangoproject.com/en/6.0/topics/tasks/
.. _django-tasks-db: https://github.com/RealOrangeOne/django-tasks-db
.. _Celery: https://docs.celeryq.dev
