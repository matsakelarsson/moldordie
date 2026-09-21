{%- set prometheus = cookiecutter.observability == 'prometheus' -%}
{%- set celery = cookiecutter.use_celery == 'y' -%}
{#- The scraper a provider issues tokens to: an arm of the metrics page alone. #}
{%- set service_tokens = prometheus and cookiecutter.identity_provider != 'none' -%}
{%- set entra = cookiecutter.identity_provider == 'entra' -%}
.. _observability:

Observability
======================================================================
{% if prometheus %}
The project measures itself and exposes the result at ``/metrics`` in Prometheus'
exposition format: request counts and durations from the middlewares that wrap the
chain, connections, errors and query durations from the database backend, hits and
misses from the cache, and the writes of any model that asks for them. What reads and
stores those numbers is yours to run — this page describes what to point it at.

The credential
----------------------------------------------------------------------

A scrape is a machine, not a visitor, so the endpoint takes a bearer token and never a
session: no account, group or browser login decides whether a scrape succeeds.
{% if service_tokens -%}
Two credentials are accepted and the token itself says which it is, so a deployment
picks either and needs no scrape to hold both.
{%- else -%}
A deployment that configured no token has authorised nobody, so every request is
refused.
{%- endif %}

Each deployed environment drew its own token when the project was generated, as
``DJANGO_METRICS_TOKEN`` in ``.envs/.<environment>/.django``; a token that reads ``dev``
therefore reads nothing else. The developer's machine declares a value that is the same
in every checkout, so the local scrape configuration beside it can name it; it is a
development value and not a secret, which is also why the local Prometheus is published
to the loopback interface alone::

    curl -H "Authorization: Bearer $DJANGO_METRICS_TOKEN" http://localhost:8000/metrics
{% if service_tokens %}
A scraper the provider knows
----------------------------------------------------------------------

A deployment whose scraper has an identity at {% if entra %}the tenant{% else %}Google{% endif %} needs no drawn token at
all. Register the scraper as a calling service and grant its registration the
``identity.read_metrics`` permission in the admin (:ref:`authentication`): a registered
service without that permission is refused with ``403``, because a service the provider
vouches for is not by that alone a service this project lets read its metrics.
{% if entra %}
Prometheus obtains its own tokens from the client credentials of the scraper's app
registration:

.. code-block:: yaml

    scrape_configs:
      - job_name: {{ cookiecutter.project_slug }}
        metrics_path: /metrics
        oauth2:
          client_id: <the scraper's application (client) id>
          client_secret_file: /etc/prometheus/scraper-secret
          token_url: https://login.microsoftonline.com/<tenant id>/oauth2/v2.0/token
          scopes:
            - api://<this application's id>/.default
        static_configs:
          - targets: ['django:5000']
{% else %}
Google's identity tokens last an hour and Prometheus mints none of its own, so the
token has to reach it as a file it re-reads (``authorization.credentials_file``), kept
fresh by whatever runs beside it: the metadata server on an instance the service
account is attached to, a sidecar, a periodic job. Where that is more machinery than a
drawn token is worth, use ``DJANGO_METRICS_TOKEN`` instead.
{% endif %}
Neither credential falls back to the other: a token naming a configured issuer is
verified and never compared with ``DJANGO_METRICS_TOKEN``, and anything else is only
compared with it. A deployment that authorises its scrapers as services can leave that
variable empty, and one that has no service identities can leave the registrations so.
{% endif %}
Scraping a deployment
----------------------------------------------------------------------

Two properties of the deployed stack decide what the scrape configuration looks like,
and a third decides whether the scrape is answered at all.

**Scrape the application, not the proxy in front of it.** The application can run as
several containers behind Traefik (``docker compose -f docker-compose.production.yml up
--scale django=4``), and a scrape that arrives through the proxy describes whichever
replica answered it: the numbers would jump between scrapes and none of them would be the
whole picture. Point the scraper at the application's own address instead — with one
container, that is the Compose service:

.. code-block:: yaml

    scrape_configs:
      - job_name: {{ cookiecutter.project_slug }}
        metrics_path: /metrics
        authorization:
          credentials_file: /etc/prometheus/metrics-token
        static_configs:
          - targets: ['django:5000']

**The address it dials has to be one the application answers to.** Django refuses a
request whose ``Host`` is not in ``ALLOWED_HOSTS``, before any view runs and with 400,
so each deployed environment's ``DJANGO_ALLOWED_HOSTS`` names ``django`` beside the site's
own domain. Scraping several replicas means addressing each of them, so whatever the
service discovery yields — the names you gave the containers, or the addresses the
platform assigned — belongs in that list as well. A refused credential is 401, so on a
400 check ``ALLOWED_HOSTS`` and the ``django.security.DisallowedHost`` log first; Django
answers 400 to other malformed requests too.

**One container, one set of samples.** Gunicorn runs ``WEB_CONCURRENCY`` workers, each
with metrics of its own, so the client's multiprocess mode is what makes a single scrape
describe the container: ``compose/production/django/start`` points
``PROMETHEUS_MULTIPROC_DIR`` at a directory of that container and empties it before
Gunicorn starts. A worker that exits leaves its samples behind, which is what keeps the
container's counters whole across a recycled worker; ``config/gunicorn.py`` tells the
client about the exit so that a gauge declared with one of the ``live`` multiprocess
modes stops counting it. None of django-prometheus' own gauges is declared that way,
so that hook removes no file until the project adds one that is.

That mode costs two things worth knowing. The process, platform and garbage-collection
collectors are not in the exposition, because each describes one process while the
exposition describes the container; read those from the container runtime instead. And a
gauge exposes a sample per process by default, processes that have exited included; only
the ``live`` modes leave those out, and only those are what ``config/gunicorn.py`` can
retire. Counters, histograms and summaries add up on their own.

Other processes
----------------------------------------------------------------------

The task worker{% if cookiecutter.use_celery == 'y' %}, the Celery worker and beat{% endif %}
record the same database and cache metrics, in their own processes, and serve no HTTP.
Nothing collects them: they are not in the web container's exposition, and the queries
those processes run appear in no scrape. Measuring them means giving those containers
something a scrape can read, which this project does not generate.

Measuring a model
----------------------------------------------------------------------

A model can count its own writes by mixing in django-prometheus' model mixin, which adds
insert, update and delete counters labelled with the name given::

    from django_prometheus.models import ExportModelOperationsMixin


    class Order(ExportModelOperationsMixin("order"), models.Model):
        ...

While developing
----------------------------------------------------------------------

{% if cookiecutter.use_docker == 'y' -%}
The local Compose file runs a Prometheus that scrapes the application with the
development token::

    docker compose -f docker-compose.local.yml up prometheus

Its own interface is at http://localhost:9090, published to this machine only, because
it asks for no credential of its own and would otherwise hand out the metrics the
application refuses without one. ``compose/local/prometheus/prometheus.yml`` is the
configuration it reads, and the target's health is the fastest way to see whether the
credential is right.
{%- else -%}
Set ``DJANGO_METRICS_TOKEN`` in the environment the development server runs in, then read
the endpoint with ``curl`` as above, or point a Prometheus of your own at
``localhost:8000``.
{%- endif %}
{%- else %}
The project exports traces and metrics over OTLP: a span for every request and for
every query it makes to PostgreSQL and to Redis{% if celery %}, and one for every Celery task{% endif %}, with
the durations and the counts that go with them. What receives, stores and shows them
is yours to run — this page describes what the application sends and what to point it
at.

Nothing is exported until a destination is named
----------------------------------------------------------------------

``OTEL_EXPORTER_OTLP_ENDPOINT`` is the collector's base address, and while it is unset
the project starts no exporter and instruments no library: a checkout, a management
command and the test suite dial nowhere. Each deployed environment names its own in
``.envs/.<environment>/.django``, next to ``OTEL_DEPLOYMENT_ENVIRONMENT``, which says
which deployment a span came from — all three run one settings module, so their env
files are where they differ.

Two more variables describe the connection, both commented out until a deployment
needs them. ``OTEL_EXPORTER_OTLP_HEADERS`` is what the collector asks a caller for,
written as comma-separated ``name=value`` pairs. ``OTEL_EXPORTER_OTLP_CERTIFICATE`` is
the authority that signed the collector's own certificate, where that is a private
one: it is the trust anchor for the connection this project opens, and has nothing to
do with the certificate the site is served under.

The exporters post over HTTP, to the path the protocol gives each signal:
``/v1/traces`` and ``/v1/metrics`` under the configured address. They are told what
the settings say rather than left to read the environment themselves, so
``config/settings/base.py`` is the whole answer to where this project exports.

Every span is exported as things stand. The SDK reads ``OTEL_TRACES_SAMPLER`` and
``OTEL_TRACES_SAMPLER_ARG`` from the environment itself, so a deployment that cannot
afford one span per request sets them in its env file and needs no change here::

    OTEL_TRACES_SAMPLER=parentbased_traceidratio
    OTEL_TRACES_SAMPLER_ARG=0.05

Which processes export, and where each starts
----------------------------------------------------------------------

Every process that serves something, and no other. ``AppConfig.ready`` runs for every
management command, so a project that started its exporters there would give
``migrate``, ``collectstatic``, ``shell`` and the test runner exporters of their own.
{% if celery %}Under Celery's prefork pool it would be worse than wasteful: ``ready`` runs in the
parent, before the fork, and the exporters' threads do not survive it.
{% endif %}Each process is started from its own entry point instead (``docs/adr/0020``):

* the Gunicorn workers, from the ``post_fork`` hook in ``config/gunicorn.py``. It runs
  in the worker, after the fork and before the worker loads the application, which is
  the one moment where both conditions hold: the Django instrumentation inserts a
  middleware into ``MIDDLEWARE``, and the handler reads that setting once, when it
  builds its chain;
{%- if celery %}
* the Celery worker processes, from ``worker_process_init``, and the scheduler from
  ``beat_init``, both in ``config/celery_app.py``. That signal belongs to the prefork
  pool, which is the one the generated start script runs;
{%- endif %}
* the task worker and the development server, from ``TelemetryConfig.ready``, because
  ``DJANGO_TELEMETRY_COMPONENT`` names the component in their start scripts. A
  management command is told nothing, and so starts nothing.

Each process reports as an instance of its own, ``<component>-<hostname>-<pid>``,
under one service name. A deployment runs several containers of several components,
each with workers of its own; without that they would arrive as one instance and be
read as one process.

The worker processes export as much as the web ones do. Their queries and their tasks
are spans like any other, which is the difference from a scrape of an HTTP endpoint:
nothing has to be reachable for a process to be measured.

What is instrumented
----------------------------------------------------------------------

The libraries this project talks to, and no others: Django, psycopg and redis{% if celery %}, and
Celery{% endif %}. They are the ``INSTRUMENTORS`` tuple in
``{{ cookiecutter.project_slug }}/telemetry/configure.py``; adding one means pinning its
instrumentation package and naming it there. Nothing instruments an HTTP client,
because the project makes no outgoing request of its own.

The queries are instrumented through the driver rather than through Django's database
backend, so the ones a management command{% if celery %} or a task{% endif %} runs are measured too.

An incoming call from another service already continues that service's trace: the
Django instrumentation reads the ``traceparent`` header off the request and makes the
request span a child of the span that made the call. The outgoing half is the one this
project does not have, because it makes no HTTP call of its own. A service that calls
another one pins the instrumentation of the client it uses —
``opentelemetry-instrumentation-httpx`` or ``-requests`` — and names it in
``INSTRUMENTORS``; that is what writes the header the other side reads. Until then a
call this project makes starts a second trace on the other side rather than continuing
this one.

The attribute names are the stable semantic conventions: ``http.request.method`` and
``http.response.status_code`` on a request, ``db.system.name`` and ``db.query.text``
on a query, and ``http.server.request.duration`` in seconds for the metric. The
instrumentations emit the older names unless ``OTEL_SEMCONV_STABILITY_OPT_IN`` says
otherwise, so ``telemetry/configure.py`` sets it before it instruments anything; a
deployment whose dashboards still read the old names sets
``OTEL_SEMCONV_STABILITY_OPT_IN=http/dup,database/dup`` in its env file, which emits
both while they move.

Logs stay on standard output, where the container runtime collects them. Exporting
them over OTLP is a separate change: the logs SDK is still provisional, and a log line
is worth more with a trace id in it than in a second pipeline.

A span of your own
----------------------------------------------------------------------

Anything the instrumentations do not cover is a span you open::

    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)


    def reconcile(order):
        with tracer.start_as_current_span("reconcile") as span:
            span.set_attribute("order.id", str(order.pk))
            ...

