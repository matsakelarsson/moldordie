# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

Instructions for AI coding agents working in this repository. `README.md` is where people start;
this file holds what an agent needs on top of it: how the project was generated, what is wired
up, the commands that run here, and the conventions the code and its tests enforce.

## Generation choices

Generated from [moldordie](https://github.com/matsakelarsson/moldordie) with the answers below.
They record how this tree was built; nothing reads them at runtime, so editing the table changes
nothing.

| Option | Answer |
| ------ | ------ |
{%- for name in option_names("list", "flag") %}
| `{{ name }}` | `{{ cookiecutter[name] }}` |
{%- endfor %}

Generation then deleted every file those answers did not call for, so what is absent is absent on
purpose: if an app, a setting or a dependency is not in the tree, this project was generated
without it. Add it deliberately — pin it, wire it up, test it — rather than assuming a default is
already there.

## The stack

- Django 6.0 on Python 3.14 (3.12 and later are supported), PostgreSQL {{ cookiecutter.postgresql_version }} and Redis
- Served over ASGI: Uvicorn in development, Gunicorn with a Uvicorn worker in production
- Settings split into `base.py`, `local.py`, `test.py` and `production.py` under
  `config/settings/`, read from the environment through django-environ. Importing a settings
  module only binds names; every deployed environment runs `production.py`
- Accounts through django-allauth on a custom user model, with
  {%- if cookiecutter.username_type == 'email' %} the email address as the login{% else %} a username as the login{% endif %};
  `User.get_absolute_url` says how a user is addressed and `User.display_name` how one is shown
- Server-rendered templates with htmx (through django-htmx) over the UI library in
  `{{ cookiecutter.project_slug }}/ui/`: django-cotton components, project-owned CSS,
  colour palettes, and a showcase served under `DEBUG` at `/ui/components/`. There is no
  Node.js toolchain, no asset pipeline and no CDN
- A nonce-based Content Security Policy on every response, configured by `SECURE_CSP` in
  `config/settings/base.py`
- Background work through Django's Tasks framework: run immediately in development and tests,
  stored in PostgreSQL and executed by a worker process in production
{%- if cookiecutter.use_celery == 'y' %}
- Celery next to it for the work that framework has no answer for — schedules, retry policies and
  workflows — wired up in `config/celery_app.py`
{%- endif %}
{%- if cookiecutter.rest_api == 'DRF' %}
- A REST API with Django REST Framework: routes in `config/api_router.py`, serializers under
  `{{ cookiecutter.project_slug }}/users/api/`, an OpenAPI schema from drf-spectacular
{%- elif cookiecutter.rest_api == 'Django Ninja' %}
- A REST API with Django Ninja: the api instance in `config/api.py`, schemas under
  `{{ cookiecutter.project_slug }}/users/api/`
{%- endif %}
{%- if cookiecutter.identity_provider == 'entra' %}
- Sign-in through Microsoft Entra ID next to password login, over allauth's generic OpenID
  Connect provider keyed by the object id (`docs/authentication.rst`)
{%- elif cookiecutter.identity_provider == 'google' %}
- Sign-in through Google next to password login, over allauth's Google provider
  (`docs/authentication.rst`)
{%- endif %}
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
- `{{ cookiecutter.project_slug }}/identity/`: allauth's headless API issuing the
  single-page application's JWTs, the verification of provider-issued service tokens, and
  the Ninja authentication policies every route runs under
{%- endif %}
{%- if cookiecutter.realtime == 'channels' %}
- Websockets through Django Channels, routed by `config/websocket.py` from `config/asgi.py`
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}
- Sentry, initialised by the `{{ cookiecutter.project_slug }}.sentry` app from the
  `SENTRY_*` settings that `production.py` defines
{%- endif %}
{%- if cookiecutter.cloud_provider == 'AWS' %}
- Uploads on Amazon S3 in production through django-storages
{%- elif cookiecutter.use_docker == 'y' %}
- Uploads served by nginx in production, from the volume the application writes them to
{%- else %}
- Uploads stored on the local filesystem; nothing serves them in production, so a media
  backend is the first thing to add before deploying
{%- endif %}
{%- if cookiecutter.use_whitenoise == 'y' %}
- Static files served by WhiteNoise from the application process
{%- elif cookiecutter.cloud_provider == 'AWS' %}
- Static files served from Amazon S3
{%- endif %}
- Email through Anymail
  {%- if cookiecutter.mail_service == 'Mailgun' %} with Mailgun{% elif cookiecutter.mail_service == 'Amazon SES' %} with Amazon SES{% else %} over SMTP{% endif %} in production
  {%- if cookiecutter.mail_catcher == 'Mailpit' %}, caught locally by Mailpit on port 8025
  {%- elif cookiecutter.mail_catcher == 'Mailtrap Local' %}, caught locally by Mailtrap Local on port 3550
  {%- else %}, printed to the console in development
  {%- endif %}
{%- if cookiecutter.use_docker == 'y' %}
- Docker Compose for development and for every deployed environment, behind Traefik
{%- endif %}
{%- if cookiecutter.ci_tool == 'Github' %}
- GitHub Actions running pre-commit, mypy, `makemigrations --check` and the test suite
{%- elif cookiecutter.ci_tool == 'Gitlab' %}
- GitLab CI running pre-commit, mypy, `makemigrations --check` and the test suite
{%- endif %}

