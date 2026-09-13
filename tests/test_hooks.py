"""Unit tests for the hooks"""

import json
import os
from itertools import product
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

import pytest

from hooks.post_gen_project import FLAG_OPTIONS
from hooks.post_gen_project import REMOVALS
from hooks.post_gen_project import append_to_gitignore_file
from hooks.post_gen_project import envs_unused
from hooks.post_gen_project import normalize_context
from hooks.post_gen_project import prune
from hooks.post_gen_project import remove_channels_tests

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "{{cookiecutter.project_slug}}"
SLUG_PLACEHOLDER = "{{cookiecutter.project_slug}}"
PROJECT_SLUG = "my_test_project"


@pytest.fixture
def working_directory(tmp_path):
    prev_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev_cwd)


def test_append_to_gitignore_file(working_directory):
    gitignore_file = working_directory / ".gitignore"
    gitignore_file.write_text("node_modules/\n")
    append_to_gitignore_file(".envs/*")
    linesep = os.linesep.encode()
    assert gitignore_file.read_bytes() == b"node_modules/" + linesep + b".envs/*" + linesep
    assert gitignore_file.read_text() == "node_modules/\n.envs/*\n"


def test_normalize_context_lowercases_only_the_flags_on_a_copy():
    context = {"use_docker": "Y", "cloud_provider": "AWS", "project_name": "Yes Project"}
    assert normalize_context(context) == {
        "use_docker": "y",
        "cloud_provider": "AWS",
        "project_name": "Yes Project",
    }
    assert context["use_docker"] == "Y"


@pytest.mark.parametrize(
    ("use_docker", "use_heroku", "expected"),
    [("n", "n", True), ("y", "n", False), ("n", "y", False), ("y", "y", False)],
)
def test_envs_unused_when_neither_docker_nor_heroku(use_docker, use_heroku, expected):
    assert envs_unused({"use_docker": use_docker, "use_heroku": use_heroku}) is expected


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


# ``prune`` on a copy of the template tree, checked against hand-written expectations.
#
# The expectations below are written from ``cookiecutter.json`` and the generation-options
# docs, not derived from the hook, so they exercise the deletion code independently of how
# it is organised. Every test asserts the complete set of removed files and directories, so
# an unexpected deletion fails without maintaining a survivor list.


def default_context():
    """The answers ``cookiecutter --no-input`` uses: the first choice, or the value itself."""
    options = json.loads((REPO / "cookiecutter.json").read_text())
    context = {
        option: choices[0] if isinstance(choices, list) else choices
        for option, choices in options.items()
        if not option.startswith("_")
    }
    context["project_slug"] = PROJECT_SLUG
    return context


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
    prune({**default_context(), **answers}, root)
    assert before - listing(root) == below(before, expected_targets)


# Hand-written removal targets, relative to the project root, grouped by the answer that causes them.
PKG = PROJECT_SLUG
NOT_GPL = {"COPYING"}
CLOSED_SOURCE = {"LICENSE", "CONTRIBUTORS.txt"}
USERNAME_LOGIN = {f"{PKG}/users/managers.py", f"{PKG}/users/tests/test_managers.py"}
NO_DOCKER = {
    "compose",
    "docker-compose.local.yml",
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
NO_HEROKU = {"Procfile", "bin"}
UNUSED_ENVS = {".envs", "merge_production_dotenvs_in_dotenv.py", "tests"}
CI_CONFIGS = {"Gitlab": ".gitlab-ci.yml", "Github": ".github"}
NO_CI = set(CI_CONFIGS.values())
NO_DRF = {"config/api_router.py", f"{PKG}/users/api/serializers.py"}
NO_NINJA = {"config/api.py", f"{PKG}/users/api/schema.py"}
NO_REST_API = {"config/api_router.py", "config/api.py", f"{PKG}/users/api", f"{PKG}/users/tests/api"}
NO_CHANNELS = {"config/websocket.py", f"{PKG}/tests/test_websocket.py"}

# cookiecutter.json defaults: MIT, username login, no Docker, AWS, no Celery, no Heroku,
# envs kept, no CI, no REST API, no Channels.
DEFAULTS = NOT_GPL | USERNAME_LOGIN | NO_DOCKER | NO_HEROKU | NO_CELERY | NO_CI | NO_REST_API | NO_CHANNELS
# Docker on, everything else at its default: the helper scripts and the Celery images go instead of compose.
WITH_DOCKER = (DEFAULTS - NO_DOCKER) | DOCKER | NO_CELERY_IMAGES


def test_prune_with_the_default_answers(unpruned_project):
    assert_prunes(unpruned_project, DEFAULTS)


def test_prune_reads_the_flags_case_insensitively(unpruned_project):
    assert_prunes(unpruned_project, WITH_DOCKER | NO_NGINX, use_docker="Y")


def test_prune_fails_on_a_missing_target(unpruned_project):
    (unpruned_project / "Procfile").unlink()
    with pytest.raises(FileNotFoundError):
        prune(default_context(), unpruned_project)


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


@pytest.mark.parametrize(
    ("use_docker", "use_heroku", "keep_local_envs_in_vcs", "expected"),
    [
        # The envs only go when nothing uses them and the user did not ask to keep them.
        ("n", "n", "n", DEFAULTS | UNUSED_ENVS),
        ("n", "n", "y", DEFAULTS),
        ("y", "n", "n", WITH_DOCKER | NO_NGINX),
        ("n", "y", "n", DEFAULTS - NO_HEROKU),
        ("n", "y", "y", DEFAULTS - NO_HEROKU),
        ("y", "y", "n", (WITH_DOCKER | NO_NGINX) - NO_HEROKU),
    ],
)
def test_prune_docker_heroku_and_envs(unpruned_project, use_docker, use_heroku, keep_local_envs_in_vcs, expected):
    assert_prunes(
        unpruned_project,
        expected,
        use_docker=use_docker,
        use_heroku=use_heroku,
        keep_local_envs_in_vcs=keep_local_envs_in_vcs,
    )


@pytest.mark.parametrize("ci_tool", ["None", "Gitlab", "Github"])
def test_prune_keeps_only_the_chosen_ci_config(unpruned_project, ci_tool):
    other_configs = {path for tool, path in CI_CONFIGS.items() if tool != ci_tool}
    assert_prunes(unpruned_project, (DEFAULTS - NO_CI) | other_configs, ci_tool=ci_tool)


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
    "use_heroku",
    "keep_local_envs_in_vcs",
    "use_celery",
    "ci_tool",
    "rest_api",
    "realtime",
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
    options = json.loads((REPO / "cookiecutter.json").read_text())
    domains = {}
    for option in REMOVAL_OPTIONS:
        if isinstance(options[option], list):
            domains[option] = tuple(options[option])
        else:
            assert option in FLAG_OPTIONS, f"{option} is free text, so its values cannot be enumerated"
            domains[option] = ("y", "n")
    return domains


def removal_contexts():
    """A guarded context for every combination of the removal-relevant answers."""
    domains = option_domains()
    for values in product(*domains.values()):
        yield RemovalContext(zip(domains, values, strict=True))


def removal_targets(context):
    """The paths the removal rules delete for ``context``, one entry per listing."""
    return [
        PurePosixPath(path.format(project_slug=PROJECT_SLUG))
        for applies, paths in REMOVALS
        if applies(context)
        for path in paths
    ]


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
