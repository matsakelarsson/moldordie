"""Gunicorn's configuration, passed as ``--config /app/config/gunicorn.py``.

Named by path rather than as a module, so Gunicorn executes this file and the master
process imports no part of the project to read it.

Each worker keeps its own metrics, so the exposition of one worker would describe a
quarter of the traffic. The Python client answers that with multiprocess mode: every
process writes its samples into ``PROMETHEUS_MULTIPROC_DIR`` and the exporter reads
all of them. The directory belongs to one container and is emptied before Gunicorn
starts, in ``compose/production/django/start`` — the variable has to be set before
Python starts, because ``prometheus_client`` reads it when it is imported.

What is left to do here is the other end of a worker's life: a worker that exits
leaves its samples behind, and nothing would ever retire them.
"""

from typing import Any

from prometheus_client import multiprocess


def child_exit(server: Any, worker: Any) -> None:
    """Retire the samples of a worker that has exited.

    Gunicorn calls this in the arbiter, which is the only process that learns a
    worker is gone; without it a recycled or crashed worker's counters would be
    served for the life of the container.
    """
    # prometheus_client ships a py.typed marker but annotates this function with nothing
    multiprocess.mark_process_dead(worker.pid)  # type: ignore[no-untyped-call]
