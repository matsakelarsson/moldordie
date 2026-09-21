{%- set prometheus = cookiecutter.observability == 'prometheus' -%}
{%- set docker = cookiecutter.use_docker == 'y' -%}
"""Gunicorn's configuration, passed as ``--config {% if docker %}/app/{% endif %}config/gunicorn.py``.

Named by path rather than as a module, so Gunicorn executes this file and the master
process imports no part of the project to read it.
{% if prometheus %}
Each worker keeps its own metrics, so the exposition of one worker would describe a
quarter of the traffic. The Python client answers that with multiprocess mode: every
process writes its samples into ``PROMETHEUS_MULTIPROC_DIR`` and the exporter reads
all of them. {% if docker %}The directory belongs to one container and is emptied before Gunicorn
starts, in ``compose/production/django/start`` — the variable has to be set before
Python starts, because ``prometheus_client`` reads it when it is imported.{% else %}The directory belongs to one deployment of this project, and
whatever starts Gunicorn is what points the variable at it and empties it first. It
has to be set before Python starts, because ``prometheus_client`` reads it when it is
imported (``docs/observability.rst``).{% endif %}

Nothing here sets it, and nothing here requires it: a deployment that runs one worker,
or that has not configured the directory yet, serves every request as before and
exposes the metrics of whichever worker answered the scrape.
{%- else %}
A worker exports traces and metrics of its own, and it has to start doing so before it
loads the application: the Django instrumentation inserts a middleware into
``MIDDLEWARE``, and the handler reads that setting once, when it builds its chain.
``post_fork`` runs in the worker, after the fork and before the application is loaded,
which is the one moment where both hold (``docs/adr/0020``).

The arbiter starts nothing. It answers no request, and the exporters' threads would
not survive the fork into a worker anyway.
{%- endif %}
"""

{% if prometheus %}import os
{% endif %}from typing import Any
{% if prometheus %}
from prometheus_client import multiprocess

# Where the workers of one {% if docker %}container{% else %}deployment{% endif %} write their samples. The client reads this
# when it is imported, so whatever sets it has to be what starts the process.
MULTIPROCESS_DIRECTORY = "PROMETHEUS_MULTIPROC_DIR"


def on_starting(server: Any) -> None:
    """Say so where nothing pointed the workers at a directory to share.

    Gunicorn is starting and will serve either way: what is missing costs a scrape
    its other workers, which is worth one line in the log and is not worth refusing
    to start over. Said here because the arbiter says it once, rather than from the
    endpoint, which would say it to the scraper on every scrape.
    """
    if not os.environ.get(MULTIPROCESS_DIRECTORY):
        server.log.warning(
            "%s is not set, so each worker keeps metrics of its own and a scrape "
            "describes whichever worker answered it (docs/observability.rst)",
            MULTIPROCESS_DIRECTORY,
        )


def child_exit(server: Any, worker: Any) -> None:
    """Tell the client that a worker has exited.

    Gunicorn calls this in the arbiter, the only process that learns a worker is
    gone. ``mark_process_dead`` removes that worker's ``live`` gauge files and
    nothing else: its counters, histograms and its gauges of every other mode are kept
    on purpose, so a recycled worker's contributions stay in the container's totals.
    None of django-prometheus' gauges uses a ``live`` mode, so this hook removes no
    file today; it is what keeps a gauge this project adds later — a ``livesum`` of
    the connections a worker holds, say — from counting workers that have exited.

    Where no directory was configured there is nothing to retire, and the client
    would go looking for the variable itself and join a file name onto ``None``. This
    runs in the arbiter, where what that raises ends the whole deployment on the
    first worker to be recycled, so the question is asked here first.
    """
    if not os.environ.get(MULTIPROCESS_DIRECTORY):
        return
    # prometheus_client ships a py.typed marker but annotates this function with nothing
    multiprocess.mark_process_dead(worker.pid)  # type: ignore[no-untyped-call]
{%- else %}

def post_fork(server: Any, worker: Any) -> None:
    """Start this worker's exporters, in the worker and before it loads the application.

    Imported here rather than at the top of the file: the arbiter reads this
    configuration, and nothing of the project belongs in the process that never
    serves a request.
    """
    from {{ cookiecutter.project_slug }}.telemetry.configure import configure  # noqa: PLC0415

    configure("web")
{%- endif %}
