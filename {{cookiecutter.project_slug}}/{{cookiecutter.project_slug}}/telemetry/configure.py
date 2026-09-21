{%- set celery = cookiecutter.use_celery == 'y' -%}
"""Traces and metrics over OTLP, started in each process that serves something.

Importing this module starts nothing. ``configure`` does, and it is called from the
entry point of every serving process and from nowhere else: Gunicorn's ``post_fork``
hook in ``config/gunicorn.py``,{% if celery %} the Celery signals in ``config/celery_app.py``,{% endif %}
and ``TelemetryConfig.ready`` where the environment names a component, which the start
script of a serving process does and no other command.

``ready`` runs for every management command, so starting the exporters there for every
process would give ``migrate``, ``collectstatic``, ``shell`` and the test runner
exporters of their own{% if celery %}, and under Celery's prefork pool it runs in the parent, before
the fork, where the batching processor's thread does not survive{% endif %} (``docs/adr/0020``).

Nothing is exported until a deployment names a destination: with no endpoint
configured, ``configure`` installs no provider and instruments no library at all.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from functools import partial
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

from django.conf import settings
from opentelemetry import metrics
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
{%- if celery %}
from opentelemetry.instrumentation.celery import CeleryInstrumentor
{%- endif %}
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# What tells an app registry that this process serves something. A start script sets
# it for the processes that have no hook of their own to start from.
COMPONENT_VARIABLE = "DJANGO_TELEMETRY_COMPONENT"

# The semantic conventions the instrumentations speak. They read this variable when
# they are asked to instrument, and emit the older attribute names without it; a
# project generated today has no dashboard reading those, so it starts on the stable
# ones. A deployment moving dashboards that do sets "http/dup,database/dup" in its env
# file, which emits both, and is free to set anything else.
SEMANTIC_CONVENTIONS = "OTEL_SEMCONV_STABILITY_OPT_IN"
STABLE_CONVENTIONS = "http,database"

# What the resource says this process is, under the names the specification gives
SERVICE_NAME = "service.name"
SERVICE_INSTANCE_ID = "service.instance.id"
DEPLOYMENT_ENVIRONMENT = "deployment.environment.name"

# How long a shutdown waits for the exporters. A flush to a collector that is there
# takes milliseconds; one to a collector that is not must not hold a deployment up,
# so it is bounded here rather than left at the SDK's thirty seconds. The whole of a
# shutdown is bounded by the same figure, because what the SDK is given is what it
# tries for rather than what it takes (``flush``).
SHUTDOWN_TIMEOUT_MILLIS = 5000
MILLISECONDS = 1000
SHUTDOWN_TIMEOUT_SECONDS = SHUTDOWN_TIMEOUT_MILLIS / MILLISECONDS

# What this process started, once ``configure`` has: the component it exports as and
# the two providers ``shutdown`` flushes. Each entry point above is the only one in
# its process, so this records rather than guards — until an environment names a
# component to a process that starts from a hook as well, where a second set of
# exporters would export through neither.
_started: dict[str, Any] = {}

# The libraries this project talks to, each instrumented by the package that knows
# it. Their common base excludes itself from type checking, so it cannot be named as
# the element type here.
INSTRUMENTORS: tuple[type[Any], ...] = (
    # The request span and the request duration. It inserts a middleware into
    # MIDDLEWARE, so it has to run before the handler builds the chain from it,
    # which is what decides where each entry point below sits
    DjangoInstrumentor,
    # The queries, through the driver rather than through Django's backend, so the
    # ones a management command or a task runs are measured too
    PsycopgInstrumentor,
    RedisInstrumentor,
{%- if celery %}
    # The task span, linked to the request that enqueued the task
    CeleryInstrumentor,
{%- endif %}
)


class TelemetrySettings(Protocol):
    """The settings this module reads; ``config/settings/base.py`` defines them."""

    OTEL_SERVICE_NAME: str
    OTEL_DEPLOYMENT_ENVIRONMENT: str
    OTEL_EXPORTER_OTLP_ENDPOINT: str
    OTEL_EXPORTER_OTLP_HEADERS: dict[str, str]
    OTEL_EXPORTER_OTLP_CERTIFICATE: str


def started() -> str | None:
    """The component this process exports as, or None while it exports nothing."""
    return _started.get("component")


def instance_id(component: str) -> str:
    """What tells this process apart from the others exporting under one service name.

    A deployment runs several containers of several components, each with workers of
    its own, and they all report as one service; without this they would arrive as one
    instance and their measurements would be read as one process's.
    """
    return f"{component}-{socket.gethostname()}-{os.getpid()}"


def resource(component: str, telemetry_settings: TelemetrySettings) -> Resource:
    """What every span and every measurement this process exports is attributed to."""
    return Resource.create(
        {
            SERVICE_NAME: telemetry_settings.OTEL_SERVICE_NAME,
            SERVICE_INSTANCE_ID: instance_id(component),
            DEPLOYMENT_ENVIRONMENT: telemetry_settings.OTEL_DEPLOYMENT_ENVIRONMENT,
        },
    )


def connection(signal: str, telemetry_settings: TelemetrySettings) -> dict[str, Any]:
    """How an exporter reaches the collector for ``signal``: traces, or metrics.

    Each signal has a path of its own under the configured base address, which is the
    one the OTLP specification defines. The exporters would read the same variables
    from the environment themselves; they are told instead, so that what they post to
    is what the settings say and a reader of the settings has the whole answer.
    """
    base = telemetry_settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    return {
        "endpoint": f"{base}/v1/{signal}",
        "headers": dict(telemetry_settings.OTEL_EXPORTER_OTLP_HEADERS),
        # No certificate of a deployment's own verifies against the authorities the
        # image already trusts. True rather than None, because anything falsy sends
        # the exporter to the environment for an answer of its own, and an empty
        # OTEL_EXPORTER_OTLP_CERTIFICATE — the variable this setting is read from —
        # arrives at requests as verify="", which turns verification off entirely.
        "certificate_file": telemetry_settings.OTEL_EXPORTER_OTLP_CERTIFICATE or True,
    }


def tracer_provider(
    component: str,
    telemetry_settings: TelemetrySettings,
) -> TracerProvider:
    """A provider that batches this process's spans and posts them to the collector."""
    provider = TracerProvider(resource=resource(component, telemetry_settings))
    exporter = OTLPSpanExporter(**connection("traces", telemetry_settings))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def meter_provider(
    component: str,
    telemetry_settings: TelemetrySettings,
) -> MeterProvider:
    """A provider that posts this process's measurements on a schedule of its own."""
    exporter = OTLPMetricExporter(**connection("metrics", telemetry_settings))
    return MeterProvider(
        resource=resource(component, telemetry_settings),
        metric_readers=[PeriodicExportingMetricReader(exporter)],
    )


