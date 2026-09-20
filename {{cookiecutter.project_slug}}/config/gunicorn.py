"""Gunicorn's configuration, passed as ``--config /app/config/gunicorn.py``.

Named by path rather than as a module, so Gunicorn executes this file and the master
process imports no part of the project to read it.

Each worker keeps its own metrics, so the exposition of one worker would describe a
quarter of the traffic. The Python client answers that with multiprocess mode: every
process writes its samples into ``PROMETHEUS_MULTIPROC_DIR`` and the exporter reads
all of them. The directory belongs to one container and is emptied before Gunicorn
starts, in ``compose/production/django/start`` — the variable has to be set before
Python starts, because ``prometheus_client`` reads it when it is imported.

What is left to do here is the other end of a worker's life. A worker that exits
leaves its samples behind, which is what keeps the container's counters whole; only
a gauge declared with one of the ``live`` multiprocess modes has to forget it.
"""

from typing import Any

from prometheus_client import multiprocess


def child_exit(server: Any, worker: Any) -> None:
    """Tell the client that a worker has exited.

    Gunicorn calls this in the arbiter, the only process that learns a worker is
    gone. ``mark_process_dead`` removes that worker's ``live`` gauge files and
    nothing else: its counters, histograms and ordinary gauges are kept on purpose,
    so a recycled worker's contributions stay in the container's totals. The metrics
    django-prometheus declares are counters and histograms, so this retires nothing
    today; it is what keeps a gauge this project adds later — a ``livesum`` of the
    connections a worker holds, say — from counting workers that no longer exist.
    """
    # prometheus_client ships a py.typed marker but annotates this function with nothing
    multiprocess.mark_process_dead(worker.pid)  # type: ignore[no-untyped-call]
