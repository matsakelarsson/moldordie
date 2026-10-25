{%- set celery = cookiecutter.use_celery == 'y' -%}
"""The telemetry wiring: what starts the exporters, and what they are told.

No test here starts a real one. What ``configure`` installs is recorded instead,
because both halves install themselves in the process rather than in an object a test
can throw away: a tracer provider is set once and for all, and the Django
instrumentation writes a middleware into ``MIDDLEWARE``. Nothing dials out either:
the exporters are built, which opens no connection, and nothing records a span or a
measurement for them to post.

Everything else is done as the process does it. An entry point is driven the way its
process drives it and read back through ``started``, so how each of them reaches
``configure`` is its own business; a shutdown is watched on ``Exporters`` of the
test's own, around providers that record what they are asked instead of exporting.
"""

from __future__ import annotations

import asyncio
import os
import time
from functools import partial
from types import SimpleNamespace

import pytest
{%- if celery %}
from celery.signals import beat_init
from celery.signals import worker_process_init
from celery.signals import worker_process_shutdown
{%- endif %}
from django.apps import AppConfig
from opentelemetry import metrics
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
{%- if celery %}
from opentelemetry.instrumentation.celery import CeleryInstrumentor
{%- endif %}
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

from config import gunicorn

from {{ cookiecutter.project_slug }}.telemetry import COMPONENT_VARIABLE
from {{ cookiecutter.project_slug }}.telemetry import asgi
from {{ cookiecutter.project_slug }}.telemetry import configure as telemetry

APP = "{{ cookiecutter.project_slug }}.telemetry"
COMPONENT = "web"
ENDPOINT = "https://collector.example.com:4318"


@pytest.fixture
def exported(monkeypatch):
    """What ``configure`` installs, recorded rather than installed.

    The process's own exporters are what ``configure`` starts, and they are stopped
    on the way out as a process stops them. Which is also why this begins on a process
    that exports nothing: the suite names no collector, and a test that left the
    exporters started would be a defect of its own.
    """
    assert telemetry.started() is None
    recorded = SimpleNamespace(tracer=None, meter=None, instrumented=[])

    def install_tracer(provider):
        recorded.tracer = provider

    def install_meter(provider):
        recorded.meter = provider

    def record(instrumentor, **kwargs):
        recorded.instrumented.append(type(instrumentor))

    monkeypatch.setattr(trace, "set_tracer_provider", install_tracer)
    monkeypatch.setattr(metrics, "set_meter_provider", install_meter)
    # The real instrumentations, asked and recorded: each of them would otherwise
    # wrap a library of this process for good
    for instrumentor in telemetry.INSTRUMENTORS:
        monkeypatch.setattr(instrumentor, "instrument", record)
    yield recorded
    # Installing them is recorded rather than done, but building them is real: each
    # provider holds a thread and an atexit hook that would outlive this test
    telemetry.shutdown()


def test_a_serving_process_exports_its_traces_and_its_metrics(settings, exported):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT

    assert telemetry.configure(COMPONENT) is True

    assert telemetry.started() == COMPONENT
    assert exported.tracer is not None
    assert exported.meter is not None


def test_the_instrumented_libraries_are_the_ones_the_project_uses(settings, exported):
    """Each of them is something this project actually talks to; nothing else is
    instrumented, because an instrumentation costs a dependency to keep current."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT

    telemetry.configure(COMPONENT)

    assert set(exported.instrumented) == {
        DjangoInstrumentor,
        PsycopgInstrumentor,
        RedisInstrumentor,
{%- if celery %}
        CeleryInstrumentor,
{%- endif %}
    }


def test_the_stable_conventions_are_what_it_speaks(
    settings,
    exported,
    monkeypatch,
):
    """The instrumentations emit the older attribute names unless told otherwise, and
    a project generated today has no dashboard that reads those."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    # Set before it is removed: monkeypatch records no undo for a name that was not
    # there, and configure sets this one, which would then outlive the test
    monkeypatch.setenv(telemetry.SEMANTIC_CONVENTIONS, "")
    monkeypatch.delenv(telemetry.SEMANTIC_CONVENTIONS)

    telemetry.configure(COMPONENT)

    assert os.environ[telemetry.SEMANTIC_CONVENTIONS] == telemetry.STABLE_CONVENTIONS


