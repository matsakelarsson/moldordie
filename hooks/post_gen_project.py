import json
import secrets
import shutil
import string
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TERMINATOR = "\x1b[0m"
WARNING = "\x1b[1;33m [WARNING]: "
SUCCESS = "\x1b[1;32m [SUCCESS]: "

# What the credentials read when the ``debug`` answer is ``y``.
DEBUG_VALUE = "debug"

ALPHANUMERIC = string.ascii_letters + string.digits
LETTERS = string.ascii_letters

# The env files that carry a placeholder, in the order a change is promoted through the
# environments: the developer's machine, then the three deployed ones.
LOCAL_DJANGO = ".envs/.local/.django"
LOCAL_POSTGRES = ".envs/.local/.postgres"
DEV_DJANGO = ".envs/.dev/.django"
DEV_POSTGRES = ".envs/.dev/.postgres"
TEST_DJANGO = ".envs/.test/.django"
TEST_POSTGRES = ".envs/.test/.postgres"
PRODUCTION_DJANGO = ".envs/.production/.django"
PRODUCTION_POSTGRES = ".envs/.production/.postgres"


def always(context):
    return True


def with_celery(context):
    return context["use_celery"] == "y"


def with_prometheus(context):
    """Metrics through django-prometheus: a scrape presents a credential of its own."""
    return context["observability"] == "prometheus"


def with_headless(context):
    """Django Ninja with an identity provider: allauth's headless API signs the app's tokens."""
    return context["rest_api"] == "Django Ninja" and context["identity_provider"] != "none"


@dataclass(frozen=True)
class Secret:
    """One row of ``SECRETS``: a value drawn once and written over ``placeholder`` in each of ``files``."""

    placeholder: str
    """The name inside the ``!!!SET ...!!!`` marker of the template."""
    files: tuple[str, ...]
    """Where the value goes, relative to the project root; several files share the one value."""
    length: int = 64
    alphabet: str = ALPHANUMERIC
    debug: bool = True
    """Whether the ``debug`` answer replaces the value with ``DEBUG_VALUE``: the credentials a
    developer types, not the keys nothing needs to know."""
    applies: Callable[[dict], bool] = always
    """Whether the template renders the placeholder for the answers; a row that does not apply is skipped."""


