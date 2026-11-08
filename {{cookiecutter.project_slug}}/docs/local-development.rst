Local development
======================================================================

{% if cookiecutter.use_docker == 'y' -%}
Prerequisites
----------------------------------------------------------------------

* `Docker`_ with the Compose plugin.
* `pre-commit`_, to run the checks before each commit.
* `just`_, if you want the shorter commands listed below.

Build the stack
----------------------------------------------------------------------

The first build takes a while. ``pyproject.toml`` pins the dependencies, but a new project has no lock file yet, so build the images, write the lock file inside a container, and build again so that the images install from it::

    docker compose -f docker-compose.local.yml build
    docker compose -f docker-compose.local.yml run --rm django uv lock
    docker compose -f docker-compose.local.yml build

Create the repository and install the hooks::

    git init
    pre-commit install

Commit ``uv.lock``, because the production image refuses to build without it.

Run the stack
----------------------------------------------------------------------

::

    docker compose -f docker-compose.local.yml up

This starts Django, PostgreSQL
{%- if cookiecutter.mail_catcher != 'None' %}, the mail catcher{% endif %}
{%- if cookiecutter.use_celery == 'y' %}, Redis, the Celery worker and beat, Flower{% endif %}
{%- if cookiecutter.observability == 'prometheus' %}, Prometheus{% elif cookiecutter.observability == 'opentelemetry' %}, the OpenTelemetry collector{% endif %} and the Tailwind watcher. The ``django`` service applies the migrations when it starts, and the site is at http://localhost:8000. Add ``-d`` to run in the background.

Setting ``COMPOSE_FILE`` lets you leave out ``-f``::

    export COMPOSE_FILE=docker-compose.local.yml
    docker compose up

With ``just`` installed, ``just up``, ``just down``, ``just logs django``, ``just manage migrate`` and ``just pytest`` do the same as the longer commands.

Management commands
----------------------------------------------------------------------

Run them in a one-off container of the ``django`` service::

    docker compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser

Environment variables
----------------------------------------------------------------------

``.envs/.local/.django`` and ``.envs/.local/.postgres`` hold the variables of the stack on your machine, and their credentials were generated with the project. Neither file is in version control, so copy them to a new checkout. :doc:`settings` lists every variable the settings read.

Adding a package
----------------------------------------------------------------------

``uv add`` inside a container changes only that container. Add the package to ``pyproject.toml`` instead, then update the lock file and rebuild::

    docker compose -f docker-compose.local.yml run --rm django uv lock
    docker compose -f docker-compose.local.yml build

Debugging
----------------------------------------------------------------------

To stop at an ``ipdb`` breakpoint, run the service with its ports published and attached to your terminal::

    docker compose -f docker-compose.local.yml run --rm --service-ports django

``config/settings/local.py`` adds the container's gateway to ``INTERNAL_IPS``, so django-debug-toolbar appears at http://localhost:8000. Reaching the site under another address means adding it to ``ALLOWED_HOSTS`` and ``INTERNAL_IPS`` there.

Email
----------------------------------------------------------------------

{% if cookiecutter.mail_catcher == 'Mailpit' -%}
Mailpit catches every email the project sends. Read them at http://127.0.0.1:8025.
{%- elif cookiecutter.mail_catcher == 'Mailtrap Local' -%}
Mailtrap Local catches every email the project sends. Read them at http://127.0.0.1:3550.
{%- else -%}
The project prints every email to the log of the ``django`` service.
{%- endif %}
{% if cookiecutter.use_celery == 'y' %}
Celery
----------------------------------------------------------------------

The ``celeryworker`` and ``celerybeat`` services start with the stack. Flower is at http://localhost:5555, with the ``CELERY_FLOWER_USER`` and ``CELERY_FLOWER_PASSWORD`` of ``.envs/.local/.django``. To queue the example task, open a shell and call it::

    docker compose -f docker-compose.local.yml run --rm django python manage.py shell
    >>> from {{ cookiecutter.project_slug }}.users.tasks import cache_users_count
    >>> cache_users_count.delay()
{% endif %}
{%- else -%}
Prerequisites
----------------------------------------------------------------------