``get_tracer`` returns a tracer that does nothing while no provider is installed, so
this costs nothing in a checkout, in a management command or in the tests.

While developing
----------------------------------------------------------------------

{% if cookiecutter.use_docker == 'y' -%}
The local Compose file runs a collector that prints what arrives::

    docker compose -f docker-compose.local.yml logs -f otel-collector

``.envs/.local/.django`` points the application at it and
``compose/local/otel-collector/config.yml`` is the configuration it reads: an OTLP
receiver and a debug exporter, so nothing leaves this machine and nothing is kept. It
publishes no port, because the application reaches it by service name.

A request that produces no span means the exporters never started: the development
server starts them from ``DJANGO_TELEMETRY_COMPONENT``, which ``compose/local/django/start``
sets, so a command run with ``just manage`` exports nothing on purpose.
{%- else -%}
Run a collector of your own and set ``OTEL_EXPORTER_OTLP_ENDPOINT`` to its address in
the environment the development server runs in, together with
``DJANGO_TELEMETRY_COMPONENT=web``, which is what tells the app registry that this
process serves something. Without that variable a ``runserver`` exports nothing, for
the same reason ``migrate`` does not.
{%- endif %}

Collecting a deployment
----------------------------------------------------------------------

The application posts to one address; what stands there is the deployment's to choose.
A collector between the application and wherever the data is stored is the usual
arrangement, because it is where a deployment puts what it does not want in the
application: the credentials of the store, the sampling it can afford, and the
batching. A collector of its own also means the application's exporters talk to
something on the same network, which is the connection it is easiest to secure.

