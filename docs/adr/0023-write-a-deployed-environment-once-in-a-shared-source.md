---
status: accepted
---

# Write a deployed environment once, in a shared source

ADR 0013 made a deployed environment configuration alone: `dev`, `test` and `production` each
own a directory of env files, a Compose file and a Traefik router file, over one production
settings module and one set of production images. That decision is about the generated
project, and it stands. In the template, though, the three environments were three
hand-kept copies of the same text: the Django env files 104 lines each with 5 differing,
the Postgres env files identical, the Compose files identical once the environment's name
is replaced, the router files differing in the host and production's `www` arm. Every
commit that added a deployment variable applied one hunk three times, and two generation
tests existed only to police the copies, partly: `OTEL_DEPLOYMENT_ENVIRONMENT` differed per
environment and was asserted nowhere.

Each kind of file a deployed environment owns is written once, in the **shared source**:
the `templates` directory at the repository root, which Cookiecutter's loader searches
beside the project template and never renders as output (Cookiecutter 2.2.0, "templates
inheritance"; the README states the minimum). The three environments' files stay in the
project template under their present paths, so the removal rules do not change, and each
becomes a stub of two statements: it names its environment and includes the source for its
kind, with Jinja's whitespace control so that the rendered bytes are the source's. What an
environment differs in is one table in the shared source, `templates/deployed/environments`,
keyed by the name: the host it answers for (a prefix for `dev` and `test`, the apex for
production) and whether the apex also answers as `www`. Everything else derives from the
name: the names Sentry and OpenTelemetry report as, the allowed hosts (production keeps its
leading-dot form), the commented audience, the env-file paths, the volume names, the image
names and Traefik's build argument. The routers take the host from the table, and production's
apex also answers as `www` when the domain is an apex, which no prefixed host is.

The generated project does not change by a byte. `scripts/compare_generated.py` baked every
supported combination, plain and hostile, from the commit before and from the working tree:
all 90 the same for the env files, then all 96 the same for the Compose files and the
routers, with three extra rows for the forks no supported combination reaches (Docker with
an older PostgreSQL, Docker with a subdomain as the domain name, and the subdomain with
Celery and nginx, which renders every router). ADR 0013 counted a routing change as three
router files rather than one; in the template it is one now, and the generated tree still
has three.

## Considered options

- **Three copies, aligned by hand**, the previous state: a deployment variable was three
  hunks, and the tests that compared the copies compared the variable names only.
- **Rendering the environments at runtime** (Compose overrides, interpolated paths, a Docker
  provider): rejected by ADR 0013, which this decision does not reopen. The shared source is
  a generation-time mechanism; the generated tree still has three of everything.
- **One env file with the environment's name as a variable**: changes the generated tree, and
  a developer downstream edits one environment's file without touching the others.
- **Deriving the stubs from the table** (generating the stubs themselves): the stubs are
  what Cookiecutter walks, six two-line files, and a path that exists in the template is what
  the removal rules and the hook tests read.

## Consequences

A contributor adding a deployment variable, a service, a volume or a router writes it once,
in `templates/deployed/`, and the three environments cannot disagree about it; the
generation tests hold the generated tree to that, as a developer sees it: the three Compose
files declare the same services and volumes. Adding a deployed environment takes its four
stubs, a row of the table, its name in the hook's `DEPLOYED_ENVIRONMENTS` and in the tests'
hand-written tuple. The shared source is Jinja, not dotenv or YAML, so this repository's
pre-commit hooks and ruff leave it alone, as they do the project template: a whitespace
fixer would change the rendered bytes. The hook tests' check of the placeholder sites reads
the shared source for the deployed environments' files and fails if a stub carries a
placeholder itself. Neither the shared source nor a stub may hold `{{`, `{%` or `{#` beyond
Cookiecutter's own syntax; a generated project holds no `templates` directory and no
unrendered include, which the generation tests assert for every combination.
