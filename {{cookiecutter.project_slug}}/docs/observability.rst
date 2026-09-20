.. _observability:

Observability
======================================================================

The project measures itself and exposes the result at ``/metrics`` in Prometheus'
exposition format: request counts and durations from the middlewares that wrap the
chain, connections, errors and query durations from the database backend, hits and
misses from the cache, and the writes of any model that asks for them. What reads and
stores those numbers is yours to run — this page describes what to point it at.

The credential
----------------------------------------------------------------------

A scrape is a machine, not a visitor, so the endpoint takes a bearer token and never a
session: no account, group or browser login decides whether a scrape succeeds, and a
deployment that configured no token has authorised nobody, so every request is refused.

Each deployed environment drew its own token when the project was generated, as
``DJANGO_METRICS_TOKEN`` in ``.envs/.<environment>/.django``; a token that reads ``dev``
therefore reads nothing else. The developer's machine declares a fixed value instead,
because nothing on it is worth protecting::

    curl -H "Authorization: Bearer $DJANGO_METRICS_TOKEN" http://localhost:8000/metrics

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
platform assigned — belongs in that list as well. A 400 from ``/metrics`` is always this;
a refused credential is 401.

**One container, one set of samples.** Gunicorn runs ``WEB_CONCURRENCY`` workers, each
with metrics of its own, so the client's multiprocess mode is what makes a single scrape
describe the container: ``compose/production/django/start`` points
``PROMETHEUS_MULTIPROC_DIR`` at a directory of that container, empties it before Gunicorn
starts, and ``config/gunicorn.py`` retires the samples of a worker that has exited.

That mode costs two things worth knowing. The process, platform and garbage-collection
collectors are not in the exposition, because each describes one process while the
exposition describes the container; read those from the container runtime instead. And a
gauge reports the sample of every live worker unless it is declared with a way to combine
them — counters, histograms and summaries add up on their own.

Other processes
----------------------------------------------------------------------

The task worker{% if cookiecutter.use_celery == 'y' %}, the Celery worker and beat{% endif %}
record the same database and cache metrics, but they serve no HTTP and so expose nothing.
Reading them means giving that container something to scrape; until then, what they do
shows up in the database and cache metrics of the queries they run.

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

Its own interface is at http://localhost:9090; ``compose/local/prometheus/prometheus.yml``
is the configuration it reads, and the target's health is the fastest way to see whether
the credential is right.
{%- else -%}
Set ``DJANGO_METRICS_TOKEN`` in the environment the development server runs in, then read
the endpoint with ``curl`` as above, or point a Prometheus of your own at
``localhost:8000``.
{%- endif %}