## Commands

{% if cookiecutter.use_docker == 'y' -%}
Everything runs in the containers of `docker-compose.local.yml`. `just` wraps the common ones;
`just --list` shows them all.

| Task | Command |
| ---- | ------- |
| Build the images | `just build` |
| Start the stack | `just up` (`just down` to stop, `just logs` to follow) |
| A management command | `just manage <command>` |
| Migrations | `just manage makemigrations` then `just manage migrate` |
| Tests | `just pytest` |
| One test | `just pytest {{ cookiecutter.project_slug }}/users/tests/test_models.py -k the_name` |
| Type checks | `docker compose -f docker-compose.local.yml run --rm django mypy .` |
| Linters and formatters | `pre-commit run --all-files`, on the host, as CI runs them |
| Documentation | `docker compose -f docker-compose.docs.yml up` |
| Add or change a dependency | edit `pyproject.toml`, then `docker compose -f docker-compose.local.yml run --rm django uv lock` and rebuild |

The site is served at <http://localhost:8000>.
{%- if cookiecutter.use_celery == 'y' %} Celery's worker, beat and Flower run as their own
services in the same Compose file.
{%- endif %}
{%- else -%}
Everything runs through `uv` from the project root, against a PostgreSQL
{%- if cookiecutter.use_celery == 'y' %} and a Redis{% endif %} you run yourself.

| Task | Command |
| ---- | ------- |
| Install the dependencies | `uv sync` |
| Serve the site | `uv run uvicorn config.asgi:application --host 0.0.0.0 --reload --reload-include '*.html'` |
| A management command | `uv run python manage.py <command>` |
| Migrations | `uv run python manage.py makemigrations` then `uv run python manage.py migrate` |
| Tests | `uv run pytest` |
| One test | `uv run pytest {{ cookiecutter.project_slug }}/users/tests/test_models.py -k the_name` |
| Type checks | `uv run mypy .` |
| Linters and formatters | `uv run pre-commit run --all-files` |
| Documentation | `uv run make livehtml` from `docs/` |
| Add or change a dependency | edit `pyproject.toml`, then `uv lock` |

The database connection is read from `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER` and `POSTGRES_PASSWORD`; the test settings read the same ones.
{%- if cookiecutter.use_celery == 'y' %} Celery reads `REDIS_URL`; run a worker with
`uv run celery -A config.celery_app worker -l info` and the scheduler with
`uv run celery -A config.celery_app beat`.
{%- endif %}
{%- endif %}

Run the tests and the type checks before reporting a change as done. The pre-commit hooks run
ruff, djLint and the other checks on commit, and mypy on push.

## Layout

