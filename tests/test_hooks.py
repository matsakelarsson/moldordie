"""Unit tests for the hooks"""

import re
from itertools import product
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

import pytest

from hooks.post_gen_project import AGENT_FILES
from hooks.post_gen_project import AGENT_GUIDE
from hooks.post_gen_project import ALPHANUMERIC
from hooks.post_gen_project import REMOVALS
from hooks.post_gen_project import SECRETS
from hooks.post_gen_project import fill_secrets
from hooks.post_gen_project import place_agent_guide
from hooks.post_gen_project import prune
from hooks.post_gen_project import random_string
from hooks.post_gen_project import remove_channels_tests
from hooks.post_gen_project import write_example_dotenv
from local_extensions import FREE_TEXT
from local_extensions import OPTIONS
from tests.answers import complete_answers
from tests.removal_coverage import removed_paths

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "{{cookiecutter.project_slug}}"
SLUG_PLACEHOLDER = "{{cookiecutter.project_slug}}"
PROJECT_SLUG = "my_test_project"


def context_of(*layers):
    """The context the hook receives for ``layers`` of answers on top of the defaults: what
    ``cookiecutter --no-input`` uses, with the project slug rendered."""
    return complete_answers({"project_slug": PROJECT_SLUG}, *layers)


# ``fill_secrets`` on hand-written placeholder files, through a generator the tests control.
#
# The sites below are written from the template, not read from the secrets table, so the
# table is checked against them: every site is filled by exactly one row.

# The deployed environments, in the order a change is promoted through them, and every
# environment including the developer's machine.
DEPLOYED_ENVIRONMENTS = ("dev", "test", "production")
ENVIRONMENTS = ("local", *DEPLOYED_ENVIRONMENTS)

# The placeholder sites of the template by file, in file order, as rendered with Celery,
# with Django Ninja and an identity provider, and with metrics; the Flower ones are not
# rendered without Celery, the headless key without Ninja and a provider, and the metrics
# token without django-prometheus.
PLACEHOLDER_SITES = {
    ".envs/.local/.django": ("CELERY_FLOWER_USER", "CELERY_FLOWER_PASSWORD"),
    ".envs/.local/.postgres": ("POSTGRES_USER", "POSTGRES_PASSWORD"),
    ".envs/.dev/.django": (
        "DJANGO_SECRET_KEY",
        "DJANGO_ADMIN_URL",
        "DJANGO_HEADLESS_JWT_PRIVATE_KEY",
        "DJANGO_METRICS_TOKEN",
        "CELERY_FLOWER_USER",
        "CELERY_FLOWER_PASSWORD",
    ),
    ".envs/.dev/.postgres": ("POSTGRES_USER", "POSTGRES_PASSWORD"),
    ".envs/.test/.django": (
        "DJANGO_SECRET_KEY",
        "DJANGO_ADMIN_URL",
        "DJANGO_HEADLESS_JWT_PRIVATE_KEY",
        "DJANGO_METRICS_TOKEN",
        "CELERY_FLOWER_USER",
        "CELERY_FLOWER_PASSWORD",
    ),
    ".envs/.test/.postgres": ("POSTGRES_USER", "POSTGRES_PASSWORD"),
    ".envs/.production/.django": (
        "DJANGO_SECRET_KEY",
        "DJANGO_ADMIN_URL",
        "DJANGO_HEADLESS_JWT_PRIVATE_KEY",
        "DJANGO_METRICS_TOKEN",
        "CELERY_FLOWER_USER",
        "CELERY_FLOWER_PASSWORD",
    ),
    ".envs/.production/.postgres": ("POSTGRES_USER", "POSTGRES_PASSWORD"),
    "config/settings/local.py": ("DJANGO_SECRET_KEY", "DJANGO_HEADLESS_JWT_PRIVATE_KEY"),
    "config/settings/test.py": ("DJANGO_SECRET_KEY", "DJANGO_HEADLESS_JWT_PRIVATE_KEY"),
}
FLOWER_PLACEHOLDERS = {"CELERY_FLOWER_USER", "CELERY_FLOWER_PASSWORD"}
HEADLESS_PLACEHOLDERS = {"DJANGO_HEADLESS_JWT_PRIVATE_KEY"}
HEADLESS_ANSWERS = {"rest_api": "Django Ninja", "identity_provider": "entra"}
METRICS_PLACEHOLDERS = {"DJANGO_METRICS_TOKEN"}
METRICS_ANSWERS = {"observability": "prometheus"}
# The sites that read one shared value: the database role, so that a backup restores across
# the environments, and Flower's user.
SHARED_SITES = (
    {(f".envs/.{environment}/.postgres", "POSTGRES_USER") for environment in ENVIRONMENTS},
    {(f".envs/.{environment}/.django", "CELERY_FLOWER_USER") for environment in ENVIRONMENTS},
)
# The sites the debug answer leaves random: nothing types a key or the admin URL.
RANDOM_IN_DEBUG = {
    *(
        (f".envs/.{environment}/.django", placeholder)
        for environment in DEPLOYED_ENVIRONMENTS
        for placeholder in (
            "DJANGO_SECRET_KEY",
            "DJANGO_ADMIN_URL",
            "DJANGO_HEADLESS_JWT_PRIVATE_KEY",
            "DJANGO_METRICS_TOKEN",
        )
    ),
    ("config/settings/local.py", "DJANGO_SECRET_KEY"),
    ("config/settings/local.py", "DJANGO_HEADLESS_JWT_PRIVATE_KEY"),
    ("config/settings/test.py", "DJANGO_SECRET_KEY"),
    ("config/settings/test.py", "DJANGO_HEADLESS_JWT_PRIVATE_KEY"),
}
PLACEHOLDER = re.compile(r"!!!SET (\w+)!!!")


