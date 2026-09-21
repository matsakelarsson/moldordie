{%- set celery = cookiecutter.use_celery == 'y' -%}
"""The telemetry wiring: what starts the exporters, and what they are told.

No test here starts a real one. What ``configure`` installs is recorded instead,
because both halves install themselves in the process rather than in an object a test
can throw away: a tracer provider is set once and for all, and the Django
instrumentation writes a middleware into ``MIDDLEWARE``. Nothing dials out either:
the exporters are built, which opens no connection, and nothing records a span or a
measurement for them to post.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
{%- if celery %}
from celery.signals import beat_init
from celery.signals import worker_process_init
{%- endif %}
from django.apps import AppConfig
from opentelemetry import metrics
from opentelemetry import trace
{%- if celery %}
from opentelemetry.instrumentation.celery import CeleryInstrumentor
{%- endif %}
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

from {{ cookiecutter.project_slug }}.telemetry import apps
from {{ cookiecutter.project_slug }}.telemetry import configure as telemetry

APP = "{{ cookiecutter.project_slug }}.telemetry"
COMPONENT = "web"
ENDPOINT = "https://collector.example.com:4318"


@pytest.fixture
def exported(monkeypatch):
    """What ``configure`` installs, recorded rather than installed."""
    recorded = SimpleNamespace(tracer=None, meter=None, instrumented=[])

    def install_tracer(provider):
        recorded.tracer = provider

    def install_meter(provider):
        recorded.meter = provider

    def record(instrumentor, **kwargs):
        recorded.instrumented.append(type(instrumentor))

    monkeypatch.setattr(telemetry, "_started", {})
    monkeypatch.setattr(trace, "set_tracer_provider", install_tracer)
    monkeypatch.setattr(metrics, "set_meter_provider", install_meter)
    # The real instrumentations, asked and recorded: each of them would otherwise
    # wrap a library of this process for good
    for instrumentor in telemetry.INSTRUMENTORS:
        monkeypatch.setattr(instrumentor, "instrument", record)
    return recorded


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
    monkeypatch.delenv(telemetry.SEMANTIC_CONVENTIONS, raising=False)

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


def test_no_certificate_of_its_own_leaves_the_trust_store_of_the_container(settings):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = ENDPOINT
    settings.OTEL_EXPORTER_OTLP_CERTIFICATE = ""

    assert telemetry.connection("traces", settings)["certificate_file"] is None


def test_the_app_starts_nothing_unless_the_environment_names_a_component(monkeypatch):
    """ready() runs for every management command, and a command serves nothing."""
    started: list[str] = []
    monkeypatch.delenv(telemetry.COMPONENT_VARIABLE, raising=False)
    monkeypatch.setattr(apps, "configure", started.append)

    AppConfig.create(APP).ready()

    assert started == []


def test_the_app_starts_the_component_the_environment_names(monkeypatch):
    """The start script of a process that has no hook of its own names it here."""
    started: list[str] = []
    monkeypatch.setenv(telemetry.COMPONENT_VARIABLE, "taskworker")
    monkeypatch.setattr(apps, "configure", started.append)

    AppConfig.create(APP).ready()

    assert started == ["taskworker"]
{%- if celery %}


@pytest.fixture
def celery_starts(monkeypatch):
    """What the Celery signals start, recorded rather than started.

    ``config/celery_app.py`` calls ``configure`` through this module, so replacing it
    here is what its handlers see; the app's own ``ready`` holds a reference of its
    own and is patched where it is tested.
    """
    started: list[str] = []
    monkeypatch.setattr(telemetry, "configure", started.append)
    return started


def test_a_worker_process_starts_its_own_telemetry(celery_starts):
    """The prefork pool sends this in the child, which is where the exporters belong:
    their threads would not survive the fork out of the parent."""
    worker_process_init.send(sender=None)

    assert celery_starts == ["celeryworker"]


def test_the_scheduler_starts_its_own_telemetry(celery_starts):
    beat_init.send(sender=None)

    assert celery_starts == ["celerybeat"]
{%- endif %}