# Secrets. Each row is one value drawn on generation. A value meant to be the same in
# several files is one row naming them all; the same placeholder in several rows is drawn
# afresh for each, so the environments share nothing else. Every file of an applicable row
# must exist and carry the placeholder: ``main`` fills the secrets before anything is
# pruned, and a placeholder the template renders only for some answers has a condition
# (tests/test_hooks.py checks the rows against the template's placeholder sites).
SECRETS = (
    # A deployed environment's own key: dev and test share production's settings module,
    # so nothing but a separate draw keeps a token minted for one from being accepted by
    # another.
    Secret("DJANGO_SECRET_KEY", (DEV_DJANGO,), debug=False),
    Secret("DJANGO_SECRET_KEY", (TEST_DJANGO,), debug=False),
    Secret("DJANGO_SECRET_KEY", (PRODUCTION_DJANGO,), debug=False),
    Secret("DJANGO_SECRET_KEY", ("config/settings/local.py",), debug=False),
    Secret("DJANGO_SECRET_KEY", ("config/settings/test.py",), debug=False),
    Secret("DJANGO_ADMIN_URL", (DEV_DJANGO,), length=32, debug=False),
    Secret("DJANGO_ADMIN_URL", (TEST_DJANGO,), length=32, debug=False),
    Secret("DJANGO_ADMIN_URL", (PRODUCTION_DJANGO,), length=32, debug=False),
    # One database role for every environment: pg_dump records the owner, so a backup
    # taken in one restores in the others.
    Secret(
        "POSTGRES_USER",
        (LOCAL_POSTGRES, DEV_POSTGRES, TEST_POSTGRES, PRODUCTION_POSTGRES),
        length=32,
        alphabet=LETTERS,
    ),
    Secret("POSTGRES_PASSWORD", (LOCAL_POSTGRES,)),
    Secret("POSTGRES_PASSWORD", (DEV_POSTGRES,)),
    Secret("POSTGRES_PASSWORD", (TEST_POSTGRES,)),
    Secret("POSTGRES_PASSWORD", (PRODUCTION_POSTGRES,)),
    # Flower's credentials are rendered with Celery only; its user is shared like the database role.
    Secret(
        "CELERY_FLOWER_USER",
        (LOCAL_DJANGO, DEV_DJANGO, TEST_DJANGO, PRODUCTION_DJANGO),
        length=32,
        alphabet=LETTERS,
        applies=with_celery,
    ),
    Secret("CELERY_FLOWER_PASSWORD", (LOCAL_DJANGO,), applies=with_celery),
    Secret("CELERY_FLOWER_PASSWORD", (DEV_DJANGO,), applies=with_celery),
    Secret("CELERY_FLOWER_PASSWORD", (TEST_DJANGO,), applies=with_celery),
    Secret("CELERY_FLOWER_PASSWORD", (PRODUCTION_DJANGO,), applies=with_celery),
    # The key allauth signs the single-page application's tokens with, one per environment.
    Secret("DJANGO_HEADLESS_JWT_PRIVATE_KEY", (DEV_DJANGO,), debug=False, applies=with_headless),
    Secret("DJANGO_HEADLESS_JWT_PRIVATE_KEY", (TEST_DJANGO,), debug=False, applies=with_headless),
    Secret("DJANGO_HEADLESS_JWT_PRIVATE_KEY", (PRODUCTION_DJANGO,), debug=False, applies=with_headless),
    Secret("DJANGO_HEADLESS_JWT_PRIVATE_KEY", ("config/settings/local.py",), debug=False, applies=with_headless),
    Secret("DJANGO_HEADLESS_JWT_PRIVATE_KEY", ("config/settings/test.py",), debug=False, applies=with_headless),
    # The credential a scrape presents, one per deployed environment so a token that
    # reads dev reads nothing else. The developer's machine declares a value instead.
    Secret("DJANGO_METRICS_TOKEN", (DEV_DJANGO,), debug=False, applies=with_prometheus),
    Secret("DJANGO_METRICS_TOKEN", (TEST_DJANGO,), debug=False, applies=with_prometheus),
    Secret("DJANGO_METRICS_TOKEN", (PRODUCTION_DJANGO,), debug=False, applies=with_prometheus),
)


# The committed example of a deployment's environment. No env file is ever committed, so
# this is where the generated tests and whoever deploys read the list of variables a
# deployment supplies; the values that would be secret are left unset.
EXAMPLE_DOTENV = ".env.example"
EXAMPLE_SOURCES = (PRODUCTION_DJANGO, PRODUCTION_POSTGRES)


def write_example_dotenv(root):
    """Write ``.env.example``: the production env files merged, every secret left unset.

    Called before ``fill_secrets``, while the placeholders are still in the files, so the
    example cannot declare anything but what a deployment actually reads.
    """
    lines = []
    for file in EXAMPLE_SOURCES:
        for line in (root / file).read_text().splitlines():
            name, separator, _ = line.partition("=")
            # A drawn value is the deployment's to set, and the trailing text of a line
            # like ``DJANGO_ADMIN_URL=!!!SET ...!!!/`` goes with it.
            lines.append(f"{name}=" if separator and "!!!SET " in line else line)
        lines.append("")
    (root / EXAMPLE_DOTENV).write_text("\n".join(lines))


def random_string(length, alphabet):
    """``length`` characters drawn from ``alphabet`` by the operating system's randomness."""
    return "".join(secrets.choice(alphabet) for _ in range(length))


