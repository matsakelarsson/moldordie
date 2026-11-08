Deployment
======================================================================

{% if cookiecutter.use_docker == 'y' -%}
The deployed environments
----------------------------------------------------------------------

A change is promoted through three deployed environments. Each is a Compose file in the root of the project and a directory of env files:

.. list-table::
   :header-rows: 1

   * - Environment
     - Compose file
     - Env files
     - Host
   * - ``dev``
     - ``docker-compose.dev.yml``
     - ``.envs/.dev/``
     - ``dev.{{ cookiecutter.domain_name }}``
   * - ``test``
     - ``docker-compose.test.yml``
     - ``.envs/.test/``
     - ``test.{{ cookiecutter.domain_name }}``
   * - ``production``
     - ``docker-compose.production.yml``
     - ``.envs/.production/``
     - ``{{ cookiecutter.domain_name }}``

All three build their images from ``compose/production/`` and run ``config/settings/production.py``. They differ in their hosts, their secrets and their Docker volumes. The commands below use ``docker-compose.production.yml``. Point ``-f`` at another file, and edit that environment's env files, to run them against it.

The services
----------------------------------------------------------------------

* ``django``, the application behind Gunicorn.
* ``postgres``, the database.
* ``redis``, the cache{% if cookiecutter.use_celery == 'y' %} and Celery's broker{% endif %}.
* ``taskworker``, the worker of the Tasks framework. See :doc:`tasks`.
* ``traefik``, the reverse proxy, which serves HTTPS.
{%- if cookiecutter.use_celery == 'y' %}
* ``celeryworker`` and ``celerybeat``, Celery's worker and scheduler.
* ``flower``, which watches Celery. Traefik serves it over HTTPS on port 5555, with the ``CELERY_FLOWER_USER`` and ``CELERY_FLOWER_PASSWORD`` of the env file.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'None' %}
* ``nginx``, which serves the media files from the ``production_django_media`` volume. Keep that volume, because it holds the uploads.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' %}
* ``awscli``, for the database backups kept in S3.
{%- endif %}

Before the first deployment
----------------------------------------------------------------------

#. Commit ``uv.lock``, which the image build requires. :doc:`local-development` says how to write it.

#. Point the DNS records of the environment's host at the server. Traefik then obtains a certificate from Let's Encrypt and renews it.

#. Copy ``.envs/`` to the server. It holds each environment's secrets, so it is not in version control. ``.env.example`` lists what a deployment has to supply.

#. Fill in what ``.envs/.production/.django`` leaves empty. :doc:`settings` lists every variable.

   * ``DJANGO_SERVER_EMAIL``, the address errors are sent from.
{%- if cookiecutter.mail_service == 'Mailgun' %}
   * ``MAILGUN_API_KEY`` and ``MAILGUN_DOMAIN``. Without them, signing up fails with a server error when the project sends the verification email.
{%- elif cookiecutter.mail_service == 'Amazon SES' %}
   * AWS credentials that can send through Amazon SES. See `Anymail's Amazon SES page`_. Without them, signing up fails with a server error when the project sends the verification email.
{%- else %}
   * The SMTP server, as ``EMAIL_HOST`` and the settings around it in ``config/settings/production.py``, which reads none of them from the environment. Without it, signing up fails with a server error when the project sends the verification email.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' %}
   * ``DJANGO_AWS_ACCESS_KEY_ID``, ``DJANGO_AWS_SECRET_ACCESS_KEY`` and ``DJANGO_AWS_STORAGE_BUCKET_NAME``.
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}
   * ``SENTRY_DSN``.
{%- endif %}
{%- if cookiecutter.observability == 'opentelemetry' %}
   * ``OTEL_EXPORTER_OTLP_ENDPOINT``, the collector. See :doc:`observability`.
{%- endif %}
{%- if cookiecutter.identity_provider == 'entra' %}
   * ``ENTRA_TENANT_ID``, ``ENTRA_LOGIN_CLIENT_ID`` and ``ENTRA_LOGIN_CLIENT_SECRET``. See :doc:`authentication`.
{%- elif cookiecutter.identity_provider == 'google' %}
   * ``GOOGLE_LOGIN_CLIENT_ID`` and ``GOOGLE_LOGIN_CLIENT_SECRET``. See :doc:`authentication`.
{%- endif %}
{%- if cookiecutter.headless %}
   * ``DJANGO_FRONTEND_ORIGINS`` and ``DJANGO_FRONTEND_URL``, where the single-page application is served from.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' and cookiecutter.use_whitenoise == 'n' %}