def test_a_deployment_may_choose_the_conventions_itself(
    settings,
    exported,
    monkeypatch,
):
    """Emitting both is how a deployment moves dashboards that read the old names."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    monkeypatch.setenv(telemetry.SEMANTIC_CONVENTIONS, "http/dup,database/dup")

    telemetry.configure(COMPONENT)

    assert os.environ[telemetry.SEMANTIC_CONVENTIONS] == "http/dup,database/dup"


def test_nothing_is_exported_without_a_destination(settings, exported):
    """Which is what keeps a checkout, a command and this suite dialling nowhere."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ""

    assert telemetry.configure(COMPONENT) is False

    assert telemetry.started() is None
    assert exported.tracer is None
    assert exported.meter is None
    assert exported.instrumented == []


def test_a_process_that_exports_already_starts_nothing_more(settings, exported):
    """A second set of providers would be installed nowhere and export nothing."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    telemetry.configure(COMPONENT)
    installed = exported.tracer

    assert telemetry.configure("taskworker") is False

    assert telemetry.started() == COMPONENT
    assert exported.tracer is installed


def test_the_resource_says_what_reported(settings):
    settings.OTEL_SERVICE_NAME = "the-service"
    settings.OTEL_DEPLOYMENT_ENVIRONMENT = "dev"

    attributes = telemetry.resource(COMPONENT, settings).attributes

    assert attributes[telemetry.SERVICE_NAME] == "the-service"
    assert attributes[telemetry.DEPLOYMENT_ENVIRONMENT] == "dev"
    assert attributes[telemetry.SERVICE_INSTANCE_ID] == telemetry.instance_id(COMPONENT)


def test_every_process_reports_as_an_instance_of_its_own():
    """A deployment runs several components, each in several processes, under one
    service name; without this their measurements would be read as one process's."""
    assert telemetry.instance_id("web") != telemetry.instance_id("taskworker")
    assert str(os.getpid()) in telemetry.instance_id("web")


def test_each_signal_is_posted_to_the_path_the_protocol_gives_it(settings):
    """The configured address is the base one, as the specification defines it."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = f"{ENDPOINT}/"

    traces = telemetry.connection("traces", settings)
    measurements = telemetry.connection("metrics", settings)

    assert traces["endpoint"] == f"{ENDPOINT}/v1/traces"
    assert measurements["endpoint"] == f"{ENDPOINT}/v1/metrics"


def test_the_collector_is_told_what_it_asks_of_a_caller(settings):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    settings.OTEL_EXPORTER_OTLP_HEADERS = {"authorization": "Bearer the-credential"}
    settings.OTEL_EXPORTER_OTLP_CERTIFICATE = "/etc/ssl/certs/collector-ca.crt"

    connection = telemetry.connection("traces", settings)

    assert connection["headers"] == settings.OTEL_EXPORTER_OTLP_HEADERS
    assert connection["certificate_file"] == settings.OTEL_EXPORTER_OTLP_CERTIFICATE


def test_no_certificate_of_its_own_verifies_against_the_trusted_authorities(settings):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    settings.OTEL_EXPORTER_OTLP_CERTIFICATE = ""

    assert telemetry.connection("traces", settings)["certificate_file"] is True


def test_an_empty_certificate_in_the_environment_still_verifies(settings, monkeypatch):
    """What the exporter is told has to be what it uses.

    Anything falsy sends it to the environment for an answer of its own, and what it
    reads there is the variable this setting is read from. A deployment that writes
    ``OTEL_EXPORTER_OTLP_CERTIFICATE=`` — the same empty idiom the env file uses for
    the endpoint — would otherwise post to the collector, with whatever credential
    ``OTEL_EXPORTER_OTLP_HEADERS`` carries, over a connection it never verified.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_CERTIFICATE", "")
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    settings.OTEL_EXPORTER_OTLP_CERTIFICATE = ""

    exporter = OTLPSpanExporter(**telemetry.connection("traces", settings))

    # What the exporter hands requests as ``verify``, and it exposes it nowhere
    # else. Anything falsy there is what selects ``CERT_NONE``, so the property
    # this asserts is the one that decides, rather than the value carrying it:
    # the exporter is annotated as taking a path, and True is not one.
    assert exporter._certificate_file  # noqa: SLF001