def unfilled_project(root, *, with_celery, with_headless, with_metrics=True):
    """The placeholder sites as the template renders them, one ``NAME=!!!SET NAME!!!`` line each."""
    for file, names in PLACEHOLDER_SITES.items():
        path = root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = [
            name
            for name in names
            if (with_celery or name not in FLOWER_PLACEHOLDERS)
            and (with_headless or name not in HEADLESS_PLACEHOLDERS)
            and (with_metrics or name not in METRICS_PLACEHOLDERS)
        ]
        path.write_text("".join(f"{name}=!!!SET {name}!!!\n" for name in rendered))


def site_values(root):
    """What each placeholder site of the project at ``root`` holds, by ``(file, name)``."""
    return {
        (file, name): value
        for file in PLACEHOLDER_SITES
        for name, value in (line.split("=", 1) for line in (root / file).read_text().splitlines())
    }


class CountingDraw:
    """A generator standing in for the random one: distinct values, and a record of what was asked for."""

    def __init__(self):
        self.calls = []

    def __call__(self, length, alphabet):
        self.calls.append((length, alphabet))
        return f"drawn-{len(self.calls)}"


def test_placeholder_sites_are_those_of_the_template():
    """The hand-written sites are the template's, so the tests below fill what generation fills."""
    found = {}
    for path in TEMPLATE.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            names = PLACEHOLDER.findall(path.read_text(errors="ignore"))
            if names:
                found[path.relative_to(TEMPLATE).as_posix()] = tuple(names)
    assert found == PLACEHOLDER_SITES


def test_secrets_fill_every_placeholder_site_once():
    """A site in two rows would be drawn twice, one in no row would stay a placeholder."""
    listed = [(file, secret.placeholder) for secret in SECRETS for file in secret.files]
    assert len(listed) == len(set(listed))
    assert set(listed) == {(file, name) for file, names in PLACEHOLDER_SITES.items() for name in names}


def test_fill_secrets_draws_each_value_once(tmp_path):
    """The shared sites read one value and every other site its own: nothing is drawn twice or reused."""
    unfilled_project(tmp_path, with_celery=True, with_headless=True)
    draw = CountingDraw()
    fill_secrets(
        tmp_path,
        context_of({"use_celery": "y"}, HEADLESS_ANSWERS, METRICS_ANSWERS),
        draw=draw,
    )
    values = site_values(tmp_path)
    for shared in SHARED_SITES:
        assert len({values[site] for site in shared}) == 1
    assert len(set(values.values())) == len(values) - sum(len(shared) - 1 for shared in SHARED_SITES)
    assert len(draw.calls) == len(set(values.values()))
    assert not any("!!!SET" in value for value in values.values())


def test_fill_secrets_debug_fixes_the_credentials(tmp_path):
    """With debug, the credentials read ``debug``; the keys and the admin URL are still drawn."""
    unfilled_project(tmp_path, with_celery=True, with_headless=True)
    draw = CountingDraw()
    fill_secrets(
        tmp_path,
        context_of({"use_celery": "y", "debug": "y"}, HEADLESS_ANSWERS, METRICS_ANSWERS),
        draw=draw,
    )
    values = site_values(tmp_path)
    assert {site for site, value in values.items() if value == "debug"} == set(values) - RANDOM_IN_DEBUG
    assert len({values[site] for site in RANDOM_IN_DEBUG}) == len(RANDOM_IN_DEBUG)
    assert len(draw.calls) == len(RANDOM_IN_DEBUG)