| Path | What lives there |
| ---- | ---------------- |
| `config/settings/` | The four settings modules; each setting is rendered from one block |
| `config/urls.py` | URL routing; under `DEBUG` also the error-page previews and the showcase |
| `config/asgi.py` | The ASGI entry point |
{%- if cookiecutter.rest_api == 'DRF' %}
| `config/api_router.py` | The REST API's routes |
{%- elif cookiecutter.rest_api == 'Django Ninja' %}
| `config/api.py` | The api instance every route is registered on |
{%- endif %}
{%- if cookiecutter.use_celery == 'y' %}
| `config/celery_app.py` | The Celery application |
{%- endif %}
{%- if cookiecutter.realtime == 'channels' %}
| `config/websocket.py` | The websocket routing and consumers |
{%- endif %}
| `{{ cookiecutter.project_slug }}/users/` | The custom user model, its forms, views, adapters and tests |
| `{{ cookiecutter.project_slug }}/ui/` | The UI library's Python side: filters, palettes, themes, checks, showcase |
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
| `{{ cookiecutter.project_slug }}/identity/` | The app's own tokens, service tokens and the authentication policies |
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}
| `{{ cookiecutter.project_slug }}/sentry/` | The app that initialises the Sentry SDK |
{%- endif %}
| `{{ cookiecutter.project_slug }}/templates/` | Pages, the allauth overrides and the components under `cotton/ui/` |
| `{{ cookiecutter.project_slug }}/static/` | The UI library's stylesheets, `css/project.css` and `js/project.js` |
| `{{ cookiecutter.project_slug }}/htmx.py` | The htmx mixin and the login-redirect middleware |
| `{{ cookiecutter.project_slug }}/typedefs.py` | The shared request types the views annotate against |
| `{{ cookiecutter.project_slug }}/tests/` | Tests that belong to no single app, such as the policy and the error pages |
| `tests/` | Tests of the root-level files |
| `docs/` | The Sphinx documentation, including the UI library's contract |
| `.envs/` | One directory of environment files per environment; never committed |
| `.env.example` | What a deployment must supply, with the drawn values left unset |
{%- if cookiecutter.use_docker == 'y' %}
| `compose/` | The images: `local/` for development, `production/` for every deployed environment |
{%- endif %}
{%- if cookiecutter.ci_tool == 'Github' %}
| `.github/workflows/ci.yml` | The pipeline: pre-commit, mypy, migrations and the tests |
{%- elif cookiecutter.ci_tool == 'Gitlab' %}
| `.gitlab-ci.yml` | The pipeline: pre-commit, mypy, migrations and the tests |
{%- endif %}

New apps go under `{{ cookiecutter.project_slug }}/`, are created from there with
`startapp` and are added to `LOCAL_APPS` in `config/settings/base.py`. The places marked
"your stuff" are where your own code is meant to go.

## Conventions

1. **No inline code in templates.** The Content Security Policy allows no `unsafe-inline`: no
   inline `<script>` or `<style>`, no `style=` attributes, no `on*` or `hx-on*` handlers.
   Behaviour belongs in `static/js/project.js`, delegated from the document; styling belongs in
   the stylesheets. A script that truly must be inline carries the request's nonce.
2. **Build pages from the UI library.** Use the components under `templates/cotton/ui/`
   (`<c-ui.button>`, `<c-ui.card>`, `<c-ui.field>` and the rest) rather than hand-written markup,
   and write values into their attributes through the `ui_attr`, `ui_url` and `ui_attrs` filters,
   never as a bare interpolation. Colours come from the `--ui-` tokens, never as literals.
   `docs/frontend.rst` is the library's contract; `/ui/components/` shows every component.
3. **Render each setting from one block.** In `config/settings/`, a setting is defined once, read
   from the environment where it is configurable, and documented where it is not obvious. A new
   variable a deployment supplies goes into every file under `.envs/` and into `.env.example`.
4. **Keep the settings importable.** Importing a settings module binds names and nothing else: no
   connections, no SDK initialisation, no side effects. Work that needs the app registry belongs
   in an `AppConfig.ready`.
5. **Tests live next to the code they test**, in the app's `tests/` package, and run under
   `config.settings.test` through pytest-django. Use the factories in
   `{{ cookiecutter.project_slug }}/users/tests/factories.py` and the fixtures in
   `conftest.py`. The generated suite starts green and at full coverage; keep it there.
6. **Everything is typed.** mypy runs in strict mode with the django-stubs plugin:
   annotate every function, and use the request types from
   `{{ cookiecutter.project_slug }}/typedefs.py` rather than redefining them.
7. **Migrations are committed.** Run `makemigrations` in the same change as the model edit
{%- if cookiecutter.ci_tool != 'None' %}; CI runs `makemigrations --check` and rejects a model
   change without one{% endif %}.
8. **Dependencies are pinned** to exact versions in `pyproject.toml`; `uv.lock` is committed and
   regenerated with `uv lock`, never edited by hand.
9. **No environment file is committed.** `.gitignore` keeps `.env` and everything under `.envs/`
   out of version control; `.env.example` is the only declaration in the repository.

## Documentation

- `README.md` — setting up, the commands, and what the chosen options added
- `docs/howto.rst` — how to write and build these docs
- `docs/frontend.rst` — the UI library: components, filters, tokens, palettes and themes
- `docs/users.rst` — the user model and its views
{%- if cookiecutter.identity_provider != 'none' %}
- `docs/authentication.rst` — sign-in through the identity provider, and what it trusts
{%- endif %}
- [moldordie's own documentation](https://github.com/matsakelarsson/moldordie) — why the
  project is laid out this way, and what each generation option does