class Recording:
    """A provider that records being flushed and stopped, and exports nothing."""

    def __init__(self):
        self.calls = []

    def force_flush(self, timeout_millis=None):
        self.calls.append(("force_flush", timeout_millis))

    def shutdown(self, timeout_millis=None):
        self.calls.append(("shutdown", timeout_millis))


class Blocking:
    """A provider whose flush does not come back inside anyone's deadline."""

    def __init__(self, seconds):
        self.seconds = seconds

    def force_flush(self, timeout_millis=None):
        time.sleep(self.seconds)

    def shutdown(self, timeout_millis=None):
        time.sleep(self.seconds)


REFUSED = "the collector refused the connection"


class Raising:
    """A provider that cannot send what it is holding, and says so by raising.

    The SDK does: a meter provider collects its readers' errors and re-raises them as
    one, and an exporter over HTTP raises whatever the connection did.
    """

    def __init__(self):
        self.calls = []

    def force_flush(self, timeout_millis=None):
        self.calls.append(("force_flush", timeout_millis))
        raise RuntimeError(REFUSED)

    def shutdown(self, timeout_millis=None):
        self.calls.append(("shutdown", timeout_millis))
        raise RuntimeError(REFUSED)


def holding(tracing, metering):
    """Exporters of a test's own, started on providers that export nothing."""
    exporters = telemetry.Exporters()
    exporters.start(COMPONENT, tracing, metering)
    return exporters


async def unreachable(scope, receive, send):
    """The wrapped application, which no lifespan message may reach."""
    raise AssertionError(scope)


async def nothing(*args):
    """A receive or send the scopes that pass through are never asked for."""


def drive_lifespan(application, messages):
    """Send ``messages`` to ``application``'s lifespan; return what it sent back."""

    async def driven():
        sent = []
        incoming = iter(messages)

        async def receive():
            return next(incoming)

        async def send(message):
            sent.append(message)

        await application({"type": "lifespan"}, receive, send)
        return sent

    return asyncio.run(driven())


def test_a_stopping_process_sends_what_it_is_holding():
    """Up to a batch of spans and an interval of measurements have been recorded and
    not sent; a process that is stopped would otherwise take them with it."""
    tracing, metering = Recording(), Recording()
    exporters = holding(tracing, metering)

    exporters.shutdown()

    assert ("force_flush", telemetry.SHUTDOWN_TIMEOUT_MILLIS) in tracing.calls
    assert ("shutdown", None) in tracing.calls
    assert ("shutdown", telemetry.SHUTDOWN_TIMEOUT_MILLIS) in metering.calls
    assert exporters.component is None


def test_stopping_twice_sends_nothing_the_second_time():
    tracing = Recording()
    exporters = holding(tracing, Recording())
    exporters.shutdown()
    sent = list(tracing.calls)

    exporters.shutdown()

    assert tracing.calls == sent


def test_a_process_that_started_nothing_has_nothing_to_send(settings, exported):
    """Which is every process of a project that named no collector: nothing was
    installed, so there is nothing to flush and nothing to say about it."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ""

    assert telemetry.configure(COMPONENT) is False

    telemetry.shutdown()
    assert exported.tracer is None
    assert exported.instrumented == []
    assert telemetry.started() is None


def test_the_server_lifespan_sends_what_the_worker_is_holding(settings, exported):
    """A web worker is ended by a signal its server re-raises once it has stopped
    serving, so this is the last thing it runs and the last time the exporters are
    reachable. The wrapper is built as ``config/asgi.py`` builds it, on the process's
    own exporters, started as a worker starts them."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    telemetry.configure(COMPONENT)

    sent = drive_lifespan(
        asgi.flushing_on_shutdown(unreachable),
        [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}],
    )

    assert [message["type"] for message in sent] == [
        "lifespan.startup.complete",
        "lifespan.shutdown.complete",
    ]
    assert telemetry.started() is None


# A deadline short enough to be missed on purpose, and a flush that will not meet it
DEADLINE = 0.05
BLOCKED = 1.0