def test_fill_secrets_skips_the_flower_rows_without_celery(tmp_path):
    """Without Celery the template renders no Flower placeholders, so their rows do not apply."""
    unfilled_project(tmp_path, with_celery=False, with_headless=True)
    draw = CountingDraw()
    fill_secrets(
        tmp_path,
        context_of({"use_celery": "n"}, HEADLESS_ANSWERS, METRICS_ANSWERS),
        draw=draw,
    )
    values = site_values(tmp_path)
    assert not any(name in FLOWER_PLACEHOLDERS for _, name in values)
    assert not any("!!!SET" in value for value in values.values())
    assert len(draw.calls) == len(set(values.values()))


@pytest.mark.parametrize(
    "answers",
    [
        {"rest_api": "Django Ninja", "identity_provider": "none"},
        {"rest_api": "DRF", "identity_provider": "entra"},
        {"rest_api": "None", "identity_provider": "google"},
    ],
    ids=lambda answers: "-".join(answers.values()),
)
def test_fill_secrets_skips_the_headless_key_without_ninja_and_a_provider(tmp_path, answers):
    """Only Django Ninja with a provider renders the key allauth signs the app's tokens with."""
    unfilled_project(tmp_path, with_celery=True, with_headless=False)
    draw = CountingDraw()
    fill_secrets(tmp_path, context_of({"use_celery": "y"}, answers, METRICS_ANSWERS), draw=draw)
    values = site_values(tmp_path)
    assert not any(name in HEADLESS_PLACEHOLDERS for _, name in values)
    assert not any("!!!SET" in value for value in values.values())
    assert len(draw.calls) == len(set(values.values()))


def test_fill_secrets_fails_on_a_missing_file(tmp_path):
    unfilled_project(tmp_path, with_celery=True, with_headless=False)
    (tmp_path / "config" / "settings" / "test.py").unlink()
    with pytest.raises(FileNotFoundError):
        fill_secrets(tmp_path, context_of({"use_celery": "y"}), draw=CountingDraw())


def test_fill_secrets_fails_on_a_missing_placeholder(tmp_path):
    """A row for a placeholder the template did not render is an error, not a silent no-op."""
    unfilled_project(tmp_path, with_celery=False, with_headless=False)
    with pytest.raises(ValueError, match="CELERY_FLOWER_USER"):
        fill_secrets(tmp_path, context_of({"use_celery": "y"}), draw=CountingDraw())


def test_random_string():
    """The default generator draws the requested length from the alphabet, and does not repeat itself."""
    length = 64
    drawn = random_string(length, ALPHANUMERIC)
    assert len(drawn) == length
    assert set(drawn) <= set(ALPHANUMERIC)
    assert drawn != random_string(length, ALPHANUMERIC)


@pytest.fixture
def channels_tests(tmp_path):
    """The project-level tests package as generated with ``realtime=channels``."""
    tests_path = tmp_path / PROJECT_SLUG / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "__init__.py").touch()
    (tests_path / "test_websocket.py").touch()
    return tests_path


def test_remove_channels_tests_drops_the_package_when_only_the_websocket_test_lives_there(tmp_path, channels_tests):
    remove_channels_tests(tmp_path, PROJECT_SLUG)
    assert not channels_tests.exists()


def test_remove_channels_tests_keeps_other_tests(tmp_path, channels_tests):
    other_test = channels_tests / "test_urls.py"
    other_test.touch()
    remove_channels_tests(tmp_path, PROJECT_SLUG)
    assert not (channels_tests / "test_websocket.py").exists()
    assert other_test.exists()
    assert (channels_tests / "__init__.py").exists()


# ``write_example_dotenv`` on hand-written env files: no env file is committed, so the example
# is what a checkout reads the deployment's variables from, and it is derived rather than
# written by hand so that it cannot declare anything else.