def fill_secrets(root, context, draw=random_string):
    """Write a value for every applicable row of ``SECRETS`` into the project at ``root``.

    ``draw(length, alphabet)`` supplies the values. ``context`` holds the answers as the
    pre-generation hook passed them on. A file that is missing or has no placeholder is
    an error, so the rows must match what the template rendered.
    """
    debugging = context["debug"] == "y"
    for secret in SECRETS:
        if not secret.applies(context):
            continue
        value = DEBUG_VALUE if secret.debug and debugging else draw(secret.length, secret.alphabet)
        marker = f"!!!SET {secret.placeholder}!!!"
        for file in secret.files:
            path = root / file
            content = path.read_text()
            if marker not in content:
                msg = f"{file} has no {marker}"
                raise ValueError(msg)
            path.write_text(content.replace(marker, value))


# The agent guide. The template renders it once, under AGENT_GUIDE; every coding agent
# reads it under its own name, so ``place_agent_guide`` moves it there after pruning
# (docs/adr/0015). The ``none`` answer keeps no guide at all: that is a removal rule.
AGENT_GUIDE = "AGENTS.md"
AGENT_FILES = {
    "claude": "CLAUDE.md",
    "codex": AGENT_GUIDE,
    "cursor": AGENT_GUIDE,
    "copilot": ".github/copilot-instructions.md",
}


def place_agent_guide(context, root):
    """Move the guide of the project at ``root`` to the file its coding agent reads.

    Runs after pruning: the target may sit in a directory the answers dropped, as
    ``.github`` is dropped without GitHub Actions, and is then created for the guide.
    """
    agent = context["coding_agent"]
    if agent == "none":  # the removal rule deleted the guide
        return
    target = AGENT_FILES[agent]
    if target == AGENT_GUIDE:
        return
    path = root / target
    path.parent.mkdir(parents=True, exist_ok=True)
    (root / AGENT_GUIDE).rename(path)


# Removal rules. When a rule's condition holds for the answers, the paths
# listed with it are deleted from the generated project. Paths are relative to the
# project root; ``{project_slug}`` stands for the project package. For any answers,
# no path may be listed twice or under another listed path, so the rules can be
# applied in any order (tests/test_hooks.py checks this over every combination).
# Deletions that depend on what else is in the generated tree, like dropping a
# package once its last test is gone, are steps in ``prune`` rather than rules.
REMOVALS = (
    (lambda c: c["open_source_license"] == "Not open source", ("CONTRIBUTORS.txt", "LICENSE")),
    (lambda c: c["open_source_license"] != "GPLv3", ("COPYING",)),
    (
        lambda c: c["username_type"] == "username",
        ("{project_slug}/users/managers.py", "{project_slug}/users/tests/test_managers.py"),
    ),
    (
        lambda c: c["use_docker"] == "n",
        (
            "compose",
            "docker-compose.local.yml",
            "docker-compose.dev.yml",
            "docker-compose.test.yml",
            "docker-compose.production.yml",
            "docker-compose.docs.yml",
            ".dockerignore",
            "justfile",
        ),
    ),
    # The utility scripts set up a bare-metal server.
    (lambda c: c["use_docker"] == "y", ("utility",)),
    # nginx serves the media files when no cloud provider does.
    (lambda c: c["use_docker"] == "y" and c["cloud_provider"] != "None", ("compose/production/nginx",)),
    # The AWS image holds the S3 backup maintenance scripts.
    (lambda c: c["use_docker"] == "y" and c["cloud_provider"] != "AWS", ("compose/production/aws",)),
    # users/tasks.py and its tests stay: they also hold the Django Tasks example.
    (lambda c: c["use_celery"] == "n", ("config/celery_app.py",)),
    (
        lambda c: c["use_celery"] == "n" and c["use_docker"] == "y",
        ("compose/local/django/celery", "compose/production/django/celery"),
    ),
    (lambda c: c["ci_tool"] != "Gitlab", (".gitlab-ci.yml",)),
    (lambda c: c["ci_tool"] != "Github", (".github",)),
    # No coding agent, so no guide; every other answer moves it to the file that agent reads.
    (lambda c: c["coding_agent"] == "none", (AGENT_GUIDE,)),
    (lambda c: c["rest_api"] == "DRF", ("config/api.py", "{project_slug}/users/api/schema.py")),
    (
        lambda c: c["rest_api"] == "Django Ninja",
        ("config/api_router.py", "{project_slug}/users/api/serializers.py"),
    ),
    (
        lambda c: c["rest_api"] == "None",
        ("config/api_router.py", "config/api.py", "{project_slug}/users/api", "{project_slug}/users/tests/api"),
    ),
    # The websocket test goes in ``remove_channels_tests``, which also decides about its package.
    (lambda c: c["realtime"] != "channels", ("config/websocket.py",)),
    # The app that initialises the Sentry SDK, installed by the production settings.
    (lambda c: c["use_sentry"] == "n", ("{project_slug}/sentry", "{project_slug}/tests/test_sentry.py")),
    # Metrics: the endpoint a scrape reads, the Gunicorn configuration that retires the
    # samples of a worker that exited, and the page describing how to scrape them.
    (
        lambda c: c["observability"] != "prometheus",
        (
            "config/gunicorn.py",
            "docs/observability.rst",
            "{project_slug}/metrics.py",
            "{project_slug}/tests/test_metrics.py",
        ),
    ),
    # The local Prometheus reads the endpoint while developing; without Docker the
    # whole compose directory goes instead.
    (
        lambda c: c["observability"] != "prometheus" and c["use_docker"] == "y",
        ("compose/local/prometheus",),
    ),
    # Sign-in through the identity provider: its documentation, the check of its credentials and its tests.
    (
        lambda c: c["identity_provider"] == "none",
        (
            "docs/authentication.rst",
            "{project_slug}/users/checks.py",
            "{project_slug}/users/tests/social.py",
            "{project_slug}/users/tests/test_checks.py",
            "{project_slug}/users/tests/test_social_login.py",
        ),
    ),
    # The Entra provider subclass, handed out by the social account adapter.
    (
        lambda c: c["identity_provider"] != "entra",
        ("{project_slug}/users/providers.py", "{project_slug}/users/tests/test_providers.py"),
    ),
    # The app behind the single-page application's login: Django Ninja with a provider only.
    (lambda c: not with_headless(c), ("{project_slug}/identity",)),
)


