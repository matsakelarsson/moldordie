---
status: accepted
---

# Run every deployed environment on the production settings

The generated project had two environments, `local` and `production`, and a change went from a
developer's machine straight to the one deployment. A promotion chain was wanted instead: `dev`
and `test` in front of `production`, so a change is exercised on a deployment twice before it
reaches users. The question each new environment raised was what it is made of — whether it
brings a settings module of its own, or only configuration.

A deployed environment is configuration and nothing else. `dev`, `test` and `production` each
own a directory of env files (`.envs/.dev/`, `.envs/.test/`, `.envs/.production/`), a Compose
file in the project root, and a Traefik router file naming the hosts it answers for. All three
build their images from `compose/production/` and all three run
`config/settings/production.py`, which each environment's `.django` file names in
`DJANGO_SETTINGS_MODULE`. A settings module belongs to a kind of configuration — development,
tests, a deployment — not to a deployment instance: three near-copies would drift, and the
further `dev` and `test` drifted from `production` the less they would rehearse it. The
template already assumed this, in a production settings module that reads `SENTRY_ENVIRONMENT`
with a `production` default and env files that carry `DJANGO_SETTINGS_MODULE`. It also leaves
`config/settings/test.py`, the settings the generated suite runs under, to mean what it always
meant.

What an environment differs in is its variables, and the differences that are not the
operator's to remember are drawn when the project is generated. Each deployed environment gets
its own Django secret key, admin URL, database password, Flower password and, with the
single-page application, token signing key: separate rows of `SECRETS`, so a session or token
minted for `dev` is not accepted by `production`. The database role and Flower's user stay
shared across all four environments, as they were across two, so a `pg_dump` taken in one
restores in another.

Traefik was the one piece of the deployment that hardcoded the domain, in a file that was at
once its static configuration and, through `providers.file.filename` pointing back at itself,
its dynamic configuration. It is now split the way Traefik recommends: `traefik.yml` holds the
static configuration and points at a dynamic directory, `dynamic/shared.yml` holds the services
and middlewares every environment shares, and `dynamic/dev.yml`, `dynamic/test.yml` and
`dynamic/production.yml` hold each environment's routers. The image takes the environment's
name as the `ENVIRONMENT` build argument and copies that one file in as its routers, so each
environment's Compose file names its own and the rest of the configuration is written once.

## Considered options

- **A settings module per environment** (`config/settings/dev.py` and one for `test`): three
  near-copies of `production.py` free to drift, and `test` is taken by the settings the
  generated suite runs under, so it would have to be renamed in `pyproject.toml`, the generated
  CI workflow and the production Dockerfile to free the name for a deployment.
- **No files for the new environments**, the operator supplying each deployment's variables
  from outside the repository: nothing would record what a deployment must declare, and the
  secrets that must differ between environments would be left to be remembered.
- **Compose override files layered on production's** (`-f docker-compose.production.yml -f
  docker-compose.dev.yml`): Compose appends `env_file` lists rather than replacing them, so
  `dev` would load production's env files as well as its own.
- **One Compose file with the environment interpolated** (`.envs/.${ENVIRONMENT}/`): one
  unexported variable deploys the wrong configuration, and Compose does not interpolate mapping
  keys, which the volume names are.
- **A `traefik.yml` per environment**: the entry points, the ACME resolver and the services
  duplicated three times to vary the host in three rules.
- **Traefik's Docker provider with labels on the services**, which would take the host from the
  env file: Traefik would need the Docker socket.
- **Go templating in the file provider**: it does not work in the main static configuration
  file, which this file is.
- **One host rule matching any host**, leaving ACME to the name in the request: a certificate
  would be requested for any hostname pointed at the deployment.
- **Parametrising the generated `tests/test_production_settings.py` over the three
  environments**: the env files are not in version control, so it would pass on a freshly
  generated tree and fail in the project's own CI. Splitting the check across the two suites
  proves the same thing: the generated test loads `production.py` under what
  `.envs/.production` declares, so those files are known to declare everything the module
  requires, and `test_deployed_environments_declare_the_same_variables` in this repository
  checks that `dev` and `test` declare the same names. A variable added to the settings and to
  one env file fails in the first; a variable left out of `dev` fails in the second.

## Consequences

A deployment is promoted by pointing `-f` at another Compose file, and every command in
`docs/3-deployment/deployment-with-docker.rst` works unchanged against any of the three. A
setting that a deployment must be able to vary has to be read from the environment in
`production.py`, as one already had to be. The generated project carries two more Compose files
and four more env files, none of which is in version control; what a deployment must supply is
declared in the committed `.env.example` (`docs/adr/0014`).

A change to how the deployments route — a new entry point, a service behind a new path — is made
in three router files rather than one, which is the cost of each environment naming its own
hosts in a file Traefik reads directly. The shared services and middlewares, and the whole
static configuration, are still written once. `test_deployed_compose_file_wires_its_own_environment`
checks that an environment's Compose file reads only its own env files, keeps its own volumes and
builds Traefik with its own routers, so a file copied from another environment and left half
edited fails.