def test_write_example_dotenv_merges_the_files_and_unsets_the_drawn_values(tmp_path):
    for file, content in {
        ".envs/.production/.django": (
            "# General\n"
            "# DJANGO_READ_DOT_ENV_FILE=True\n"
            "DJANGO_SETTINGS_MODULE=config.settings.production\n"
            "DJANGO_SECRET_KEY=!!!SET DJANGO_SECRET_KEY!!!\n"
            "DJANGO_ADMIN_URL=!!!SET DJANGO_ADMIN_URL!!!/\n"
            "WEB_CONCURRENCY=4\n"
            "DJANGO_SERVER_EMAIL=\n"
        ),
        ".envs/.production/.postgres": "POSTGRES_DB=my_project\nPOSTGRES_USER=!!!SET POSTGRES_USER!!!\n",
    }.items():
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    write_example_dotenv(tmp_path)

    assert (tmp_path / ".env.example").read_text() == (
        "# General\n"
        # A commented-out line carries no value to unset.
        "# DJANGO_READ_DOT_ENV_FILE=True\n"
        "DJANGO_SETTINGS_MODULE=config.settings.production\n"
        # The drawn values, and the trailing slash of the admin URL, are the deployment's to set.
        "DJANGO_SECRET_KEY=\n"
        "DJANGO_ADMIN_URL=\n"
        "WEB_CONCURRENCY=4\n"
        "DJANGO_SERVER_EMAIL=\n"
        "\n"
        "POSTGRES_DB=my_project\n"
        "POSTGRES_USER=\n"
    )


def test_write_example_dotenv_runs_before_the_secrets_are_filled():
    """Afterwards the placeholders are gone and the example would carry the drawn values."""
    source = REPO / "{{cookiecutter.project_slug}}" / ".envs" / ".production" / ".django"
    assert "!!!SET DJANGO_SECRET_KEY!!!" in source.read_text(), source
    body = (REPO / "hooks" / "post_gen_project.py").read_text().partition("def main(context):")[2]
    assert body.index("write_example_dotenv(root)") < body.index("fill_secrets(root, context)")


# ``prune`` on a copy of the template tree, checked against hand-written expectations.
#
# The expectations below are written from ``cookiecutter.json`` and the generation-options
# docs, not derived from the hook, so they exercise the deletion code independently of how
# it is organised. Every test asserts the complete set of removed files and directories, so
# an unexpected deletion fails without maintaining a survivor list.


@pytest.fixture
def unpruned_project(tmp_path):
    """Every path of the template as an empty file or directory, with the slug rendered."""
    root = tmp_path / PROJECT_SLUG
    for path in TEMPLATE.rglob("*"):
        parts = path.relative_to(TEMPLATE).parts
        if "__pycache__" in parts:
            continue
        target = root.joinpath(*(part.replace(SLUG_PLACEHOLDER, PROJECT_SLUG) for part in parts))
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
    return root


def listing(root):
    """Every file and directory below ``root``, relative to it."""
    return {path.relative_to(root) for path in root.rglob("*")}


def below(paths, targets):
    """The paths that are one of ``targets`` or lie under one."""
    targets = {Path(target) for target in targets}
    return {path for path in paths if path in targets or any(parent in targets for parent in path.parents)}


def assert_prunes(root, expected_targets, **answers):
    """``prune`` removes exactly ``expected_targets`` and their contents, nothing else."""
    before = listing(root)
    missing = {Path(target) for target in expected_targets} - before
    assert not missing, f"expected targets are not in the template: {sorted(map(str, missing))}"
    prune(context_of(answers), root)
    assert before - listing(root) == below(before, expected_targets)