def configure(component: str) -> bool:
    """Start this process exporting as ``component``; False when it started nothing.

    A process with no endpoint to export to starts nothing, which is what keeps a
    checkout, the test suite and every management command from dialling anywhere. A
    process that has already started starts nothing either: a second set of providers
    would be installed nowhere, and its exporters would post what nothing records.
    """
    telemetry_settings: TelemetrySettings = settings
    if started() is not None or not telemetry_settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return False
    tracing = tracer_provider(component, telemetry_settings)
    metering = meter_provider(component, telemetry_settings)
    _started.update(component=component, tracing=tracing, metering=metering)
    trace.set_tracer_provider(tracing)
    metrics.set_meter_provider(metering)
    # Read by the first instrumentation to be asked, and once for the process
    os.environ.setdefault(SEMANTIC_CONVENTIONS, STABLE_CONVENTIONS)
    for instrumentor in INSTRUMENTORS:
        instrumentor().instrument()
    return True


def stop(signal: str, step: Callable[[], object]) -> None:
    """Take one step of a shutdown, saying rather than raising what went wrong.

    Everything that calls ``shutdown`` is on its way out of the process, and one step
    failing is not a reason to leave the rest of them undone. A signal that could not
    be sent is also not a failed shutdown: what waits on the answer is a server, and
    what it would do with the exception is fail the stop it is in the middle of.
    """
    try:
        step()
    # Nothing above this is in a position to handle what an exporter raises
    except Exception:
        logger.warning("Telemetry could not stop exporting %s", signal, exc_info=True)


def shutdown() -> None:
    """Send what this process is holding, and stop its exporters.

    A process that is stopped has recorded up to a batch of spans and an interval of
    measurements that nothing has sent yet. Every process that can reach this calls
    it on its way out; a web worker reaches it from the server's lifespan, which is
    the last thing it runs (``telemetry/asgi.py``). Starting nothing means holding
    nothing, so this does nothing where ``configure`` did.

    Each signal is stopped on its own, and what this process started is forgotten only
    once both have been: an interval of measurements would otherwise be lost to a
    flush of spans that raised, with nothing left to try it again from.
    """
    tracing: TracerProvider | None = _started.get("tracing")
    metering: MeterProvider | None = _started.get("metering")
    try:
        if tracing is not None:
            stop("traces", partial(tracing.force_flush, SHUTDOWN_TIMEOUT_MILLIS))
            stop("traces", tracing.shutdown)
        if metering is not None:
            stop("metrics", partial(metering.shutdown, SHUTDOWN_TIMEOUT_MILLIS))
    finally:
        _started.clear()


def flush(timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> bool:
    """Run ``shutdown`` under a deadline this process can keep; False if it overran.

    What the SDK is given is what it tries for, not what it takes: a batch processor
    joins its worker thread while the exporter behind it retries with a backoff of
    its own, and the documented timeouts are best-effort. So the deadline that decides
    how long a process takes to go is kept here, where nothing inside it can overrun.

    A flush that is given up on is left running rather than cancelled, because a
    thread cannot be cancelled. It is a daemon, so the interpreter does not wait for
    it either: what is still unsent at the deadline stays unsent, which is the trade
    this deadline exists to make.
    """
    flushing = threading.Thread(
        target=shutdown,
        name="telemetry-shutdown",
        daemon=True,
    )
    flushing.start()
    flushing.join(timeout)
    if flushing.is_alive():
        logger.warning("Telemetry was not flushed within %ss of shutdown", timeout)
        return False
    return True
