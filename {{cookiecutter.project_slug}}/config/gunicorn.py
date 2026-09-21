{%- set prometheus = cookiecutter.observability == 'prometheus' -%}
"""Gunicorn's configuration, passed as ``--config /app/config/gunicorn.py``.

Named by path rather than as a module, so Gunicorn executes this file and the master
process imports no part of the project to read it.
{% if prometheus %}
Each worker keeps its own metrics, so the exposition of one worker would describe a
quarter of the traffic. The Python client answers that with multiprocess mode: every
process writes its samples into ``PROMETHEUS_MULTIPROC_DIR`` and the exporter reads
all of them. The directory belongs to one container and is emptied before Gunicorn
starts, in ``compose/production/django/start`` — the variable has to be set before
Python starts, because ``prometheus_client`` reads it when it is imported.

What is left to do here is the other end of a worker's life. A worker that exits
leaves its samples behind, which is what keeps the container's counters whole; only
a gauge declared with one of the ``live`` multiprocess modes has to forget it.
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

from typing import Any
{% if prometheus %}
from prometheus_client import multiprocess


def child_exit(server: Any, worker: Any) -> None:
    """Tell the client that a worker has exited.

    Gunicorn calls this in the arbiter, the only process that learns a worker is
    gone. ``mark_process_dead`` removes that worker's ``live`` gauge files and
    nothing else: its counters, histograms and its gauges of every other mode are kept
    on purpose, so a recycled worker's contributions stay in the container's totals.
    None of django-prometheus' gauges uses a ``live`` mode, so this hook removes no
    file today; it is what keeps a gauge this project adds later — a ``livesum`` of
    the connections a worker holds, say — from counting workers that have exited.
    """
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