def remove(path):
    """Delete ``path``, which must exist: a directory with everything in it, or a file."""
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def remove_channels_tests(root, project_slug):
    """Drop the websocket test, and the project-level tests package once nothing else is left in it."""
    tests_path = root / project_slug / "tests"
    (tests_path / "test_websocket.py").unlink()
    if all(path.name == "__init__.py" for path in tests_path.iterdir()):
        shutil.rmtree(tests_path)


def prune(context, root):
    """Remove the files the chosen options do not need from the project at ``root``.

    ``context`` holds the answers as the pre-generation hook passed them on: the
    yes/no answers are ``y`` or ``n``, lowercase.
    """
    project_slug = context["project_slug"]
    for applies, paths in REMOVALS:
        if applies(context):
            for path in paths:
                remove(root / path.format(project_slug=project_slug))
    if context["realtime"] != "channels":
        remove_channels_tests(root, project_slug)


def main(context):
    root = Path.cwd()
    write_example_dotenv(root)
    fill_secrets(root, context)

    if context["cloud_provider"] == "None" and context["use_docker"] == "n":
        print(
            WARNING + "You chose to not use any cloud providers nor Docker, "
            "media files won't be served in production." + TERMINATOR,
        )

    prune(context, root)
    place_agent_guide(context, root)

    print(SUCCESS + "Project initialized, keep up the good work!" + TERMINATOR)


if __name__ == "__main__":
    # Cookiecutter renders this file through Jinja before running it. The answers
    # enter here and nowhere else, as JSON so that free-text answers cannot break
    # the source, and the unrendered module stays importable for the tests. They
    # arrive as the pre-generation hook validated them, the yes/no answers lowercase.
    main(json.loads(r"""{{ cookiecutter | tojson }}"""))
