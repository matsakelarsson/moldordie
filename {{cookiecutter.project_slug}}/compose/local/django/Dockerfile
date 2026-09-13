# define an alias for the specific python version used in this file.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS python

# Python build stage
FROM python AS python-build-stage

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

# we need to move the virtualenv outside of the $APP_HOME directory because it will be overriden by the docker compose mount
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg dependencies
  libpq-dev \
  gettext \
  wait-for-it

# Requirements are installed here to ensure they will be cached.
# A freshly generated project has no lock file yet, and ``uv.loc[k]`` matches one only
# once ``uv sync`` has written it, so the build works either way.
COPY pyproject.toml uv.loc[k] ${APP_HOME}/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project

COPY . ${APP_HOME}

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

ENV PATH="/${APP_HOME}/.venv/bin:$PATH"
ENV PYTHONPATH="${APP_HOME}/.venv/lib/python3.14/site-packages:$PYTHONPATH"

COPY --chmod=0755 ./compose/production/django/entrypoint /entrypoint

COPY --chmod=0755 ./compose/local/django/start /start

{% if cookiecutter.use_celery == "y" %}
COPY --chmod=0755 ./compose/local/django/celery/worker/start /start-celeryworker

COPY --chmod=0755 ./compose/local/django/celery/beat/start /start-celerybeat

COPY --chmod=0755 ./compose/local/django/celery/flower/start /start-flower
{% endif %}

ENTRYPOINT ["/entrypoint"]