* uv_, which installs the Python version named in ``.python-version``.
* PostgreSQL_.
{%- if cookiecutter.use_celery == 'y' %}
* Redis_, if you want tasks to go through a broker. See `Celery`_ below.
{%- endif %}

On Debian or Ubuntu, install the compiler and the libraries the dependencies build against::

    sudo utility/install_os_dependencies.sh install

The script reads the package list named after your release from ``utility/``, and stops if there is none. For a newer release, copy the nearest list to ``requirements-<codename>.apt``.

Set up the project
----------------------------------------------------------------------

#. Install the dependencies and the hooks::

    uv sync
    git init
    uv run pre-commit install

   ``pyproject.toml`` pins the dependencies, and this first ``uv sync`` writes ``uv.lock``. Commit it.

#. Create the database::

    createdb --username=postgres {{ cookiecutter.project_slug }}

   The first database on a machine may need the `PostgreSQL client authentication`_ configured first, to allow local connections and set a password for the ``postgres`` user.

#. Set the database variables::

    export POSTGRES_HOST=localhost
    export POSTGRES_USER=postgres
    export POSTGRES_PASSWORD=
    export POSTGRES_DB={{ cookiecutter.project_slug }}

   To avoid exporting them in each terminal, put them in a ``.env`` file in the root of the project and set ``DJANGO_READ_DOT_ENV_FILE=True`` in your shell. :doc:`settings` lists every variable the settings read.

#. Apply the migrations::

    uv run python manage.py migrate

Run the project
----------------------------------------------------------------------

Start the Tailwind watcher in a second terminal, with the same variables set, and leave it running. It builds ``{{ cookiecutter.project_slug }}/static/css/tailwind.css``, the stylesheet the pages load, and rebuilds it when a template changes::

    uv run python manage.py tailwind watch

Then serve the site at http://localhost:8000::

    uv run uvicorn config.asgi:application --host 0.0.0.0 --reload --reload-include '*.html' --reload-include '*.css' --timeout-graceful-shutdown 1

The page reloads itself when the server restarts. ``uv run python manage.py tailwind runserver`` starts Django's own server and the watcher together, but that server does not serve websockets.

Adding a package
----------------------------------------------------------------------

::

    uv add <package>

Email
----------------------------------------------------------------------

{% if cookiecutter.mail_catcher == 'Mailpit' -%}
Mailpit catches every email the project sends, once you start it. The Email Server section of ``README.md`` says how.
{%- elif cookiecutter.mail_catcher == 'Mailtrap Local' -%}
Mailtrap Local catches every email the project sends, once you start it. The Email Server section of ``README.md`` says how.
{%- else -%}
The project prints every email to the console of the server.
{%- endif %}
{% if cookiecutter.use_celery == 'y' %}
Celery
----------------------------------------------------------------------

``config/settings/local.py`` runs Celery tasks inline, so developing needs no broker. To send them through one, set ``CELERY_TASK_ALWAYS_EAGER = False`` there, then start Redis and a worker in terminals of their own::

    redis-server
    uv run celery -A config.celery_app worker --loglevel=info

To queue the example task, open a shell and call it::

    uv run python manage.py shell
    >>> from {{ cookiecutter.project_slug }}.users.tasks import cache_users_count
    >>> cache_users_count.delay()
{% endif %}
{%- endif %}

Background tasks
----------------------------------------------------------------------

Tasks run inline while developing, so no worker is needed. :doc:`tasks` has the details.
{% if cookiecutter.use_docker == 'y' %}
.. _Docker: https://docs.docker.com/get-docker/
.. _pre-commit: https://pre-commit.com/#install
.. _just: https://just.systems/
{%- else %}
.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _PostgreSQL: https://www.postgresql.org/download/
.. _PostgreSQL client authentication: https://www.postgresql.org/docs/current/client-authentication.html
{%- if cookiecutter.use_celery == 'y' %}
.. _Redis: https://redis.io/docs/latest/get-started/
{%- endif %}
{%- endif %}