# Hand-written removal targets, relative to the project root, grouped by the answer that causes them.
PKG = PROJECT_SLUG
NOT_GPL = {"COPYING"}
CLOSED_SOURCE = {"LICENSE", "CONTRIBUTORS.txt"}
USERNAME_LOGIN = {f"{PKG}/users/managers.py", f"{PKG}/users/tests/test_managers.py"}
NO_DOCKER = {
    "compose",
    "docker-compose.local.yml",
    "docker-compose.dev.yml",
    "docker-compose.test.yml",
    "docker-compose.production.yml",
    "docker-compose.docs.yml",
    ".dockerignore",
    "justfile",
}
DOCKER = {"utility"}  # the bare-metal helper scripts
NO_NGINX = {"compose/production/nginx"}
NO_AWS_IMAGE = {"compose/production/aws"}
NO_CELERY = {"config/celery_app.py"}
NO_CELERY_IMAGES = {"compose/local/django/celery", "compose/production/django/celery"}
CI_CONFIGS = {"Gitlab": ".gitlab-ci.yml", "Github": ".github"}
NO_CI = set(CI_CONFIGS.values())
NO_DRF = {"config/api_router.py", f"{PKG}/users/api/serializers.py"}
NO_NINJA = {"config/api.py", f"{PKG}/users/api/schema.py"}
NO_REST_API = {"config/api_router.py", "config/api.py", f"{PKG}/users/api", f"{PKG}/users/tests/api"}
NO_CHANNELS = {"config/websocket.py", f"{PKG}/tests/test_websocket.py"}
NO_SENTRY = {f"{PKG}/sentry", f"{PKG}/tests/test_sentry.py"}
# The metrics endpoint a scrape reads, and the app that exports over OTLP. The Gunicorn
# configuration and the page belong to either arm, so they go only where neither was
# chosen; each arm's local receiver goes with the images.
NO_METRICS = {f"{PKG}/metrics.py", f"{PKG}/tests/test_metrics.py"}
NO_TELEMETRY = {f"{PKG}/telemetry", f"{PKG}/tests/test_telemetry.py"}
NO_OBSERVABILITY = {"config/gunicorn.py", "docs/observability.rst"}
NO_METRICS_IMAGES = {"compose/local/prometheus"}
NO_TELEMETRY_IMAGES = {"compose/local/otel-collector"}
NO_IDENTITY_PROVIDER = {
    "docs/authentication.rst",
    f"{PKG}/users/checks.py",
    f"{PKG}/users/tests/social.py",
    f"{PKG}/users/tests/test_checks.py",
    f"{PKG}/users/tests/test_social_login.py",
}
NOT_ENTRA = {f"{PKG}/users/providers.py", f"{PKG}/users/tests/test_providers.py"}
# The app behind the calling services, and with Django Ninja the single-page
# application's login too: a provider that something reads a token from
NO_IDENTITY_APP = {f"{PKG}/identity"}
# Without Django Ninja the verifier and the registrations stay and the API's side goes
NO_IDENTITY_API = {
    f"{PKG}/identity/api.py",
    f"{PKG}/identity/auth.py",
    f"{PKG}/identity/frontend.py",
    f"{PKG}/identity/management",
    f"{PKG}/identity/permissions.py",
    f"{PKG}/identity/tests/conftest.py",
    f"{PKG}/identity/tests/headless.py",
    f"{PKG}/identity/tests/test_apps.py",
    f"{PKG}/identity/tests/test_auth.py",
    f"{PKG}/identity/tests/test_frontend.py",
    f"{PKG}/identity/tests/test_login.py",
    f"{PKG}/identity/tests/test_permissions.py",
    f"{PKG}/identity/tests/test_provider_login.py",
    f"{PKG}/identity/tests/test_revoke_jwt_sessions.py",
    f"{PKG}/identity/tests/test_services.py",
}
# The checks are the headless login's and Entra's, so the module goes with neither
NO_IDENTITY_CHECKS = {f"{PKG}/identity/checks.py"}
# The permission a scrape must hold, declared where there are metrics to read
NO_METRICS_PERMISSION = {f"{PKG}/identity/migrations/0002_the_metrics_permission.py"}
# No coding agent, so no guide for one; every other answer moves it where that agent reads it.
NO_AGENT_GUIDE = {AGENT_GUIDE}

# cookiecutter.json defaults: MIT, username login, no Docker, AWS, no Celery, no CI,
# no REST API, no identity provider, no Channels, no Sentry, no metrics, no coding agent.
DEFAULTS = (
    NOT_GPL
    | USERNAME_LOGIN
    | NO_DOCKER
    | NO_CELERY
    | NO_CI
    | NO_REST_API
    | NO_IDENTITY_PROVIDER
    | NOT_ENTRA
    | NO_IDENTITY_APP
    | NO_CHANNELS
    | NO_SENTRY
    | NO_METRICS
    | NO_TELEMETRY
    | NO_OBSERVABILITY
    | NO_AGENT_GUIDE
)
# Docker on, everything else at its default: the helper scripts go instead of compose, and
# the images of the options that are off go with it.
WITH_DOCKER = (DEFAULTS - NO_DOCKER) | DOCKER | NO_CELERY_IMAGES | NO_METRICS_IMAGES | NO_TELEMETRY_IMAGES


def test_prune_with_the_default_answers(unpruned_project):
    assert_prunes(unpruned_project, DEFAULTS)


def test_prune_fails_on_a_missing_target(unpruned_project):
    (unpruned_project / "COPYING").unlink()
    with pytest.raises(FileNotFoundError):
        prune(context_of(), unpruned_project)


