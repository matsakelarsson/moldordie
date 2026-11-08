# {{cookiecutter.project_name}}

{{ cookiecutter.description }}

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

{%- if cookiecutter.open_source_license != "Not open source" %}

License: {{cookiecutter.open_source_license}}
{%- endif %}

## Getting started
{%- if cookiecutter.use_docker == "y" %}

You need [Docker](https://docs.docker.com/get-docker/) with the Compose plugin. Build the images, write the lock file, and build again so that the images install from it:

    docker compose -f docker-compose.local.yml build
    docker compose -f docker-compose.local.yml run --rm django uv lock
    docker compose -f docker-compose.local.yml build

Commit `uv.lock`, then start the stack. It applies the migrations and serves the site at <http://localhost:8000>:

    docker compose -f docker-compose.local.yml up
{%- else %}

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and [PostgreSQL](https://www.postgresql.org/download/). On Debian or Ubuntu, install the compiler and the libraries the dependencies build against:

    sudo utility/install_os_dependencies.sh install

Install the dependencies, create the database and apply the migrations, then commit the `uv.lock` the first command writes:

    uv sync
    createdb --username=postgres {{ cookiecutter.project_slug }}
    export POSTGRES_HOST=localhost POSTGRES_USER=postgres POSTGRES_PASSWORD= POSTGRES_DB={{ cookiecutter.project_slug }}
    uv run python manage.py migrate

Start the Tailwind watcher in a second terminal, with the same variables set, and leave it running:

    uv run python manage.py tailwind watch

Then serve the site at <http://localhost:8000>:

    uv run uvicorn config.asgi:application --host 0.0.0.0 --reload --reload-include '*.html' --reload-include '*.css' --timeout-graceful-shutdown 1
{%- endif %}

`docs/local-development.rst` has the rest.

## Settings

The settings are in `config/settings/`: `base.py` holds what every environment shares, and `local.py`, `test.py` and `production.py` hold what differs. `docs/settings.rst` lists every variable they read.

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:
{%- if cookiecutter.use_docker == "y" %}

      docker compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser
{%- else %}

      uv run python manage.py createsuperuser
{%- endif %}

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Type checks

The project is type checked with mypy in strict mode. Run it from the project root:
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.local.yml run --rm django mypy .
{%- else %}

    uv run mypy .
{%- endif %}

The same check runs before every `git push` through pre-commit, and in CI. Shared request types live in `{{cookiecutter.project_slug}}/typedefs.py`.

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.local.yml run --rm django coverage run -m pytest
    docker compose -f docker-compose.local.yml run --rm django coverage html
    open htmlcov/index.html
{%- else %}

    uv run coverage run -m pytest
    uv run coverage html
    open htmlcov/index.html
{%- endif %}

#### Running tests with pytest
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.local.yml run --rm django pytest
{%- else %}

    uv run pytest
{%- endif %}

### Adding an app

The project's own `startapp` copies a complete app into `{{cookiecutter.project_slug}}/` under
the name you give, with its model called what `--model` says:
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.local.yml run --rm django python manage.py startapp blog --model Post
{%- else %}

    uv run python manage.py startapp blog --model Post
{%- endif %}

The copy holds the model with its first migration and its admin, a form, the list, detail,
create, update and delete views, each answering htmx with a partial of its template, the
templates, a factory and the tests of all of it
{%- if cookiecutter.rest_api != "None" %}, and the model's routes on the REST API{% endif %}.
The command prints where to register the app; once registered, the app's tests pass, and
you replace the model's fields with your own. The app template it copies is
`{{cookiecutter.project_slug}}/scaffold/app_template/`, checked by the same tools as the
rest of the project, so an addition to it reaches every app created after.

### Frontend

The frontend is server-rendered Django templates enhanced with [htmx](https://htmx.org) (via
[django-htmx](https://django-htmx.readthedocs.io)) and styled with
[Tailwind CSS](https://tailwindcss.com) and [daisyUI](https://daisyui.com) through
[django-tailwind-cli](https://django-tailwind-cli.readthedocs.io), which runs Tailwind's
standalone CLI: there is no Node.js toolchain, and the project ships no JavaScript of its own.

The stylesheet the pages load, `{{cookiecutter.project_slug}}/static/css/tailwind.css`, is built
from `{{cookiecutter.project_slug}}/styles/main.css` and from the class names in the templates,
and is not committed: a page without styles means it has not been built yet. Keep the watcher
running while you work,
{%- if cookiecutter.use_docker == 'y' %} which the `tailwind` service of `docker-compose.local.yml` does once the stack is up
(`just logs tailwind` follows it; `just manage tailwind build` builds once).
{%- else %} in a second terminal next to the server:

    uv run python manage.py tailwind watch

`uv run python manage.py tailwind build` builds it once, minified, which a deployment does before
`collectstatic`.
{%- endif %} The first run downloads the Tailwind CLI into `.django_tailwind_cli/`.

To change the look, edit the project's own theme in
`{{cookiecutter.project_slug}}/styles/theme.css`: every colour, radius and size daisyUI reads is
written out there. Every theme daisyUI ships is enabled as well, and the navigation's theme picker
keeps a visitor's choice in a cookie, through htmx and without a script. The examples page, `/examples/`,
shows the components and the htmx patterns at work, each with its template as written: it is starter
content, and `docs/frontend.rst` says how to delete it. htmx fragments are Django template partials, and every response carries a
nonce-based Content Security Policy, so templates must not contain inline scripts or styles.
`docs/frontend.rst` has the details.

### Background tasks

Background work goes through Django's Tasks framework; the example task lives in
`{{cookiecutter.project_slug}}/users/tasks.py`. Tasks run inline in development and in tests. In
production they are stored in PostgreSQL by django-tasks-db and executed by a worker process:
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.production.yml up taskworker
{%- else %}

    uv run python manage.py db_worker
{%- endif %}

`docs/tasks.rst` says how to define, enqueue and test a task.

{%- if cookiecutter.use_celery == "y" %}

### Celery

Celery sits next to the Tasks framework above, for the work that framework has no answer for: jobs on a schedule, jobs with a retry policy, and workflows. The example is `cache_users_count` in `{{cookiecutter.project_slug}}/users/tasks.py`, which retries itself on a transient database error and is meant to be scheduled under _Periodic Tasks_ in the admin. Work that needs neither a schedule nor retries belongs in a `django.tasks` task instead.
{%- if cookiecutter.use_docker == "y" %}

The `celeryworker` and `celerybeat` services of `docker-compose.local.yml` start with the stack. To follow the worker:

    docker compose -f docker-compose.local.yml logs -f celeryworker

Flower is at <http://localhost:5555>, with the `CELERY_FLOWER_USER` and `CELERY_FLOWER_PASSWORD` of `.envs/.local/.django`.
{%- else %}

Please note: for Celery's import magic to work, it is important _where_ the celery commands are run. Run them from the project root, the folder holding _manage.py_.

To run a celery worker:

```bash
uv run celery -A config.celery_app worker -l info
```

To run [periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html), you'll need to start the celery beat scheduler service. You can start it as a standalone process:

```bash
uv run celery -A config.celery_app beat
```

or you can embed the beat service inside a worker with the `-B` option (not recommended for production use):

```bash
uv run celery -A config.celery_app worker -B -l info
```
{%- endif %}

{%- endif %}
{%- if cookiecutter.mail_catcher == "Mailpit" %}

### Email Server

{%- if cookiecutter.use_docker == "y" %}

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailpit](https://github.com/axllent/mailpit) with a web interface is available as docker container.

Container mailpit will start automatically when you will run all docker containers.
Start them with `docker compose -f docker-compose.local.yml up`.

With Mailpit running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:8025`
{%- else %}

In development, it is often nice to be able to see emails that are being sent from your application. [Mailpit](https://github.com/axllent/mailpit) is a local SMTP server with a web interface for that.

1.  [Download the latest Mailpit release](https://github.com/axllent/mailpit/releases) for your OS.

2.  Copy the binary file to the project root.

3.  Make it executable:

        chmod +x mailpit

4.  Spin up another terminal window and start it there:

        ./mailpit

5.  Check out <http://127.0.0.1:8025/> to see how it goes.

Now you have your own mail server running locally, ready to receive whatever you send it.

{%- endif %}

{%- endif %}
{%- if cookiecutter.mail_catcher == "Mailtrap Local" %}

### Email Server

{%- if cookiecutter.use_docker == "y" %}

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailtrap Local](https://github.com/mailtrap/mailtrap-local) with a web interface is available as docker container.

Container mailtrap-local will start automatically when you will run all docker containers.
Start them with `docker compose -f docker-compose.local.yml up`.

With Mailtrap Local running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:3550`
{%- else %}

In development, it is often nice to be able to see emails that are being sent from your application. [Mailtrap Local](https://github.com/mailtrap/mailtrap-local) is a local SMTP server with a web interface for that.

1.  [Download the latest Mailtrap Local release](https://github.com/mailtrap/mailtrap-local/releases) for your OS.

2.  Copy the binary file to the project root.

3.  Make it executable:

        chmod +x mailtrap-local

4.  Spin up another terminal window and start it there:

        ./mailtrap-local

5.  Check out <http://127.0.0.1:3550/> to see how it goes.

Now you have your own mail server running locally, ready to receive whatever you send it.

{%- endif %}

{%- endif %}
{%- if cookiecutter.use_sentry == "y" %}

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/> or download and host it yourself.
The system is set up with reasonable defaults: unhandled exceptions are captured through the Django integration, and log records of level `ERROR` and above are sent as events. The SDK is initialised from the `SENTRY_*` settings in `config/settings/production.py` by the `{{ cookiecutter.project_slug }}.sentry` app once Django's app registry is ready.

You must set the DSN url in production.
{%- endif %}
{%- if cookiecutter.observability == "prometheus" %}

### Metrics

The application measures itself with [django-prometheus](https://github.com/django-commons/django-prometheus) and exposes the result at `/metrics`: requests, database connections and queries, and cache hits and misses.

A scrape is a machine, so the endpoint takes a bearer token and never a session. Each deployed environment drew its own as `DJANGO_METRICS_TOKEN`{% if cookiecutter.identity_provider != 'none' %}; a scraper the identity provider issues tokens to presents one of those instead, its registration holding the `identity.read_metrics` permission, so a deployment whose scrapers have an identity there can leave the drawn token unset{% else %}, and an unset token refuses every request{% endif %}. Scraping a deployment means finding every replica rather than going through the proxy, which answers from one of them; `docs/observability.rst` has the scrape configuration and what Gunicorn's multiprocess mode changes.
{%- endif %}
{%- if cookiecutter.observability == "opentelemetry" %}

### Telemetry

The application exports traces and metrics over OTLP with [OpenTelemetry](https://opentelemetry.io/docs/languages/python/): a span for every request and for every query it makes to PostgreSQL and to Redis{% if cookiecutter.use_celery == 'y' %}, and one for every Celery task{% endif %}.

Nothing is exported until `OTEL_EXPORTER_OTLP_ENDPOINT` names a collector, so a checkout, a management command and the test suite dial nowhere. The exporters start in each process that serves something and in no other, and send what they are holding when it stops{% if cookiecutter.use_docker == 'y' %}; the local Compose file runs a collector that prints what arrives{% endif %}. `docs/observability.rst` has the collector's configuration and where each process starts.
{%- endif %}

## Deployment
{%- if cookiecutter.use_docker == "y" %}

Each deployed environment, `dev`, `test` and `production`, is a Compose file in the root of the project with its env files under `.envs/`. Before the first deployment, commit `uv.lock`, point the host's DNS records at the server so that Traefik can obtain a certificate, copy `.envs/` to the server, and fill in what its `.django` file leaves empty.

Then build the images, apply the migrations and start the stack. For the first deployment, also create a superuser:

    docker compose -f docker-compose.production.yml build
    docker compose -f docker-compose.production.yml run --rm django python manage.py migrate
    docker compose -f docker-compose.production.yml up -d
    docker compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser

Point `-f` at another environment's file to deploy that one.
{%- else %}

The project does not choose how it is hosted. A server needs uv, PostgreSQL, Redis and a reverse proxy that terminates HTTPS. With the production environment set, install, build the stylesheet, collect the static files and apply the migrations:

    uv sync --locked --no-dev
    uv run --no-dev python manage.py tailwind build
    uv run --no-dev python manage.py collectstatic --noinput
    uv run --no-dev python manage.py migrate
{%- endif %}

`docs/deployment.rst` has the details, including what the environment must set and what to keep running.

