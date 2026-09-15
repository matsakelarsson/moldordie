# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Project Is

moldordie is a fork of [cookiecutter-django](https://github.com/cookiecutter/cookiecutter-django), a **Cookiecutter template** that generates production-ready Django projects. It is NOT a Django application itself — it's a Jinja2-templated project scaffold. The generated project lives inside `{{cookiecutter.project_slug}}/` and gets processed by Cookiecutter when users run the generator.

## Commands

### Install dependencies

```bash
uv sync --locked
```

### Run tests

```bash
# Full test suite (parallel, via tox)
uv run tox run -e py

# Direct pytest (parallel)
uv run pytest -n auto tests

# Single test
uv run pytest tests/test_cookiecutter_generation.py -k "test_name"

# Run with auto-fixable style checks enabled
AUTOFIXABLE_STYLES=1 uv run pytest -n auto tests

# Only the auto-fixable style checks, as CI's own job runs them
AUTOFIXABLE_STYLES=1 uv run pytest -n auto tests -m auto_fixable
```

### Linting and formatting

```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Ruff only
uv run ruff check --fix
uv run ruff format
```

### Integration tests (require Docker or PostgreSQL+Redis)

```bash
# Docker-based
sh tests/test_docker.sh                          # defaults
sh tests/test_docker.sh use_celery=y rest_api=DRF  # with options

# Bare metal (needs PostgreSQL and Redis running)
sh tests/test_bare.sh
sh tests/test_bare.sh use_celery=y rest_api=DRF
```

### Generate a project locally for debugging

```bash
uv run cookiecutter . --no-input --output-dir=/tmp/debug
```

## Architecture

### Template Generation Flow

1. User runs `cookiecutter` — prompted with options from `cookiecutter.json`
2. `hooks/pre_gen_project.py` validates input (project_slug format, control characters, the domain name's characters, conflicting options)
3. Jinja2 renders all files under `{{cookiecutter.project_slug}}/` with user choices; free-text answers pass through the escaping filter of each file's syntax (`local_extensions.py`, terms in `CONTEXT.md`)
4. `hooks/post_gen_project.py` receives the answers as JSON, prunes the files the chosen options do not need and generates random secrets

### Key Files

- **`cookiecutter.json`** — All template variables and their choices (project name, Docker, Celery, cloud provider, REST API, etc.)
- **`hooks/pre_gen_project.py`** — Pre-generation validation: project slug, control characters, the domain name's characters, conflicting options (uses Jinja2 syntax at the top for context manipulation)
- **`hooks/post_gen_project.py`** — Post-generation hook: `SECRETS`, the table of secrets, and `fill_secrets`, which draws and writes them; `REMOVALS`, the table of removal rules, and `prune`, which applies them plus the Channels cleanup (terms in `CONTEXT.md`)
- **`local_extensions.py`** — The option catalogue (`OPTIONS`, `option_names`; the kinds are defined under Option in `CONTEXT.md`), read from `cookiecutter.json`, and the `string_escape` Jinja filter that a free-text answer passes through where it lands inside a Python, TOML, YAML or gettext string (in HTML it passes through Jinja's `e`). Both reach Cookiecutter through `_extensions` in `cookiecutter.json`; the hooks run as standalone scripts and cannot import the catalogue, so they read it through the `option_names` Jinja global
- **`{{cookiecutter.project_slug}}/`** — The template directory; files here use Jinja2 conditionals (`{% if cookiecutter.use_celery == 'y' %}`) to include/exclude content

### Test Structure

- **`tests/test_cookiecutter_generation.py`** — Main test file. Uses `pytest-cookies` to bake the template with `SUPPORTED_COMBINATIONS`: the defaults, one row per choice of every list and flag option in the catalogue, and the hand-written `PAIRED_COMBINATIONS`, deduplicated so each project bakes once. The `bake` fixture generates the project its answers select and returns the reader, once per set of answers and test process: every test that bakes the same answers gets the same tree, so a tool that rewrites files (django-upgrade) runs on a copy and ruff runs without its cache (`docs/adr/0002`). Under xdist a process is a worker, so the tests parametrized over the combinations carry their combination as an `xdist_group` and `--dist loadgroup`, the default in `addopts`, runs each group on one worker. A test expecting the hook to refuse bakes through `cookies`. Verifies: no Jinja syntax left in output, generated code passes linting, correct files present/absent and, with `AUTOFIXABLE_STYLES=1`, that `ruff format`, djlint's formatter and `django-upgrade` would change nothing (the `auto_fixable` marker; CI runs just those in its own job).
- **`tests/generated_project.py`** — The reader (a term in `CONTEXT.md`): `GeneratedProject` locates the files under a generated root and parses the ones with a syntax (`env`, `compose`, `pins`, `settings`); `PythonModule` reads what a Python file binds at module scope from its source, over the subset its docstring lists, and fails explicitly outside it (`docs/adr/0001`). Nothing in it asserts, checks existence or validates the tree
- **`tests/test_generated_project.py`** — The reader on hand-written modules and trees: the forms it resolves, aliasing and mutation, conditional bindings, rejected modules, the `env` reads and the file readers
- **`tests/test_hooks.py`** — Unit tests for the hooks: `fill_secrets` run on hand-written placeholder files through a generator the test controls, with the secrets table checked against the template's placeholder sites; `prune` run on a copy of the template tree against hand-written expected removals, and the removal rules checked for consistency over every combination of the answers they read
- **`tests/test_options.py`** — The catalogue: every option's kind against a hand-written mapping (`KINDS`), the `option_names` global reaching a Cookiecutter environment, and the catalogue's other readers checked against it: the answers the CI integration jobs pass, the README's example session and the options page
- **`tests/test_local_extensions.py`** — The `string_escape` filter round-tripped through the Python, TOML and YAML parsers, and loaded from `cookiecutter.json`
- **`tests/test_bare.sh`** / **`tests/test_docker.sh`** — Integration scripts that generate a project and run its checks: mypy, its test suite, `makemigrations --check`, Django's checks with the local settings and its deployment checks with the production settings (placeholders stand in for the secrets), `makemessages --all` (that extraction completes and updates the catalogues, nothing about the translations themselves) and the docs build. They stay two scripts because their setup differs, an interpreter and OS packages against image builds (`docs/adr/0004`); a new check goes into both by hand, with the settings module explicit

### Generated Project Layout

The generated Django project uses:

- `config/settings/{base,local,test,production}.py` — Split settings with django-environ; importing a settings module has no side effect beyond binding names, so the generated `tests/test_production_settings.py` loads `production.py` under the environment `.envs/.production` declares (`docs/adr/0006`)
- `config/urls.py` — URL routing
- `config/settings/base.py` — nonce-based Content Security Policy (`SECURE_CSP`, Django's `ContentSecurityPolicyMiddleware`) and the `TASKS` framework wiring (`django_tasks_db` app; immediate backend in local/test, database backend plus the `taskworker` process in production)
- `config/asgi.py` — ASGI entry point served by Uvicorn (Gunicorn + Uvicorn worker in production); with `realtime=channels` it also routes websockets to `config/websocket.py`
- `<project_slug>/users/` — Custom user model (username or email-based auth via django-allauth); `User.get_absolute_url` says how a user is addressed and `User.display_name` how one is shown, and templates and views go through them instead of forking on `username_type` (`docs/adr/0003`); `users/tasks.py` holds the Django Tasks example (plus a Celery variant with `use_celery=y`)
- With `identity_provider` other than `none`, sign-in through Microsoft Entra ID or Google next to password login: `SOCIALACCOUNT_PROVIDERS` in `base.py` (Entra through the generic OpenID Connect provider keyed by `oid`, `docs/adr/0007`; the trust decisions in `docs/adr/0008`), the provider's origin in the policy's `form-action`, `users/checks.py` reporting empty credentials, `users/providers.py` (Entra only: the provider subclass the adapter hands out, refusing a token without a usable `oid`), `users/tests/social.py` driving allauth's callback with the token verification patched for `test_social_login.py` and `test_providers.py`, and the generated `docs/authentication.rst`
- `<project_slug>/htmx.py` — `HtmxTemplateMixin` (renders `template.html#partial` for htmx requests, adds `Vary: HX-Request`) and `HtmxLoginRedirectMiddleware` (turns login redirects into `HX-Redirect` for htmx requests)
- `<project_slug>/sentry/` — With `use_sentry=y`, the app whose `ready()` initialises the Sentry SDK from the `SENTRY_*` settings that `production.py` defines and that install it (`docs/adr/0006`)
- `<project_slug>/identity/` — With `rest_api=Django Ninja` and a provider, the app behind the single-page application's login: `base.py` configures allauth's headless API (app client only, JWT strategy, HS256 with `DJANGO_HEADLESS_JWT_PRIVATE_KEY` drawn per environment by the secrets table, stateful validation, refresh rotation) and CORS for `DJANGO_FRONTEND_ORIGINS`; `identity/apps.py` refuses to start with an empty key or a non-positive lifetime (`validate_token_settings`, also run on the loaded production settings by `tests/test_production_settings.py`); `identity/auth.py` holds the Ninja policies (`user_auth`, set globally by `config/api.py`: an app-issued JWT whenever an `Authorization` header is present, else Ninja's session authenticator with its CSRF check); `identity/tests/headless.py` drives the app client for the tests
- `<project_slug>/tests/` — Project-level tests that belong to no single app: the Content Security Policy, the htmx helpers, with `realtime=channels` the websocket consumer and with `use_sentry=y` the Sentry wiring
- `tests/` — Tests of the root-level files, pruned together with `.envs`: the dotenv merge script and the production settings loaded under the declared environment
- `compose/` — Docker configs for local and production
- `pyproject.toml` — The pinned dependencies, templated into `[project.dependencies]` and the `dev` dependency group; generation writes no `uv.lock`, the developer's first `uv sync` does
- `<project_slug>/templates/` — Semantic HTML styled by the vendored Pico CSS (`<project_slug>/static/vendor/pico/`, pinned with SHA-256 metadata); htmx is loaded through django-htmx's `{% htmx_script %}` (with the `hx-ws` extension when `realtime=channels`). htmx fragments are `{% partialdef %}` partials inside the page template, selected with `htmx_partial` on the view. No Node.js, Bootstrap or asset pipeline.

## Conventions

- **Python 3.12–3.14** supported (`requires-python = ">=3.12"`); 3.14 is the default via `.python-version` and the Docker images
- **No inline code in templates**: the CSP has no `unsafe-inline`, so no inline `<script>`/`<style>`, `style=` attributes or `on*=` handlers (enforced by `test_no_inline_code_in_templates`); a necessary inline script takes `nonce="{{ csp_nonce }}"`
- **Line length**: 119 characters for ruff in this repository; generated projects keep ruff's default of 88 (their djlint allows 119), so keep template Python within 88 columns
- **Ruff** for linting/formatting; config in `pyproject.toml` under `[tool.ruff]`
- **djLint** runs on the generated projects, not on the template sources, with the generated `[tool.djlint]` (`profile = "django"`): `test_djlint_lint_passes` lints every combination in the default suite, and `test_djlint_check_passes` checks the formatting with `AUTOFIXABLE_STYLES=1`. This repository has no djlint config or hook of its own, so write template HTML the way djlint leaves the rendered output
- Template files under `{{cookiecutter.project_slug}}/` are excluded from ruff (not parseable Python)
- **Settings templates** render each setting from one block: the answers a module forks on are bound to names at its top, a choice from a list (mail service, mail catcher) is a row in a table there, and the block forks on each answer where it decides something (`docs/adr/0005`)
- **Calendar versioning**: `YYYY.MM.DD`

## Adding a New Template Option

1. Declare it in `cookiecutter.json`: a list of choices makes a list option, a `"y"`/`"n"` default a flag option, any other text a free-text option. Add it to `KINDS` in `tests/test_options.py`. Nothing else registers it: the pre-generation hook lowercases and validates every flag and checks every free-text answer for control characters, and the generation tests bake every choice
2. Add validation specific to the option in `hooks/pre_gen_project.py` if needed
3. In `hooks/post_gen_project.py`: add a removal rule to `REMOVALS` for the files the option makes unnecessary, with the expected removals in `tests/test_hooks.py`; add a cleanup step to `prune` only when a deletion depends on what else is left in the generated tree, as the Channels cleanup does; a new `!!!SET NAME!!!` placeholder is a row in `SECRETS`, with its site added to `PLACEHOLDER_SITES` in `tests/test_hooks.py`; put other content modifications (`.gitignore` lines) in `main`
4. Use Jinja2 conditionals in template files: `{% if cookiecutter.option == 'y' %}`; write a free-text answer through the escaping filter of the file's syntax (`| string_escape`, or `| e` in HTML; see Escaping in `CONTEXT.md`)
5. Add a row to `PAIRED_COMBINATIONS` in `tests/test_cookiecutter_generation.py` only when the option's template arms need a second answer to be reached; an option rejected in some combination goes into `UNSUPPORTED_COMBINATIONS`
6. Document it: an entry in `docs/1-getting-started/project-generation-options.rst`, in declaration order, with a list option's choices as an enumerated list whose items start with the answer as typed; and its prompt in the README's example session. `tests/test_options.py` checks both against the catalogue

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, driven through the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels, unchanged: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root, created lazily by `/domain-modeling`. See `docs/agents/domain.md`.
