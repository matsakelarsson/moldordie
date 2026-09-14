---
status: accepted
---

# Keep the bare-metal and Docker integration scripts separate

`tests/test_bare.sh` and `tests/test_docker.sh` each generate a project and run its checks,
one on the runner's interpreter and one inside the project's images. A review proposed one
list of checks with the two scripts reduced to runners behind it. The scripts stay separate.
Their duplication is a handful of one-line commands; what differs is their setup and
lifecycle. The bare script pins an interpreter, installs the OS packages and syncs the
project; the Docker script builds the local image, locks, builds again, and at the end builds
the production image and runs the deployment checks inside it. A runner abstraction would
carry those differences without removing them, and adding checks to both scripts raises the
overlap without creating a need for it.

What the comparison did show is that the lists had drifted, and that is repaired directly.
The bare script gains `makemessages --all` and the deployment checks against the production
settings; the Docker script gains Django's checks with the local settings. Every check names
its settings module. The bare script keeps its own database and Redis connection settings, from
the CI job's environment, and supplies the production placeholders (secret key, storage
credentials, admin URL, mail credentials) only to the production-check command.

## Considered options

- **One list of checks, the scripts as runners**: the proposed abstraction. Rejected for the
  reasons above.
- **A shared shell file sourced by both scripts**: the shared part would be four lines, and
  the commands differ in how they are launched (`uv run` against `docker compose run`).
- **Two scripts, aligned by hand**: chosen. A new check is added to both, and the CI matrix
  decides which combinations each script covers.

## Consequences

The deployment checks now run for the seven bare-metal combinations as well as the three
Docker ones. They extend Django's configuration checks, and no more: they do not show that
Celery workers, Channels messaging or external services function. `makemessages --all` shows
that extraction completes and updates the generated catalogues; it says nothing about whether
the translations are complete, were current beforehand or are usable at runtime. Someone adding
a check adds it to both scripts, with the settings module explicit, and describes it in
`AGENTS.md` and `CONTRIBUTING.md` in those terms.