@pytest.mark.parametrize(
    ("open_source_license", "expected"),
    [
        ("MIT", DEFAULTS),
        ("GPLv3", DEFAULTS - NOT_GPL),
        ("Not open source", DEFAULTS | CLOSED_SOURCE),
    ],
)
def test_prune_license_files(unpruned_project, open_source_license, expected):
    assert_prunes(unpruned_project, expected, open_source_license=open_source_license)


@pytest.mark.parametrize(
    ("username_type", "expected"),
    [("username", DEFAULTS), ("email", DEFAULTS - USERNAME_LOGIN)],
)
def test_prune_custom_user_manager(unpruned_project, username_type, expected):
    assert_prunes(unpruned_project, expected, username_type=username_type)


@pytest.mark.parametrize(
    ("use_docker", "cloud_provider", "expected"),
    [
        # Docker off: all of compose goes, whatever serves the media files.
        ("n", "None", DEFAULTS),
        ("n", "AWS", DEFAULTS),
        # Docker on, no cloud: nginx serves the media files, the AWS image is not needed.
        ("y", "None", WITH_DOCKER | NO_AWS_IMAGE),
        # Docker on, AWS: the AWS image stays for the backups, nginx is not needed.
        ("y", "AWS", WITH_DOCKER | NO_NGINX),
    ],
)
def test_prune_docker_and_cloud_provider(unpruned_project, use_docker, cloud_provider, expected):
    assert_prunes(unpruned_project, expected, use_docker=use_docker, cloud_provider=cloud_provider)


@pytest.mark.parametrize(
    ("use_docker", "use_celery", "expected"),
    [
        ("n", "n", DEFAULTS),
        ("n", "y", DEFAULTS - NO_CELERY),
        ("y", "n", WITH_DOCKER | NO_NGINX),
        ("y", "y", (WITH_DOCKER | NO_NGINX) - NO_CELERY - NO_CELERY_IMAGES),
    ],
)
def test_prune_docker_and_celery(unpruned_project, use_docker, use_celery, expected):
    assert_prunes(unpruned_project, expected, use_docker=use_docker, use_celery=use_celery)


@pytest.mark.parametrize("ci_tool", ["None", "Gitlab", "Github"])
def test_prune_keeps_only_the_chosen_ci_config(unpruned_project, ci_tool):
    other_configs = {path for tool, path in CI_CONFIGS.items() if tool != ci_tool}
    assert_prunes(unpruned_project, (DEFAULTS - NO_CI) | other_configs, ci_tool=ci_tool)


@pytest.mark.parametrize("coding_agent", list(OPTIONS["coding_agent"].choices))
def test_prune_keeps_the_agent_guide_for_every_agent(unpruned_project, coding_agent):
    """Only ``none`` drops the guide; the others keep it for ``place_agent_guide`` to move."""
    kept = DEFAULTS - NO_AGENT_GUIDE if coding_agent != "none" else DEFAULTS
    assert_prunes(unpruned_project, kept, coding_agent=coding_agent)


@pytest.mark.parametrize(
    ("rest_api", "expected"),
    [
        ("None", DEFAULTS),
        ("DRF", (DEFAULTS - NO_REST_API) | NO_NINJA),
        ("Django Ninja", (DEFAULTS - NO_REST_API) | NO_DRF),
    ],
)
def test_prune_rest_api_starter_files(unpruned_project, rest_api, expected):
    assert_prunes(unpruned_project, expected, rest_api=rest_api)


@pytest.mark.parametrize(
    ("realtime", "expected"),
    [
        # The project-level tests package survives: it also holds tests not tied to Channels.
        ("none", DEFAULTS),
        ("channels", DEFAULTS - NO_CHANNELS),
    ],
)
def test_prune_channels_files(unpruned_project, realtime, expected):
    assert_prunes(unpruned_project, expected, realtime=realtime)


@pytest.mark.parametrize(
    ("use_sentry", "expected"),
    [("n", DEFAULTS), ("y", DEFAULTS - NO_SENTRY)],
)
def test_prune_sentry_app(unpruned_project, use_sentry, expected):
    assert_prunes(unpruned_project, expected, use_sentry=use_sentry)


# Each arm keeps its own files, the Gunicorn configuration and the page both arms write
# to, and, with Docker, its receiver; without Docker the receivers go with the rest of
# the compose directory.
KEPT_BY_PROMETHEUS = NO_METRICS | NO_OBSERVABILITY
KEPT_BY_TELEMETRY = NO_TELEMETRY | NO_OBSERVABILITY


