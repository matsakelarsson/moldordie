# {{cookiecutter.project_name}}

{{ cookiecutter.description }}

[![Built with moldordie](https://img.shields.io/badge/built%20with-moldordie-ff69b4.svg?logo=cookiecutter)](https://github.com/matsakelarsson/moldordie/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

{%- if cookiecutter.open_source_license != "Not open source" %}

License: {{cookiecutter.open_source_license}}
{%- endif %}

## Settings

Moved to [settings](https://github.com/matsakelarsson/moldordie/blob/main/docs/1-getting-started/settings.rst).

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:

      uv run python manage.py createsuperuser

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

    uv run coverage run -m pytest
    uv run coverage html
    open htmlcov/index.html

#### Running tests with pytest

    uv run pytest

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
`docs/frontend.rst` has the details; see also the
[frontend guide](https://github.com/matsakelarsson/moldordie/blob/main/docs/4-guides/frontend.rst).

### Background tasks

Background work goes through Django's Tasks framework; the example task lives in
`{{cookiecutter.project_slug}}/users/tasks.py`. Tasks run inline in development and in tests. In
production they are stored in PostgreSQL by django-tasks-db and executed by a worker process:
{%- if cookiecutter.use_docker == "y" %}

    docker compose -f docker-compose.production.yml up taskworker
{%- else %}

    uv run python manage.py db_worker
{%- endif %}

See the [tasks guide](https://github.com/matsakelarsson/moldordie/blob/main/docs/4-guides/tasks.rst).

{%- if cookiecutter.use_celery == "y" %}

### Celery

Celery sits next to the Tasks framework above, for the work that framework has no answer for: jobs on a schedule, jobs with a retry policy, and workflows. The example is `cache_users_count` in `{{cookiecutter.project_slug}}/users/tasks.py`, which retries itself on a transient database error and is meant to be scheduled under _Periodic Tasks_ in the admin. Work that needs neither a schedule nor retries belongs in a `django.tasks` task instead; the [tasks guide](https://github.com/matsakelarsson/moldordie/blob/main/docs/4-guides/tasks.rst) draws the line.

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
{%- if cookiecutter.mail_catcher == "Mailpit" %}

### Email Server

{%- if cookiecutter.use_docker == "y" %}

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailpit](https://github.com/axllent/mailpit) with a web interface is available as docker container.

Container mailpit will start automatically when you will run all docker containers.
Please check [moldordie Docker documentation](https://github.com/matsakelarsson/moldordie/blob/main/docs/2-local-development/developing-locally-docker.rst) for more details how to start all containers.

With Mailpit running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:8025`
{%- else %}

In development, it is often nice to be able to see emails that are being sent from your application. If you choose to use [Mailpit](https://github.com/axllent/mailpit) when generating the project a local SMTP server with a web interface will be available.

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
Please check [moldordie Docker documentation](https://github.com/matsakelarsson/moldordie/blob/main/docs/2-local-development/developing-locally-docker.rst) for more details how to start all containers.

With Mailtrap Local running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:3550`
{%- else %}

In development, it is often nice to be able to see emails that are being sent from your application. If you choose to use [Mailtrap Local](https://github.com/mailtrap/mailtrap-local) when generating the project a local SMTP server with a web interface will be available.

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

A scrape is a machine, so the endpoint takes a bearer token and never a session. Each deployed environment drew its own as `DJANGO_METRICS_TOKEN`, and an unset token refuses every request. Scraping a deployment means finding every replica rather than going through the proxy, which answers from one of them; `docs/observability.rst` has the scrape configuration and what Gunicorn's multiprocess mode changes.
{%- endif %}

## Deployment

The following details how to deploy this application.
{%- if cookiecutter.use_docker == "y" %}

### Docker

See detailed [moldordie Docker documentation](https://github.com/matsakelarsson/moldordie/blob/main/docs/3-deployment/deployment-with-docker.rst).

{%- endif %}