.. code-block:: yaml

    receivers:
      otlp:
        protocols:
          http:
            endpoint: 0.0.0.0:4318
            tls:
              cert_file: /etc/otelcol/collector.crt
              key_file: /etc/otelcol/collector.key
            auth:
              authenticator: bearertokenauth

    extensions:
      # In the contrib distribution; this is the other side of
      # OTEL_EXPORTER_OTLP_HEADERS
      bearertokenauth:
        scheme: Bearer
        token: ${env:COLLECTOR_TOKEN}

    processors:
      batch: {}

    exporters:
      otlphttp:
        endpoint: https://where-you-keep-it.example.com

    service:
      extensions: [bearertokenauth]
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlphttp]
        metrics:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlphttp]

The application then reads::

    OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.internal.example.com:4318
    OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer the-collectors-credential
    OTEL_EXPORTER_OTLP_CERTIFICATE=/etc/ssl/certs/collector-ca.crt

Scaling the application changes nothing about this. The exporters push, so a new
container is a new instance that starts reporting on its own, and nothing has to
discover it.

When the collector is down
----------------------------------------------------------------------

Nothing the application serves changes. The exporters run on threads of their own, so
a request never waits for one: with the collector refusing connections this project
answers in the time it takes without telemetry. A batch is retried with a growing
backoff and then abandoned with one line at ``ERROR``; the queue is bounded and drops
what it cannot hold rather than growing; and exporting resumes by itself when the
collector comes back, with no restart.

So read the log first when nothing arrives. A refused connection, a ``401`` and a
certificate that does not verify each say plainly which of the three variables is
wrong. Silence with nothing in the log is the other case, and means no exporter was
started at all: either the endpoint is unset in that environment's env file, or the
process was never meant to export — a management command, or a serving process whose
start script names no component.

What a restart loses
----------------------------------------------------------------------

A web worker that is stopped loses what it has buffered: up to one batch of spans and
up to one interval of measurements. Gunicorn's uvicorn worker re-raises the signal it
was sent once it has stopped serving, which ends the process before Gunicorn's own
exit hooks or the SDK's ``atexit`` flush can run. A process that exits normally — the
task worker, a management command that opened spans of its own — does flush.

Both windows are the SDK's own and are read from the environment, so a deployment that
cannot afford them shortens them in its env file::

    OTEL_BSP_SCHEDULE_DELAY=2000      # milliseconds between exports of a span batch
    OTEL_METRIC_EXPORT_INTERVAL=15000

A restart therefore costs the last seconds before it and nothing else. What was
already exported is at the collector, and the process that comes up is a new instance
whose counters start from zero there.
{%- endif %}