@pytest.mark.parametrize(
    ("use_docker", "observability", "expected"),
    [
        ("n", "none", DEFAULTS),
        ("n", "prometheus", DEFAULTS - KEPT_BY_PROMETHEUS),
        ("n", "opentelemetry", DEFAULTS - KEPT_BY_TELEMETRY),
        ("y", "none", WITH_DOCKER | NO_NGINX),
        ("y", "prometheus", (WITH_DOCKER | NO_NGINX) - KEPT_BY_PROMETHEUS - NO_METRICS_IMAGES),
        ("y", "opentelemetry", (WITH_DOCKER | NO_NGINX) - KEPT_BY_TELEMETRY - NO_TELEMETRY_IMAGES),
    ],
)
def test_prune_observability_files(unpruned_project, use_docker, observability, expected):
    assert_prunes(unpruned_project, expected, use_docker=use_docker, observability=observability)


@pytest.mark.parametrize(
    ("identity_provider", "expected"),
    [
        ("none", DEFAULTS),
        # The provider subclass exists for Entra only
        ("entra", DEFAULTS - NO_IDENTITY_PROVIDER - NOT_ENTRA),
        ("google", DEFAULTS - NO_IDENTITY_PROVIDER),
    ],
)
def test_prune_identity_provider_files(unpruned_project, identity_provider, expected):
    assert_prunes(unpruned_project, expected, identity_provider=identity_provider)


# With the default answers nothing reads the metrics, so the app that survives keeps no
# permission to read them.
KEPT = NO_IDENTITY_APP | NO_METRICS_PERMISSION


@pytest.mark.parametrize(
    ("rest_api", "identity_provider", "expected"),
    [
        ("Django Ninja", "none", (DEFAULTS - NO_REST_API) | NO_DRF),
        ("DRF", "entra", (DEFAULTS - NO_REST_API - NO_IDENTITY_PROVIDER - NOT_ENTRA) | NO_NINJA),
        (
            "Django Ninja",
            "entra",
            (DEFAULTS - NO_REST_API - NO_IDENTITY_PROVIDER - NOT_ENTRA - KEPT) | NO_DRF | NO_METRICS_PERMISSION,
        ),
        (
            "Django Ninja",
            "google",
            (DEFAULTS - NO_REST_API - NO_IDENTITY_PROVIDER - KEPT) | NO_DRF | NO_METRICS_PERMISSION,
        ),
    ],
)
def test_prune_identity_app(unpruned_project, rest_api, identity_provider, expected):
    assert_prunes(unpruned_project, expected, rest_api=rest_api, identity_provider=identity_provider)


# Metrics and a provider, so a scrape may present a token of the provider's: the verifier
# and the registrations are generated whether or not the API that also reads them is.
WITH_METRICS = DEFAULTS - KEPT_BY_PROMETHEUS - NO_IDENTITY_APP - NO_IDENTITY_PROVIDER


@pytest.mark.parametrize(
    ("rest_api", "identity_provider", "expected"),
    [
        ("None", "entra", (WITH_METRICS - NOT_ENTRA) | NO_IDENTITY_API),
        ("None", "google", WITH_METRICS | NO_IDENTITY_API | NO_IDENTITY_CHECKS),
        ("DRF", "entra", (WITH_METRICS - NO_REST_API - NOT_ENTRA) | NO_NINJA | NO_IDENTITY_API),
        ("Django Ninja", "entra", (WITH_METRICS - NO_REST_API - NOT_ENTRA) | NO_DRF),
    ],
)
def test_prune_machine_authentication(unpruned_project, rest_api, identity_provider, expected):
    assert_prunes(
        unpruned_project,
        expected,
        rest_api=rest_api,
        identity_provider=identity_provider,
        observability="prometheus",
    )


# The removal rules checked for self-consistency over every combination of the answers they
# read. This shows the table can be applied in any order and that every listed path is in the
# template, not that the rules are right: the behaviour tests above cover that for
# representative answers.

# The answers the removal rules read. Reading any other answer fails the guard below, because
# the rules would then not be checked over that answer's values.
REMOVAL_OPTIONS = (
    "open_source_license",
    "username_type",
    "use_docker",
    "cloud_provider",
    "use_celery",
    "ci_tool",
    "rest_api",
    "identity_provider",
    "realtime",
    "use_sentry",
    "observability",
    "coding_agent",
)