#. Allow public reads of the ``static/`` prefix of the bucket, or the static files return 403. Keep the ``media/`` prefix private unless you want uploads public.
{%- endif %}

Deploy
----------------------------------------------------------------------

Build the images, apply the migrations and start the stack. Nothing applies migrations when a deployed container starts, so this step is yours on every release that has them. It also creates the tables of the task queue::

    docker compose -f docker-compose.production.yml build
    docker compose -f docker-compose.production.yml run --rm django python manage.py migrate
    docker compose -f docker-compose.production.yml up -d

The first time, create a superuser::

    docker compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser

The admin is at the path ``DJANGO_ADMIN_URL`` names in the env file.

Running the stack
----------------------------------------------------------------------

::

    docker compose -f docker-compose.production.yml ps
    docker compose -f docker-compose.production.yml logs
    docker compose -f docker-compose.production.yml run --rm django python manage.py shell
    docker compose -f docker-compose.production.yml up -d --scale django=4
    docker compose -f docker-compose.production.yml up -d --scale taskworker=2

Do not scale {% if cookiecutter.use_celery == 'y' %}``postgres``, ``traefik`` or ``celerybeat``{% else %}``postgres`` or ``traefik``{% endif %}.

To survive reboots, run ``docker compose -f docker-compose.production.yml up`` under a process manager such as systemd or Supervisor, from the root of the project.
{%- else -%}
This project does not choose how it is hosted. A server needs uv_, PostgreSQL_, Redis_ and a reverse proxy that terminates HTTPS and sets ``X-Forwarded-Proto``, which the settings trust to tell a secure request.

On Debian or Ubuntu, install the compiler and the libraries the dependencies build against::

    sudo utility/install_os_dependencies.sh install

Configure the environment
----------------------------------------------------------------------

The production variables are in ``.envs/.production/``, with their secrets generated. Those files are not in version control, so copy them to the server. ``.env.example`` lists what a deployment has to supply. Merge them into one ``.env`` file in the root of the project::

    python3 merge_production_dotenvs_in_dotenv.py

Then edit ``.env``. :doc:`settings` lists every variable.

