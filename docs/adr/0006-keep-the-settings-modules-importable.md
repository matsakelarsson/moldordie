---
status: accepted
---

# Keep the settings modules importable

`config/settings/production.py` in the generated project used to call `sentry_sdk.init()` at
import, with `use_sentry=y`. Together with its reads of the environment it made the module
something only a deployment, or a shell script pasting placeholder variables, could import:
nothing in the generated test suite loaded it, so the settings that only production has (the
storage backends, the mail backend, the Content Security Policy's report-only switch) were
exercised by Django's deployment checks in CI and nowhere else. A review proposed declaring the
required environment in one place, deferring the Sentry call, and shipping a generated test
that imports the production settings under a stand-in environment.

A settings module now binds names and nothing else. The Sentry configuration stays in the
production settings as `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` and
`SENTRY_LOG_LEVEL`, read from the environment there as before; the SDK is initialised in the
`ready()` of a small app, `<project_slug>/sentry/`, that the production settings install. The
app declares the settings it reads as a `Protocol` and casts Django's settings to it once,
because django-stubs resolves settings against the test settings module, which has none of
them. Django's app registry is populated in every kind of process the project runs: the ASGI
server, management commands (the task worker included), and Celery's worker and beat through
its Django fixup, which calls `django.setup()`.

The required environment is declared where it already was, the `.envs/.production` files. The
generated `tests/test_production_settings.py` reads them, fills the blank values with
stand-ins, imports the production settings afresh under that environment, with a fresh copy
of the base module so that the lists and dicts production extends are not those the running
tests use, and checks the loaded values: that the files declare enough for the settings to
load, the storage backends and URLs of the chosen cell, the mail backend and its `ANYMAIL`
reads, the CSP report endpoint and report-only switch, the Sentry settings, and that every
installed app can be loaded. It lives in the root `tests/` package, which is pruned together
with the env files.

## Considered options

- **Keep the call in the settings and test with an empty DSN**: the SDK creates no transport
  then, but `init()` still installs its integrations, which patch Django's handlers, the
  logging module and the Redis client in the process running the tests.
- **Initialise at the process entry points** (`config/asgi.py`, `config/celery_app.py`,
  `manage.py`): three sites to keep aligned, where `ready()` is one.
- **The users app's `ready()`**: it already exists, but error reporting is not the users app's
  concern, and its module would fork on `use_sentry`.
- **An always-installed app gated on the DSN, with the settings in `base.py`**: development
  would read the production configuration, and a developer with `SENTRY_DSN` exported would
  report local errors under the `production` environment.
- **The app reading the environment itself**: the settings would no longer be the one place the
  environment is read, which the settings documentation relies on.
- **`strict_settings = false` for django-stubs** instead of the `Protocol`: every misspelled
  setting in the project would type as `Any`.
- **A stand-in environment written in the test**: a second list of the deployment's variables,
  free to drift from the env files that deployments actually use.

## Consequences

Importing any settings module of a generated project has no side effects, and its production
settings are checked by its own suite under the environment its env files declare; a variable
the settings require and the files omit fails there. A process that reads the settings without
setting Django up, Flower for one, no longer initialises the SDK. The integration scripts keep
running Django's deployment checks against the production settings with their placeholder
variables: those checks need the production settings as the process's settings module, which
the generated test does not attempt, and the env files cannot serve them because they set
`DJANGO_SECURE_SSL_REDIRECT=False`, which the checks flag. The `sentry` app is one
`{% if use_sentry %}` fork fewer in the settings and one removal rule more.