def test_a_flush_that_overruns_does_not_hold_the_worker():
    """What the deadline has to bound is the time the process takes, not the time the
    coroutine waits: a thread cannot be cancelled, and the loop joins the threads it
    started before ``asyncio.run`` returns. So this is timed rather than asked whether
    the shutdown was answered — the worker is held for exactly as long as this is.

    The wrapper is handed the flush, as ``config/asgi.py`` leaves it the process's,
    under a deadline short enough to be missed on purpose.
    """
    blocked = Blocking(BLOCKED)
    exporters = holding(blocked, blocked)

    started = time.monotonic()
    sent = drive_lifespan(
        asgi.flushing_on_shutdown(
            unreachable,
            flush=partial(exporters.flush, DEADLINE),
        ),
        [{"type": "lifespan.shutdown"}],
    )
    held = time.monotonic() - started

    assert [message["type"] for message in sent] == ["lifespan.shutdown.complete"]
    assert held < BLOCKED


def test_a_flush_says_whether_it_finished():
    """What the deadline costs is what was still unsent when it passed, so a process
    that gave up on one has something to say that a process that did not has not."""
    blocked = Blocking(BLOCKED)

    assert holding(blocked, blocked).flush(DEADLINE) is False
    assert holding(Recording(), Recording()).flush(DEADLINE) is True


def test_a_signal_that_cannot_be_sent_does_not_take_the_other_with_it():
    """The two are stopped independently: an interval of measurements would otherwise
    be lost to a flush of spans that raised, and nothing would be left to try from."""
    tracing, metering = Raising(), Recording()
    exporters = holding(tracing, metering)

    exporters.shutdown()

    assert ("force_flush", telemetry.SHUTDOWN_TIMEOUT_MILLIS) in tracing.calls
    assert ("shutdown", telemetry.SHUTDOWN_TIMEOUT_MILLIS) in metering.calls
    assert exporters.component is None


def test_a_shutdown_that_cannot_send_still_answers_the_server():
    """The server is in the middle of stopping and is waiting on this answer. Told
    that the shutdown failed, uvicorn reports the protocol as unsupported and the
    worker as having failed to stop, for a flush that no one was waiting for."""
    exporters = holding(Raising(), Raising())

    sent = drive_lifespan(
        asgi.flushing_on_shutdown(unreachable, flush=exporters.flush),
        [{"type": "lifespan.shutdown"}],
    )

    assert [message["type"] for message in sent] == ["lifespan.shutdown.complete"]


def test_every_other_scope_reaches_the_application():
    """The wrapper answers the lifespan and is otherwise not in the way."""
    seen = []

    async def application(scope, receive, send):
        seen.append(scope["type"])

    async def served():
        wrapped = asgi.flushing_on_shutdown(application)
        await wrapped({"type": "http"}, nothing, nothing)

    asyncio.run(served())

    assert seen == ["http"]


def test_the_app_starts_nothing_unless_the_environment_names_a_component(
    settings,
    exported,
    monkeypatch,
):
    """ready() runs for every management command, and a command serves nothing. With
    a collector named, so that starting would have shown."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    monkeypatch.delenv(COMPONENT_VARIABLE, raising=False)

    AppConfig.create(APP).ready()

    assert telemetry.started() is None


def test_the_app_starts_the_component_the_environment_names(
    settings,
    exported,
    monkeypatch,
):
    """The start script of a process that has no hook of its own names it here."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    monkeypatch.setenv(COMPONENT_VARIABLE, "taskworker")

    AppConfig.create(APP).ready()

    assert telemetry.started() == "taskworker"


def test_a_web_worker_starts_from_the_hook_the_server_calls_after_the_fork(
    settings,
    exported,
):
    """Gunicorn executes ``config/gunicorn.py`` by path and calls this in the worker,
    before it loads the application; it is driven here as the module it also is."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT

    gunicorn.post_fork(server=None, worker=None)

    assert telemetry.started() == "web"
{%- if celery %}


def test_a_worker_process_starts_its_own_telemetry(settings, exported):
    """The prefork pool sends this in the child, which is where the exporters belong:
    their threads would not survive the fork out of the parent."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT

    worker_process_init.send(sender=None)

    assert telemetry.started() == "celeryworker"


def test_the_scheduler_starts_its_own_telemetry(settings, exported):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT

    beat_init.send(sender=None)

    assert telemetry.started() == "celerybeat"


def test_a_worker_process_sends_what_it_holds_before_the_pool_ends_it(
    settings,
    exported,
):
    """The pool ends its children itself, so this is where a worker's last spans and
    measurements go — under the deadline, because the pool waits for this handler."""
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    worker_process_init.send(sender=None)

    worker_process_shutdown.send(sender=None)

    assert telemetry.started() is None
{%- endif %}