* ``POSTGRES_HOST`` and ``REDIS_URL`` name the containers of a Compose stack. Point them at your servers.
* ``POSTGRES_DB``, ``POSTGRES_USER`` and ``POSTGRES_PASSWORD`` were generated. Create that role and that database on your PostgreSQL server, or set them to ones you have.
* ``DJANGO_SECURE_SSL_REDIRECT`` is ``False``. Set it to ``True`` unless your proxy redirects HTTP to HTTPS itself.
* ``DJANGO_SERVER_EMAIL`` is the address errors are sent from.
{%- if cookiecutter.mail_service == 'Mailgun' %}
* ``MAILGUN_API_KEY`` and ``MAILGUN_DOMAIN`` are empty. Without them, signing up fails with a server error when the project sends the verification email.
{%- elif cookiecutter.mail_service == 'Amazon SES' %}
* Provide AWS credentials that can send through Amazon SES. See `Anymail's Amazon SES page`_. Without them, signing up fails with a server error when the project sends the verification email.
{%- else %}
* The SMTP server is ``EMAIL_HOST`` and the settings around it in ``config/settings/production.py``, which reads none of them from the environment. Without it, signing up fails with a server error when the project sends the verification email.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' %}
* ``DJANGO_AWS_ACCESS_KEY_ID``, ``DJANGO_AWS_SECRET_ACCESS_KEY`` and ``DJANGO_AWS_STORAGE_BUCKET_NAME`` are empty.
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}
* ``SENTRY_DSN`` is empty.
{%- endif %}
{%- if cookiecutter.observability == 'opentelemetry' %}
* ``OTEL_EXPORTER_OTLP_ENDPOINT`` is empty. See :doc:`observability`.
{%- endif %}
{%- if cookiecutter.identity_provider == 'entra' %}
* ``ENTRA_TENANT_ID``, ``ENTRA_LOGIN_CLIENT_ID`` and ``ENTRA_LOGIN_CLIENT_SECRET`` are empty. See :doc:`authentication`.
{%- elif cookiecutter.identity_provider == 'google' %}
* ``GOOGLE_LOGIN_CLIENT_ID`` and ``GOOGLE_LOGIN_CLIENT_SECRET`` are empty. See :doc:`authentication`.
{%- endif %}
{%- if cookiecutter.headless %}
* ``DJANGO_FRONTEND_ORIGINS`` and ``DJANGO_FRONTEND_URL`` are empty. They say where the single-page application is served from.
{%- endif %}

Every command below needs these two variables in its environment::

    export DJANGO_READ_DOT_ENV_FILE=True
    export DJANGO_SETTINGS_MODULE=config.settings.production

Deploy
----------------------------------------------------------------------

Install what production needs, build the stylesheet, collect the static files and apply the migrations. ``uv.lock`` has to be committed for the first command::

    uv sync --locked --no-dev
    uv run --no-dev python manage.py tailwind build
    uv run --no-dev python manage.py collectstatic --noinput
    uv run --no-dev python manage.py migrate

The first time, create a superuser::

    uv run --no-dev python manage.py createsuperuser

The admin is at the path ``DJANGO_ADMIN_URL`` names in ``.env``.

The processes to keep running
----------------------------------------------------------------------

Run these under a process manager such as systemd or Supervisor, from the root of the project. Behind the proxy, the application serves on port 5000::

    uv run --no-dev gunicorn config.asgi --bind 127.0.0.1:5000 -k uvicorn_worker.UvicornWorker{% if cookiecutter.observability != 'none' %} --config config/gunicorn.py{% endif %}
    uv run --no-dev python manage.py db_worker
{%- if cookiecutter.use_celery == 'y' %}
    uv run --no-dev celery -A config.celery_app worker -l INFO
    uv run --no-dev celery -A config.celery_app beat -l INFO
{%- endif %}
{%- if cookiecutter.observability != 'none' %}

:doc:`observability` says what else starting Gunicorn has to do.
{%- endif %}

Static and media files
----------------------------------------------------------------------
{% if cookiecutter.use_whitenoise == 'y' %}
WhiteNoise serves the static files from the application.
{%- else %}
``collectstatic`` uploads the static files to the bucket. Allow public reads of its ``static/`` prefix, or the static files return 403. Keep the ``media/`` prefix private unless you want uploads public.
{%- endif %}
{%- if cookiecutter.cloud_provider == 'None' %} Uploads are written to ``{{ cookiecutter.project_slug }}/media/``. Have your web server serve that directory at ``/media/``, and back it up.
{%- elif cookiecutter.use_whitenoise == 'y' %} Uploads go to the bucket, under its ``media/`` prefix.
{%- endif %}
{%- endif %}
{%- if cookiecutter.mail_service == 'Amazon SES' %}

.. _Anymail's Amazon SES page: https://anymail.readthedocs.io/en/stable/esps/amazon_ses/
{%- endif %}
{%- if cookiecutter.use_docker == 'n' %}

.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _PostgreSQL: https://www.postgresql.org/download/
.. _Redis: https://redis.io/docs/latest/get-started/
{%- endif %}