class RemovalContext(dict):
    """Answers for the removal rules, recording the ones read; reading any other is a failure."""

    accessed: ClassVar[set[str]] = set()

    def __getitem__(self, key):
        self.accessed.add(key)
        return super().__getitem__(key)

    def __missing__(self, key):
        msg = f"the removal rules read {key!r}, which is not in REMOVAL_OPTIONS"
        raise AssertionError(msg)

    def get(self, key, default=None):
        return self[key]

    def __contains__(self, key):
        return super().__contains__(key) or self.__missing__(key)


def option_domains():
    """Every value each removal-relevant answer can take, in ``cookiecutter.json`` order."""
    domains = {}
    for name in REMOVAL_OPTIONS:
        option = OPTIONS[name]
        assert option.kind != FREE_TEXT, f"{name} is free text, so its values cannot be enumerated"
        domains[name] = option.choices
    return domains


def removal_contexts():
    """A guarded context for every combination of the removal-relevant answers."""
    domains = option_domains()
    for values in product(*domains.values()):
        yield RemovalContext(zip(domains, values, strict=True))


def removal_targets(context):
    """The paths the removal rules delete for ``context``, one entry per listing."""
    return [PurePosixPath(path.format(project_slug=PROJECT_SLUG)) for path in removed_paths(REMOVALS, context)]


def test_removal_rules_delete_each_path_at_most_once():
    """For any answers, no path is listed twice, or together with a path above it."""
    # The listed paths depend only on which rules apply, so each combination of those is checked once.
    contexts_by_applying_rules = {}
    for context in removal_contexts():
        applying = tuple(applies(context) for applies, _ in REMOVALS)
        contexts_by_applying_rules.setdefault(applying, context)
    assert RemovalContext.accessed == set(REMOVAL_OPTIONS)
    for context in contexts_by_applying_rules.values():
        targets = removal_targets(context)
        target_set = set(targets)
        assert len(targets) == len(target_set), f"a path is listed twice for {dict(context)}"
        nested = [target for target in targets if any(parent in target_set for parent in target.parents)]
        assert not nested, f"paths listed under another listed path for {dict(context)}: {nested}"


def test_removal_rules_list_paths_of_the_template():
    """A renamed or dropped template file fails here rather than in every generation test."""
    missing = [
        path
        for _, paths in REMOVALS
        for path in paths
        if not (TEMPLATE / path.format(project_slug=SLUG_PLACEHOLDER)).exists()
    ]
    assert not missing


# ``place_agent_guide`` on a hand-written guide: the template renders it once, and the hook
# moves it to the file the chosen coding agent reads (docs/adr/0015).

GUIDE_TEXT = "# My Test Project\n\nInstructions for AI coding agents.\n"


@pytest.fixture
def generated_guide(tmp_path):
    """A project holding the guide where the template rendered it."""
    (tmp_path / AGENT_GUIDE).write_text(GUIDE_TEXT)
    return tmp_path


def test_agent_files_name_a_file_for_every_agent():
    """Every answer but ``none``, whose guide the removal rule deleted, reads the guide somewhere."""
    assert set(AGENT_FILES) | {"none"} == set(OPTIONS["coding_agent"].choices)


@pytest.mark.parametrize("coding_agent", list(AGENT_FILES))
def test_place_agent_guide_leaves_the_guide_where_its_agent_reads_it(generated_guide, coding_agent):
    place_agent_guide(context_of({"coding_agent": coding_agent}), generated_guide)

    target = AGENT_FILES[coding_agent]
    assert (generated_guide / target).read_text() == GUIDE_TEXT
    assert [path.relative_to(generated_guide).as_posix() for path in generated_guide.rglob("*") if path.is_file()] == [
        target,
    ]


def test_place_agent_guide_creates_the_directory_its_agent_reads_from(generated_guide):
    """Without GitHub Actions the answers dropped ``.github``, which Copilot's guide still needs."""
    assert not (generated_guide / ".github").exists()

    place_agent_guide(context_of({"coding_agent": "copilot"}), generated_guide)

    assert (generated_guide / ".github" / "copilot-instructions.md").read_text() == GUIDE_TEXT


def test_place_agent_guide_moves_nothing_without_an_agent(tmp_path):
    """The removal rule deleted the guide, so there is nothing left to place."""
    place_agent_guide(context_of({"coding_agent": "none"}), tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_place_agent_guide_runs_after_pruning():
    """Beforehand, pruning would delete the directory Copilot's guide was moved into."""
    body = (REPO / "hooks" / "post_gen_project.py").read_text().partition("def main(context):")[2]
    assert body.index("prune(context, root)") < body.index("place_agent_guide(context, root)")
