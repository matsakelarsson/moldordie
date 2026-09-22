import ast  # noqa: EXE002
import json
import os
import re
import shutil
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest
import sh
import yaml
from binaryornot.check import is_binary
from cookiecutter.exceptions import FailedHookException

from hooks.post_gen_project import REMOVALS
from local_extensions import FLAG
from local_extensions import LIST
from local_extensions import OPTIONS
from local_extensions import option_names
from tests.answers import complete_answers
from tests.answers import unknown_answers
from tests.citations import Allowance
from tests.citations import citations
from tests.generated_project import NO_DEFAULT
from tests.generated_project import EnvRead
from tests.generated_project import Expression
from tests.generated_project import GeneratedProject
from tests.generated_project import PythonModule
from tests.removal_coverage import MOST_CHANGED_ANSWERS
from tests.removal_coverage import coverage_gaps
from tests.removal_coverage import fewest_answers_keeping
from tests.removal_coverage import paths_kept
from tests.removal_coverage import removed_paths

PATTERN = r"{{(\s?cookiecutter)[.](.*?)}}"
RE_OBJ = re.compile(PATTERN)
# A secret the post-generation hook did not fill in
RE_PLACEHOLDER = re.compile(r"!!!SET \w+!!!")
# <script src="http(s)://..."> or <link href="http(s)://...">
RE_REMOTE_ASSET = re.compile(r"<(?:script|link)\b[^>]*\b(?:src|href)=[\"']https?://", re.IGNORECASE)
# Inline code the Content Security Policy would block: <script> without src or nonce,
# any <style> block (style-src allows no nonce), style="..." attributes, on*="..." handlers
# and htmx's hx-on* handlers, which the htmx-config in base.html disables as well
RE_INLINE_CODE = re.compile(
    r"<script\b(?![^>]*\b(?:src|nonce)=)[^>]*>|<style\b|\sstyle=[\"']|\son[a-z]+=[\"']|\s(?:data-)?hx-on[^\s=]*=[\"']",
    re.IGNORECASE,
)

# Paths that must never be generated any more (Node.js / asset pipeline leftovers)
FRONTEND_TOOLCHAIN_PATHS = [
    "package.json",
    "package-lock.json",
    "gulpfile.mjs",
    "webpack",
    "compose/local/node",
    "my_test_project/static/sass",
    "my_test_project/static/js/vendors.js",
    "my_test_project/static/vendor",
]
# Case-insensitive tokens that must not appear in any generated text file
FRONTEND_TOOLCHAIN_TOKENS = [
    "bootstrap",
    "crispy",
    "compressor",
    "compress_",
    "webpack",
    "gulp",
    "node_modules",
    "docker.io/node",
    "npm ",
    "cdnjs",
    "sass",
]

# A value the post-generation hook drew: a run of letters and digits longer than any word.
# Masked before a scan for forbidden words, which a random run could otherwise spell, and by
# scripts/compare_generated.py before it compares two bakes.
RE_DRAWN_VALUE = re.compile(r"[A-Za-z0-9]{32,}")
# The frontends this template removed, as no generated file may spell them any more: their
# names, the component syntax, the filters, settings, attributes and custom properties, the
# class prefix (case-sensitive and not after a hyphen: "swagger-ui-bundle" and "daisyui-"
# pass), the routes and the files
REMOVED_FRONTEND_PATTERNS = [
    r"(?i:\bpico\b)",
    r"(?i:cotton)",
    r"</?c-[a-z]",
    r"\bc-(?:vars|slot)\b",
    r"\bui_(?:attrs?|url|label|theme)\b",
    r"\bUI_(?:PALETTE|MODE|BRAND)\b",
    r"\bdata-ui-",
    r"--ui-",
    r"(?<![\w-])ui-[a-z]",
    r"\bui[:/]theme\b",
    r"/ui/",
    r"(?i:\bshowcase)",
    r"\bproject\.(?:css|js)\b",
]
RE_REMOVED_FRONTEND = re.compile("|".join(REMOVED_FRONTEND_PATTERNS))
# "alert-{{ level }}": a class name assembled around an interpolation, which Tailwind never sees whole
RE_ASSEMBLED_CLASS = re.compile(r"""\bclass=(["'])(?:(?!\1).)*?(?:[\w-]\{\{|\}\}[\w-])""", re.DOTALL)

# The themes daisyUI 5 ships, in its own order: the generated picker offers every one of them
DAISYUI_THEMES = (
    "light",
    "dark",
    "cupcake",
    "bumblebee",
    "emerald",
    "corporate",
    "synthwave",
    "retro",
    "cyberpunk",
    "valentine",
    "halloween",
    "garden",
    "forest",
    "aqua",
    "lofi",
    "pastel",
    "fantasy",
    "wireframe",
    "black",
    "luxury",
    "dracula",
    "cmyk",
    "autumn",
    "business",
    "acid",
    "lemonade",
    "night",
    "coffee",
    "winter",
    "dim",
    "nord",
    "sunset",
    "caramellatte",
    "abyss",
    "silk",
)

# The daisyUI plugin block of the source stylesheet, with its options
RE_DAISYUI_PLUGIN = re.compile(r'@plugin\s+"daisyui"\s*\{(.*?)\}', re.DOTALL)

# The style checks that a formatter run after generation would fix: ruff format, djlint's
# formatter and django-upgrade. They take longer than the rest of the suite, so they run
# only with AUTOFIXABLE_STYLES=1; CI runs just them in its own job, selected by the marker.
# A defect they find is fixed in the template, so the generated project starts clean.
AUTOFIXABLE_STYLES = os.getenv("AUTOFIXABLE_STYLES") == "1"


def auto_fixable(test):
    """Mark ``test`` as an auto-fixable style check: skipped without the flag, selectable with ``-m``."""
    return pytest.mark.auto_fixable(pytest.mark.skipif(not AUTOFIXABLE_STYLES, reason="auto-fixable")(test))


# The free-text answers the hand-written tests bake with, and the same with the characters
# that end or escape a string. They are data, not only fixtures, because
# scripts/compare_generated.py bakes the hostile answers too.
FREE_TEXT_ANSWERS = {
    "project_name": "My Test Project",
    "project_slug": "my_test_project",
    "author_name": "Test Author",
    "email": "test@example.com",
    "description": "A short description of the project.",
    "domain_name": "example.com",
    "version": "0.1.0",
    "timezone": "UTC",
}
HOSTILE_ANSWERS = {
    **FREE_TEXT_ANSWERS,
    "project_name": 'My "Test" Project\\',
    "description": 'She said "hi" & <left> C:\\path, it\'s fine.',
    "author_name": 'Tess "Quoted" O\'Brien',
    "email": '"Tess O\'Brien"@example.com',
}


@pytest.fixture
def context():
    return dict(FREE_TEXT_ANSWERS)


@pytest.fixture
def hostile_context():
    """The context with free-text answers built from the characters that end or escape a string."""
    return dict(HOSTILE_ANSWERS)


@pytest.fixture(scope="session")
def bake(cookies_session):
    """Generate the project ``answers`` select, once per test process, and open it through the reader.

    The answers reach Cookiecutter verbatim: a test that wants the defaults merges ``context``
    in itself. Generation must succeed; a test expecting the hook to refuse bakes through
    ``cookies``.

    The complete answers, the catalogue's defaults filling in what ``answers`` leaves out,
    are baked once per test process and every later call gets the same tree, so a test must
    not modify it: a tool that rewrites files runs on a copy. Under xdist a process is a
    worker; the tests that share a combination's bake are grouped onto one worker
    (``GROUPED_COMBINATIONS``), the hand-written tests bake on whichever worker runs them.
    """
    projects: dict[tuple[tuple[str, str | bool], ...], GeneratedProject] = {}

    def bake(answers: dict[str, str]) -> GeneratedProject:
        key = tuple(sorted(complete_answers(answers).items()))
        if key not in projects:
            result = cookies_session.bake(extra_context=answers)
            assert result.exception is None
            assert result.exit_code == 0
            projects[key] = GeneratedProject(result.project_path)
        return projects[key]

    return bake


# The pre-generation hook rejects these pairs of answers.
UNSUPPORTED_COMBINATIONS = [
    {"cloud_provider": "None", "use_whitenoise": "n"},
    {"cloud_provider": "None", "mail_service": "Amazon SES"},
]

# Django Ninja with an identity provider: allauth's headless API signs the single-page
# application's tokens, and the identity app guards them and verifies calling services.
HEADLESS_COMBINATIONS = [
    {"identity_provider": "entra", "rest_api": "Django Ninja"},
    {"identity_provider": "google", "rest_api": "Django Ninja"},
]

# Answers that only show their effect together, baked on top of the derived rows below. A
# file that exists only for such answers demands its row by itself:
# ``test_every_removable_path_is_baked`` fails for a path the removal rules list and no row
# keeps, and names the row. A fork inside a file that some row keeps anyway is still a matter
# of remembering it, and these are the ones remembered: cloud_provider and use_whitenoise
# decide the storage backends between them (and None with WhiteNoise off is rejected, so no
# single-answer row can reach cloud_provider=None), Channels has its own wiring in the Docker
# and Celery files, a mail catcher's host is the Compose service with Docker, and an identity
# provider's headless login exists with Django Ninja only. mail_service shares no conditional
# with cloud_provider anywhere in the template, so the two need no cross product: Amazon SES
# bakes on the default cloud_provider=AWS, the only one it supports.
PAIRED_COMBINATIONS = [
    {"cloud_provider": "AWS", "use_whitenoise": "y"},
    {"cloud_provider": "None", "use_whitenoise": "y"},
    # nginx serves the media files, and Traefik's media router points at it, only here.
    {"cloud_provider": "None", "use_whitenoise": "y", "use_docker": "y"},
    {"realtime": "channels", "use_docker": "y"},
    {"realtime": "channels", "use_celery": "y", "use_docker": "y"},
    {"mail_catcher": "Mailpit", "use_docker": "y"},
    {"mail_catcher": "Mailtrap Local", "use_docker": "y"},
    *HEADLESS_COMBINATIONS,
    # The agent guide describes the tree that was generated, so every arm of it needs an
    # agent to write it for: between them these two reach all of them.
    {
        "coding_agent": "codex",
        "use_docker": "y",
        "use_celery": "y",
        "realtime": "channels",
        "rest_api": "Django Ninja",
        "identity_provider": "entra",
        "use_sentry": "y",
        "observability": "opentelemetry",
        "ci_tool": "Github",
    },
    {
        "coding_agent": "cursor",
        "rest_api": "DRF",
        "ci_tool": "Gitlab",
        "observability": "prometheus",
        "identity_provider": "entra",
    },
    # The development Prometheus receiver, compose/local/prometheus, and the service that
    # mounts it are generated only here: the receiver goes unless Prometheus is chosen, and
    # the whole compose directory goes without Docker.
    {"observability": "prometheus", "use_docker": "y"},
    # A provider and the metrics endpoint without Django Ninja: a scrape is then the only
    # caller presenting a token the provider issued, so the verifier is generated for it
    # alone, and Google's arm of the app has no check of its own to keep.
    {"identity_provider": "google", "observability": "prometheus"},
    {"identity_provider": "entra", "rest_api": "Django Ninja", "observability": "prometheus"},
]


def rejected(answers):
    """Would the pre-generation hook refuse ``answers`` once the defaults fill in the rest?"""
    complete = complete_answers(answers)
    return any(all(complete[name] == value for name, value in pair.items()) for pair in UNSUPPORTED_COMBINATIONS)


def supported_combinations():
    """The answers the generation tests bake: the defaults, one row per choice of every list
    and flag option in the catalogue, and the paired rows. A row that the hook would reject,
    or whose answers amount to an earlier row's, is left out, so each project bakes once."""
    per_choice = ({name: choice} for name, option in OPTIONS.items() for choice in option.choices)
    rows = [{}, *per_choice, *PAIRED_COMBINATIONS]
    seen = set()
    unique = []
    for row in rows:
        complete = tuple(sorted(complete_answers(row).items()))
        if rejected(row) or complete in seen:
            continue
        seen.add(complete)
        unique.append(row)
    return unique


SUPPORTED_COMBINATIONS = supported_combinations()

# The yes/no answers: typed as text, so the pre-generation hook validates them.
FLAG_OPTIONS = option_names(FLAG)


def _fixture_id(ctx):
    """Helper to get a user-friendly test name from the parametrized context."""
    return "-".join(f"{key}:{value}" for key, value in ctx.items()) or "defaults"


def _fixture_id_of_first(value):
    """Name a parametrized case after its context override, and nothing after the other arguments."""
    return _fixture_id(value) if isinstance(value, dict) else ""


# The supported combinations as parameters named after their answers, for the tests that bake
# a combination's plain answers and so share its bake: they carry its name as their xdist
# group, and loadgroup scheduling (``addopts`` in pyproject.toml) runs a group on one worker.
GROUPED_COMBINATIONS = [
    pytest.param(row, id=_fixture_id(row), marks=pytest.mark.xdist_group(_fixture_id(row)))
    for row in SUPPORTED_COMBINATIONS
]


# The combinations that write an agent guide: the others answered ``coding_agent`` with
# ``none``, and the tests of the guide's contents have nothing to read.
GUIDE_COMBINATIONS = [
    param
    for param, row in zip(GROUPED_COMBINATIONS, SUPPORTED_COMBINATIONS, strict=True)
    if complete_answers(row)["coding_agent"] != "none"
]


def check_po(content: str):
    """gettext strings take C's backslash escapes, which Python's literals share."""
    for line in content.splitlines():
        if line.startswith('"'):
            ast.literal_eval(line)


# How to parse each kind of generated file that has a syntax; failures are SyntaxError or ValueError.
PARSERS = {
    ".json": json.loads,
    ".po": check_po,
    ".py": ast.parse,
    ".toml": tomllib.loads,
    ".yaml": lambda content: list(yaml.safe_load_all(content)),
    ".yml": lambda content: list(yaml.safe_load_all(content)),
}


def check_files(project: GeneratedProject):
    """Every text file is fully rendered and, if it has a syntax, parses."""
    for path in project.files():
        if is_binary(str(project.root / path)):
            continue

        content = project.text(path)
        match = RE_OBJ.search(content)
        assert match is None, f"cookiecutter variable not replaced in {path}"
        assert RE_PLACEHOLDER.search(content) is None, f"secret not filled in {path}"
        parse = PARSERS.get(path.suffix)
        if parse is not None:
            try:
                parse(content)
            except (SyntaxError, ValueError, yaml.YAMLError) as e:
                pytest.fail(f"{path} does not parse: {e}")


def test_every_choice_is_baked():
    """A choice no supported combination selects would leave its template arms unrendered."""
    unbaked = [
        (name, choice)
        for name, option in OPTIONS.items()
        for choice in option.choices
        if not any(complete_answers(row)[name] == choice for row in SUPPORTED_COMBINATIONS)
    ]
    assert unbaked == []


def test_every_removable_path_is_baked():
    """A path the removal rules list and no supported combination keeps is one that no check
    running over the matrix has ever read. The rules know which answers only show their effect
    together, so a new rule demands its row here, and the failure says which row.

    File-level: whether every conditional inside a kept file is rendered is not checked (docs/adr/0021).
    """
    rows = [complete_answers(row) for row in SUPPORTED_COMBINATIONS]
    unbaked, _ = coverage_gaps(paths_kept(REMOVALS, rows), exemptions={})

    choices = {name: OPTIONS[name].choices for name in option_names(LIST, FLAG)}
    missing = {
        path: fewest_answers_keeping(
            path,
            REMOVALS,
            complete_answers,
            choices,
            supported=lambda answers: not rejected(answers),
        )
        for path in unbaked
    }
    unknown = f"none of up to {MOST_CHANGED_ANSWERS} answers, so read the rules that list it"
    assert not missing, "no supported combination keeps these paths; the row that would keep each:\n" + "\n".join(
        f"  {path}: {row if row is not None else unknown}" for path, row in missing.items()
    )


def test_combinations_name_options_of_the_catalogue():
    """A misspelt option or choice in a hand-written row would bake the default project and pass."""
    for row in [*PAIRED_COMBINATIONS, *UNSUPPORTED_COMBINATIONS]:
        assert unknown_answers(row) == [], row


@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_project_generation(bake, hostile_context, context_override):
    """The project is generated, fully rendered and parseable, whatever the free-text answers.

    The hostile answers are this test's alone, so its cases join no group.
    """
    project = bake({**hostile_context, **context_override})
    assert project.package == hostile_context["project_slug"]
    assert project.root.is_dir()

    assert project.files()
    check_files(project)


# The project template, which says of a path the removal rules list whether it is a directory.
TEMPLATE = Path(__file__).resolve().parent.parent / "{{cookiecutter.project_slug}}"

# Citations of a removed path that send nobody anywhere, each with its reason. File and path
# are written as the removal rules write paths, ``{project_slug}`` standing for the package.
# Whether an allowance is still needed is not enforced, because every combination is a test of
# its own under the bake's grouping (docs/adr/0002); ``citations`` reports the unused ones.
ALLOWED_CITATIONS = [
    Allowance(".dockerignore", ".gitlab-ci.yml", "an ignore file lists what stays out of an image, there or not"),
]


def as_generated(path: str, package: str) -> str:
    """A path written as the removal rules write them, as a generated project spells it: the
    package by its name, and a directory, which the template tree tells from a file, with its slash."""
    is_directory = (TEMPLATE / path.format(project_slug="{{cookiecutter.project_slug}}")).is_dir()
    return path.format(project_slug=package) + ("/" if is_directory else "")


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_no_file_cites_a_path_its_answers_removed(bake, context_override):
    """No file of a generated project sends its reader to a path the project's own answers
    deleted: the removal rules say which those are, for every combination (docs/adr/0021).
    A citation found here is forked on the answers in the template, or, if it is a listing
    that sends nobody anywhere, allowed above with its reason.
    """
    project = bake(context_override)
    files = {str(path): project.text(path) for path in project.files() if not is_binary(str(project.root / path))}
    answers = complete_answers(context_override)
    removed = [as_generated(path, project.package) for path in removed_paths(REMOVALS, answers)]
    allowed = [
        replace(
            allowance,
            file=as_generated(allowance.file, project.package),
            path=as_generated(allowance.path, project.package),
        )
        for allowance in ALLOWED_CITATIONS
    ]

    cited, _ = citations(files, removed, allowed, package=project.package)

    assert not cited, "\n".join(f"{citation.file} cites {citation.path}" for citation in cited)


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_ruff_check_passes(bake, context_override):
    """Generated project should pass ruff check."""
    project = bake(context_override)

    # No cache: ruff would write it into the shared tree.
    try:
        sh.ruff("check", "--no-cache", ".", _cwd=str(project.root))
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_ruff_format_passes(bake, context_override):
    """The generated project is formatted as ruff format would leave it."""
    project = bake(context_override)

    try:
        sh.ruff("format", "--check", "--no-cache", ".", _cwd=str(project.root))
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_django_upgrade_passes(bake, tmp_path, context_override):
    """django-upgrade, for the Django the project pins, would rewrite nothing in it."""
    project = bake(context_override)
    # django-upgrade rewrites in place, so it runs on a copy of the shared tree.
    copy = tmp_path / project.root.name
    shutil.copytree(project.root, copy)

    python_files = [str(path) for path in project.files() if path.suffix == ".py"]
    try:
        sh.django_upgrade(
            "--target-version",
            "6.0",
            *python_files,
            _cwd=str(copy),
        )
    except sh.ErrorReturnCode as e:
        # django-upgrade names the files it rewrote on stderr.
        pytest.fail(e.stdout.decode() + e.stderr.decode())


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_djlint_lint_passes(bake, context_override):
    """Check whether generated project passes djLint --lint."""
    project = bake(context_override)

    autofixable_rules = "H014,T001"
    # The generated [tool.djlint] ignores, which --ignore replaces
    # TODO: remove T002 when fixed https://github.com/Riverside-Healthcare/djLint/issues/687
    ignored_rules = "H006,H030,H031,T002"
    try:
        sh.djlint(
            "--lint",
            "--ignore",
            f"{autofixable_rules},{ignored_rules}",
            ".",
            _cwd=str(project.root),
        )
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_djlint_check_passes(bake, context_override):
    """Check whether generated project passes djLint --check."""
    project = bake(context_override)

    try:
        sh.djlint("--check", ".", _cwd=str(project.root))
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


# (use_docker, type-check command, test command) as the generated CI configs must invoke them.
CI_SCRIPT_CASES = [
    ("n", "uv run mypy .", "uv run pytest"),
    (
        "y",
        "docker compose -f docker-compose.local.yml run --rm django mypy .",
        "docker compose -f docker-compose.local.yml run django pytest",
    ),
]


@pytest.mark.parametrize(
    ("use_docker", "expected_typecheck_script", "expected_test_script"),
    CI_SCRIPT_CASES,
)
def test_gitlab_invokes_precommit_mypy_and_pytest(
    bake,
    context,
    use_docker,
    expected_typecheck_script,
    expected_test_script,
):
    context.update({"ci_tool": "Gitlab", "use_docker": use_docker})
    project = bake(context)

    assert project.package == context["project_slug"]
    assert project.root.is_dir()

    gitlab_config = project.yaml(".gitlab-ci.yml")
    assert gitlab_config["precommit"]["script"] == [
        "uv run pre-commit run --show-diff-on-failure --color=always --all-files",
    ]
    assert gitlab_config["pytest"]["script"] == [
        expected_typecheck_script,
        expected_test_script,
    ]


@pytest.mark.parametrize(
    ("use_docker", "expected_typecheck_script", "expected_test_script"),
    CI_SCRIPT_CASES,
)
def test_github_invokes_linter_mypy_and_pytest(
    bake,
    context,
    use_docker,
    expected_typecheck_script,
    expected_test_script,
):
    context.update({"ci_tool": "Github", "use_docker": use_docker})
    project = bake(context)

    assert project.package == context["project_slug"]
    assert project.root.is_dir()

    github_config = project.yaml(".github/workflows/ci.yml")
    linter_present = False
    for action_step in github_config["jobs"]["linter"]["steps"]:
        if action_step.get("uses", "NA").startswith("pre-commit"):
            linter_present = True
    assert linter_present

    typecheck_steps = [step.get("run") for step in github_config["jobs"]["typecheck"]["steps"]]
    assert expected_typecheck_script in typecheck_steps

    pytest_steps = [step.get("run") for step in github_config["jobs"]["pytest"]["steps"]]
    assert expected_test_script in pytest_steps
    assert expected_typecheck_script not in pytest_steps


@pytest.mark.parametrize("slug", ["project slug", "Project_Slug"])
def test_invalid_slug(cookies, context, slug):
    """Invalid slug should fail pre-generation hook."""
    context.update({"project_slug": slug})

    result = cookies.bake(extra_context=context)

    assert result.exit_code != 0
    assert isinstance(result.exception, FailedHookException)


@pytest.mark.parametrize(
    "answer",
    [
        {"description": "Two\nlines"},
        {"author_name": "Tab\tstop"},
        {"domain_name": "example.com/app"},
        {"domain_name": "my site.com"},
        {"domain_name": "`example.com`"},
    ],
    ids=_fixture_id,
)
def test_invalid_free_text(cookies, context, answer):
    """A control character, or a domain name with punctuation, fails the pre-generation hook."""
    context.update(answer)

    result = cookies.bake(extra_context=context)

    assert result.exit_code != 0
    assert isinstance(result.exception, FailedHookException)


@pytest.mark.parametrize("option", FLAG_OPTIONS)
def test_invalid_flag_answer(cookies, context, capfd, option):
    """A yes/no answer that is neither fails the pre-generation hook, which names the option and its answers."""
    context.update({option: "yes"})

    result = cookies.bake(extra_context=context)

    assert result.exit_code != 0
    assert isinstance(result.exception, FailedHookException)
    assert f"{option} must be answered with y or n, not 'yes'" in capfd.readouterr().err


@pytest.mark.parametrize("invalid_context", UNSUPPORTED_COMBINATIONS)
def test_error_if_incompatible(cookies, context, invalid_context):
    """It should not generate project an incompatible combination is selected."""
    context.update(invalid_context)
    result = cookies.bake(extra_context=context)

    assert result.exit_code != 0
    assert isinstance(result.exception, FailedHookException)


def test_trim_domain_email(bake, context):
    """Check that leading and trailing spaces are trimmed in domain and email."""
    context.update(
        {
            "use_docker": "y",
            "domain_name": "   example.com   ",
            "email": "  me@example.com  ",
        },
    )
    project = bake(context)

    assert project.env("production", "django")["DJANGO_ALLOWED_HOSTS"] == ".example.com"
    assert "<me@example.com>" in project.settings("base").source


# The deployed environments, in the order a change is promoted through them. Each has its own
# env files, Compose file and Traefik routers, and all three run config/settings/production.py.
DEPLOYED_ENVIRONMENTS = ("dev", "test", "production")

# The generated files that hold a secret drawn on each bake, so two bakes never agree on them;
# scripts/compare_generated.py masks the drawn values in these files and in no other.
SECRET_FILES = {
    ".envs/.local/.django",
    ".envs/.local/.postgres",
    ".envs/.dev/.django",
    ".envs/.dev/.postgres",
    ".envs/.test/.django",
    ".envs/.test/.postgres",
    ".envs/.production/.django",
    ".envs/.production/.postgres",
    "config/settings/local.py",
    "config/settings/test.py",
}


def project_contents(project: GeneratedProject) -> dict[str, bytes]:
    """Every generated file by its path relative to the project root, with its content."""
    return {str(path): project.bytes(path) for path in project.files()}


def env_read(module: PythonModule, name: str) -> EnvRead:
    """The one read of ``name`` through ``env`` in ``module``."""
    reads = [read for read in module.env_reads() if read.name == name]
    assert len(reads) == 1, f"{module.path} reads {name} {len(reads)} times, not once"
    return reads[0]


TOKEN = re.compile(r"[A-Za-z0-9]{64}")
ROLE = re.compile(r"[A-Za-z]{32}")
# The roles the environments share; every other secret is drawn per file.
SHARED_ROLES = ("POSTGRES_USER", "CELERY_FLOWER_USER")


def test_secrets_are_drawn_once_each(bake, context):
    """The database and Flower roles are the same in both environments; every other secret is its own."""
    project = bake({**context, "use_celery": "y"})
    local_django = project.env("local", "django")
    local_postgres = project.env("local", "postgres")
    production_django = project.env("production", "django")
    production_postgres = project.env("production", "postgres")

    roles = {local_postgres["POSTGRES_USER"], local_django["CELERY_FLOWER_USER"]}
    assert local_postgres["POSTGRES_USER"] == production_postgres["POSTGRES_USER"]
    assert local_django["CELERY_FLOWER_USER"] == production_django["CELERY_FLOWER_USER"]
    assert len(roles) == len(SHARED_ROLES)
    assert all(ROLE.fullmatch(role) for role in roles)

    tokens = [
        local_postgres["POSTGRES_PASSWORD"],
        production_postgres["POSTGRES_PASSWORD"],
        local_django["CELERY_FLOWER_PASSWORD"],
        production_django["CELERY_FLOWER_PASSWORD"],
        production_django["DJANGO_SECRET_KEY"],
        env_read(project.settings("local"), "DJANGO_SECRET_KEY").default,
        env_read(project.settings("test"), "DJANGO_SECRET_KEY").default,
    ]
    assert len(set(tokens)) == len(tokens)
    assert all(TOKEN.fullmatch(token) for token in tokens)
    assert re.fullmatch(r"[A-Za-z0-9]{32}/", production_django["DJANGO_ADMIN_URL"])


def test_debug_answer_fixes_the_credentials(bake, context):
    """With debug, the credentials read ``debug`` while the keys and the admin URL stay random."""
    project = bake({**context, "use_celery": "y", "debug": "y"})
    for environment in ("local", "production"):
        django = project.env(environment, "django")
        postgres = project.env(environment, "postgres")
        assert postgres["POSTGRES_USER"] == postgres["POSTGRES_PASSWORD"] == "debug"
        assert django["CELERY_FLOWER_USER"] == django["CELERY_FLOWER_PASSWORD"] == "debug"
    production_django = project.env("production", "django")
    assert TOKEN.fullmatch(production_django["DJANGO_SECRET_KEY"])
    assert re.fullmatch(r"[A-Za-z0-9]{32}/", production_django["DJANGO_ADMIN_URL"])


@pytest.mark.parametrize("answer", ["y", "n"])
def test_uppercase_flag_answers_select_the_same_features(bake, context, answer):
    """Every yes/no answer typed in uppercase generates the project its lowercase spelling does.

    The answers are lowercased before rendering, so every reader sees one spelling: the
    templates (dependencies, settings), the post-generation hook (secrets, ``.gitignore``)
    and pruning. Each is checked on the uppercase project so that the comparison cannot
    pass on two projects that ignored the answers alike.
    """
    answers = dict.fromkeys(FLAG_OPTIONS, answer)
    lowercase = bake({**context, **answers})
    uppercase = bake({**context, **dict.fromkeys(FLAG_OPTIONS, answer.upper())})

    expected = project_contents(lowercase)
    generated = project_contents(uppercase)
    assert generated.keys() == expected.keys()
    differing = {path for path in expected if generated[path] != expected[path]}
    assert differing <= SECRET_FILES

    selected = answer == "y"
    assert ({"celery", "sentry-sdk", "whitenoise"} <= pinned(uppercase)) is selected
    assert ("SENTRY_DSN" in uppercase.settings("production").source) is selected
    assert (uppercase.root / "docker-compose.local.yml").exists() is selected
    # The env files are generated for every project, and none of them is ever committed.
    assert (uppercase.root / ".envs").is_dir()
    assert ".envs/*" in uppercase.text(".gitignore")
    if selected:
        assert uppercase.env("local", "postgres")["POSTGRES_USER"] == "debug"


def test_pyproject_toml(bake, context):
    # Free-text answers with the characters that end or escape a TOML string.
    author_name = 'Project "Quoted" Author'
    author_email = "me@example.com"
    description = 'She said "hi" & <left> C:\\path, it\'s fine.'
    context.update(
        {
            "description": description,
            "domain_name": "example.com",
            "email": author_email,
            "author_name": author_name,
        },
    )
    project = bake(context)

    data = project.pyproject

    assert data
    assert data["project"]["authors"][0]["email"] == author_email
    assert data["project"]["authors"][0]["name"] == author_name
    assert data["project"]["description"] == description
    assert data["project"]["version"] == context["version"]
    assert data["project"]["name"] == context["project_slug"]
    assert data["project"]["requires-python"] == ">=3.12"
    assert "Programming Language :: Python :: 3.12" in data["project"]["classifiers"]
    assert "Programming Language :: Python :: 3.14" in data["project"]["classifiers"]
    assert data["tool"]["mypy"]["python_version"] == "3.12"


def pinned(project: GeneratedProject) -> set[str]:
    """The distribution names the generated ``pyproject.toml`` pins, across its arrays."""
    return {pin.name for array in project.pins.values() for pin in array}


PROMETHEUS_PACKAGES = {"django-prometheus", "prometheus-client"}
TELEMETRY_PACKAGES = {
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp-proto-http",
    "opentelemetry-instrumentation-django",
    "opentelemetry-instrumentation-psycopg",
    "opentelemetry-instrumentation-redis",
}

# (answers, packages the generated project must pin, packages it must not)
DEPENDENCY_CASES = [
    ({"use_celery": "y"}, {"celery", "django-celery-beat", "celery-types", "watchfiles"}, {"flower"}),
    ({"use_celery": "y", "use_docker": "y"}, {"flower"}, set()),
    ({"use_celery": "n"}, set(), {"celery", "django-celery-beat", "celery-types", "watchfiles", "flower"}),
    ({"realtime": "channels"}, {"channels", "channels-redis", "types-channels"}, set()),
    ({"realtime": "none"}, set(), {"channels", "channels-redis", "types-channels"}),
    (
        {"rest_api": "DRF"},
        {"djangorestframework", "djangorestframework-stubs", "drf-spectacular", "django-cors-headers"},
        {"django-ninja"},
    ),
    (
        {"rest_api": "Django Ninja"},
        {"django-ninja", "django-cors-headers"},
        {"djangorestframework", "djangorestframework-stubs", "drf-spectacular"},
    ),
    ({"rest_api": "None"}, set(), {"django-cors-headers", "djangorestframework", "django-ninja"}),
    ({"use_sentry": "y"}, {"sentry-sdk"}, set()),
    ({"use_sentry": "n"}, set(), {"sentry-sdk"}),
    ({"observability": "prometheus"}, PROMETHEUS_PACKAGES, TELEMETRY_PACKAGES),
    # The instrumentations are the libraries the project talks to, and only those
    (
        {"observability": "opentelemetry"},
        TELEMETRY_PACKAGES,
        PROMETHEUS_PACKAGES | {"opentelemetry-instrumentation-celery"},
    ),
    ({"observability": "opentelemetry", "use_celery": "y"}, {"opentelemetry-instrumentation-celery"}, set()),
    ({"observability": "none"}, set(), PROMETHEUS_PACKAGES | TELEMETRY_PACKAGES),
    ({"use_whitenoise": "y"}, {"whitenoise"}, {"collectfasta"}),
    ({"cloud_provider": "AWS", "use_whitenoise": "n"}, {"django-storages", "collectfasta"}, {"whitenoise"}),
    ({"cloud_provider": "None", "use_whitenoise": "y"}, {"whitenoise"}, {"django-storages", "collectfasta"}),
    ({"mail_service": "Other SMTP"}, {"django-anymail"}, set()),
    ({"identity_provider": "none"}, {"django-allauth"}, set()),
    # PyJWT verifies the tokens of calling services, wherever something reads one
    ({"identity_provider": "entra", "observability": "prometheus"}, {"pyjwt"}, set()),
    ({"identity_provider": "entra", "rest_api": "Django Ninja"}, {"pyjwt"}, set()),
    ({"identity_provider": "entra"}, set(), {"pyjwt"}),
]


@pytest.mark.parametrize(("context_override", "expected", "unexpected"), DEPENDENCY_CASES, ids=_fixture_id_of_first)
def test_pyproject_pins_the_dependencies_of_the_chosen_options(bake, context_override, expected, unexpected):
    """The dependencies an option needs are pinned in pyproject.toml, and only then."""
    project = bake(context_override)

    names = pinned(project)
    assert expected <= names
    assert not unexpected & names


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_pyproject_dependencies_are_pinned_and_sorted(bake, context_override):
    """Every dependency is pinned to one version, and the arrays are in the order pyproject-fmt keeps."""
    project = bake(context_override)

    arrays = project.pins
    assert set(arrays) == {"dependencies", "dev"}
    for name, requirements in arrays.items():
        unpinned = [str(pin) for pin in requirements if [spec.operator for spec in pin.specifier] != ["=="]]
        assert not unpinned, f"{name} does not pin {unpinned}"
        expected = sorted(requirements, key=lambda pin: (pin.name, str(pin)))
        assert requirements == expected, f"{name} is not sorted"


def test_generation_writes_no_lock_file(bake, context):
    """Generation resolves nothing: the developer's first ``uv sync`` writes the lock file."""
    project = bake({**context, "use_docker": "y"})

    assert not (project.root / "uv.lock").exists()
    assert not (project.root / ".venv").exists()
    assert not (project.root / "requirements").exists()
    assert not (project.root / "compose" / "local" / "uv").exists()


def test_free_text_answers_survive_escaping(bake, hostile_context):
    """Each free-text answer reads back unchanged from the generated file it was escaped into."""
    hostile_context.update(
        {
            "use_docker": "y",  # generates the Traefik configuration
            "rest_api": "DRF",  # generates SPECTACULAR_SETTINGS
            "timezone": 'Zone/"Quoted"',  # nothing here starts Django, which would reject it
        },
    )
    project = bake(hostile_context)
    project_name = hostile_context["project_name"]
    author_name = hostile_context["author_name"]
    email = hostile_context["email"]

    settings = project.settings("base")
    assert settings.literal("TIME_ZONE") == hostile_context["timezone"]
    assert settings.literal("ADMINS") == [f'"{author_name}" <{email}>']
    assert settings.literal("SPECTACULAR_SETTINGS")["TITLE"] == f"{project_name} API"

    sphinx = project.module("docs/conf.py")
    assert sphinx.literal("project") == project_name
    assert sphinx.literal("author") == author_name
    assert sphinx.literal("copyright").endswith(f", {author_name}")

    package = project.module(f"{hostile_context['project_slug']}/__init__.py")
    assert package.literal("__version__") == hostile_context["version"]

    traefik = project.yaml("compose/production/traefik/traefik.yml")
    assert traefik["certificatesResolvers"]["letsencrypt"]["acme"]["email"] == email

    base_html = project.template("base.html")
    assert "My &#34;Test&#34; Project\\" in base_html
    assert 'content="She said &#34;hi&#34; &amp; &lt;left&gt; C:\\path, it&#39;s fine."' in base_html
    assert 'content="Tess &#34;Quoted&#34; O&#39;Brien"' in base_html


@pytest.mark.parametrize("rest_api", ["None", "DRF", "Django Ninja"])
def test_strict_typing_setup(bake, context, rest_api):
    """The generated project is type checked in strict mode with the right plugins and request types."""
    context.update({"rest_api": rest_api})
    project = bake(context)

    pyproject = project.pyproject
    assert pyproject["tool"]["mypy"]["strict"] is True
    assert "mypy_django_plugin.main" in pyproject["tool"]["mypy"]["plugins"]
    assert ("mypy_drf_plugin.main" in pyproject["tool"]["mypy"]["plugins"]) is (rest_api == "DRF")
    type_checking = pyproject["tool"]["ruff"]["lint"].get("flake8-type-checking", {})
    assert ("runtime-evaluated-decorators" in type_checking) is (rest_api == "Django Ninja")

    typedefs = project.text(f"{context['project_slug']}/typedefs.py")
    assert "class AuthenticatedHttpRequest(HttpRequest):" in typedefs
    assert "class AuthenticatedHtmxRequest(" in typedefs
    assert ("class AuthenticatedApiRequest(Request):" in typedefs) is (rest_api == "DRF")


@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_asgi_entrypoint(bake, context, realtime):
    """Every project is served through ASGI; the Channels wiring is only generated on request."""
    context.update({"realtime": realtime})
    project = bake(context)

    config = project.root / "config"
    assert (config / "asgi.py").exists()
    assert not (config / "wsgi.py").exists()
    base = project.settings("base")
    assert 'ASGI_APPLICATION = "config.asgi.application"' in base.source
    assert "WSGI_APPLICATION" not in base.source

    uses_channels = realtime == "channels"
    assert (config / "websocket.py").exists() is uses_channels
    websocket_test = project.root / context["project_slug"] / "tests" / "test_websocket.py"
    assert websocket_test.exists() is uses_channels
    assert ("channels" in base.literal("INSTALLED_APPS")) is uses_channels
    assert "CHANNEL_LAYERS" not in base.source
    assert ("InMemoryChannelLayer" in project.settings("local").source) is uses_channels
    assert ("InMemoryChannelLayer" in project.settings("test").source) is uses_channels
    assert ("channels_redis.core.RedisChannelLayer" in project.settings("production").source) is uses_channels
    assert [pin.extras for pin in project.pins["dependencies"] if pin.name == "uvicorn"] == [{"standard"}]
    names = pinned(project)
    assert "uvicorn-worker" in names
    assert ("channels-redis" in names) is uses_channels
    assert ("types-channels" in names) is uses_channels
    base_html = project.template("base.html")
    assert ('{% htmx_script extensions="hx-ws" %}' in base_html) is uses_channels
    assert ("{% htmx_script %}" in base_html) is not uses_channels


@pytest.mark.parametrize("use_docker", ["y", "n"])
def test_docker_compose_files_match_use_docker(bake, context, use_docker):
    """All docker-compose files, including the docs one, are only generated with use_docker=y."""
    context.update({"use_docker": use_docker})
    project = bake(context)

    compose_files = [
        "docker-compose.local.yml",
        *(f"docker-compose.{environment}.yml" for environment in DEPLOYED_ENVIRONMENTS),
        "docker-compose.docs.yml",
    ]
    for compose_file in compose_files:
        assert (project.root / compose_file).exists() is (use_docker == "y")


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_deployed_environments_declare_the_same_variables(bake, context_override):
    """The deployed environments run one settings module, so their env files agree on what
    they declare and differ only in the values: their own hosts, secrets, and the name each
    reports as. The env files are generated whatever the answers (docs/adr/0014).
    """
    project = bake(context_override)

    for service in ("django", "postgres"):
        declared = {environment: set(project.env(environment, service)) for environment in DEPLOYED_ENVIRONMENTS}
        assert len(set(map(frozenset, declared.values()))) == 1, declared

    for environment in DEPLOYED_ENVIRONMENTS:
        django = project.env(environment, "django")
        assert django["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
        # Sentry and the collector are told which deployment reported, so each names itself.
        for variable in ("SENTRY_ENVIRONMENT", "OTEL_DEPLOYMENT_ENVIRONMENT"):
            if variable in django:
                assert django[variable] == environment, variable

    hosts = {project.env(environment, "django")["DJANGO_ALLOWED_HOSTS"] for environment in DEPLOYED_ENVIRONMENTS}
    assert len(hosts) == len(DEPLOYED_ENVIRONMENTS), hosts


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_the_shared_source_leaves_no_trace_in_a_generated_project(bake, context_override):
    """A deployed environment's files are rendered from a shared source outside the project
    template (docs/adr/0023): the source directory is never generated, and nothing that
    includes it is left unrendered."""
    project = bake(context_override)

    assert not (project.root / "templates").exists()
    for environment in DEPLOYED_ENVIRONMENTS:
        for service in ("django", "postgres"):
            text = project.text(f".envs/.{environment}/.{service}")
            assert "{%" not in text, f"{environment}/{service} was not rendered"


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_the_example_dotenv_declares_the_deployment_variables(bake, context_override):
    """No env file is committed, so ``.env.example`` is what a checkout -- the project's own
    CI included -- reads the deployment's variables from. It is the production env files
    merged, so it declares exactly what they do, with every drawn value left for the
    deployment to set and every other value as it stands.
    """
    project = bake(context_override)

    example = project.dotenv(".env.example")
    declared = {**project.env("production", "django"), **project.env("production", "postgres")}
    assert set(example) == set(declared)
    for name, value in example.items():
        # Either the deployment's to set, or the value the env file carries; never a
        # drawn secret, and never something the example invented.
        assert value in ("", declared[name]), f"{name}={value}"
    assert TOKEN.search(project.text(".env.example")) is None
    # The generated test fills an unset value with a stand-in named after it, so the keys
    # it loads stay distinct; a shared placeholder would make them equal.
    assert {name for name, value in example.items() if not value} >= {"DJANGO_SECRET_KEY"}


@pytest.mark.xdist_group("deployed-environments")
@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_deployed_compose_file_wires_its_own_environment(bake, context, environment):
    """Each deployed environment reads its own env files, keeps its own volumes and builds
    Traefik with its own routers, from the one set of production images.
    """
    context.update({"use_docker": "y"})
    project = bake(context)

    compose = project.compose(environment)
    for name, service in compose["services"].items():
        for entry in service.get("env_file", []):
            assert entry.startswith(f"./.envs/.{environment}/"), f"{name} reads {entry}"
        build = service.get("build")
        if build is None:  # an upstream image, tagged and pulled as it comes
            continue
        # The images are production's, and the tagged ones name the environment that built them.
        assert build["dockerfile"].startswith("./compose/production/"), f"{name} builds {build['dockerfile']}"
        if "image" in service:
            assert f"_{environment}_" in service["image"], f"{name} is {service['image']}"
    assert all(name.startswith(f"{environment}_") for name in compose["volumes"]), compose["volumes"]
    assert compose["services"]["traefik"]["build"]["args"] == {"ENVIRONMENT": environment}


def test_traefik_routers_name_the_shared_services(bake, context):
    """Traefik's configuration is split: the static file, the shared services and middlewares,
    and one router file per environment, which the image is built with. A router naming
    something the shared file does not declare would only fail once deployed, so the answers
    that render every router are baked and the three environments checked against it.
    """
    context.update(
        {"use_docker": "y", "use_celery": "y", "cloud_provider": "None", "use_whitenoise": "y"},
    )
    project = bake(context)

    traefik = Path("compose") / "production" / "traefik"
    static = project.yaml(traefik / "traefik.yml")
    # The routers live in the directory, so the static file no longer points back at itself.
    assert static["providers"]["file"] == {"directory": "/etc/traefik/dynamic", "watch": True}
    shared = project.yaml(traefik / "dynamic" / "shared.yml")["http"]
    assert set(shared) == {"middlewares", "services"}

    for environment in DEPLOYED_ENVIRONMENTS:
        routers = project.yaml(traefik / "dynamic" / f"{environment}.yml")["http"]["routers"]
        assert set(routers) == {"web-secure-router", "flower-secure-router", "web-media-router"}
        for name, router in routers.items():
            assert router["service"] in shared["services"], f"{environment}: {name} names no service"
            for middleware in router.get("middlewares", []):
                assert middleware in shared["middlewares"], f"{environment}: {name} names {middleware}"
            assert set(router["entryPoints"]) <= set(static["entryPoints"]), f"{environment}: {name}"
            # Every host the deployment answers for is its own, so one environment's
            # certificate is never requested by another.
            host = "" if environment == "production" else f"{environment}."
            assert f"Host(`{host}{context['domain_name']}`)" in router["rule"], router["rule"]


@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_docker_serves_asgi(bake, context, realtime):
    """The Docker start scripts run Uvicorn; local development needs no Redis for Channels."""
    context.update({"realtime": realtime, "use_docker": "y"})
    project = bake(context)

    local_start = project.text("compose/local/django/start")
    assert "exec uvicorn config.asgi:application" in local_start
    production_start = project.text("compose/production/django/start")
    assert "exec gunicorn config.asgi" in production_start
    assert "uvicorn_worker.UvicornWorker" in production_start

    compose = project.compose("local")
    assert "redis" not in compose["services"]
    assert "taskworker" not in compose["services"]


def test_frontend_stack(bake, context):
    """The generated project loads htmx through django-htmx and generates none of a Node.js toolchain's files."""
    project = bake(context)

    for path in FRONTEND_TOOLCHAIN_PATHS:
        assert not (project.root / path).exists(), f"{path} should not be generated"

    base = project.settings("base")
    assert "django_htmx" in base.literal("INSTALLED_APPS")
    assert "django_htmx.middleware.HtmxMiddleware" in base.literal("MIDDLEWARE")
    assert "django-htmx" in pinned(project)

    base_html = project.template("base.html")
    assert "{% htmx_script %}" in base_html
    assert 'hx-headers=\'{"X-CSRFToken": "{{ csrf_token }}"}\'' in base_html


def test_no_remote_assets(bake, context):
    """No stylesheet or script is loaded from a CDN or any other remote host."""
    project = bake(context)

    offenders = [
        path for path in project.files() if path.suffix == ".html" and RE_REMOTE_ASSET.search(project.text(path))
    ]
    assert offenders == []


def test_no_inline_code_in_templates(bake, context):
    """Templates contain no inline scripts, styles or event handlers, which the CSP would block."""
    project = bake(context)

    offenders = []
    for path in project.files():
        if path.suffix != ".html":
            continue
        match = RE_INLINE_CODE.search(project.text(path))
        if match:
            offenders.append(f"{path}: {match.group(0)}")
    assert offenders == []


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_no_trace_of_a_removed_frontend(bake, context_override):
    """No generated file, whatever the answers, names a frontend or a toolchain this template removed.

    Every combination is scanned: the default answers prune the agent guide, the Compose files
    and the CI configuration, which a scan of the default project would never read.
    """
    project = bake(context_override)

    offenders = [f"{path}: its path" for path in project.files() if RE_REMOVED_FRONTEND.search(f"/{path}")]
    for path in project.files():
        if is_binary(str(project.root / path)):
            continue
        content = RE_DRAWN_VALUE.sub("", project.text(path))
        offenders.extend(f"{path}: {token}" for token in FRONTEND_TOOLCHAIN_TOKENS if token in content.lower())
        offenders.extend(f"{path}: {match.group(0)}" for match in RE_REMOVED_FRONTEND.finditer(content))
    assert offenders == []


def test_class_names_are_written_whole(bake, context):
    """No class attribute glues an interpolation to part of a name: Tailwind generates a class only
    where it finds the whole name. It does not prove that every class used is in the built stylesheet."""
    project = bake(context)

    offenders = []
    for path in project.files():
        if path.suffix != ".html":
            continue
        offenders.extend(f"{path}: {match.group(0)}" for match in RE_ASSEMBLED_CLASS.finditer(project.text(path)))
    assert offenders == []


def test_template_partials(bake, context):
    """htmx fragments are Django template partials selected by HtmxTemplateMixin."""
    project = bake(context)

    templates = Path(context["project_slug"]) / "templates"
    assert not (project.root / templates / "users" / "partials").exists()
    assert not (project.root / templates / "partials" / "messages.html").exists()
    assert "{% partialdef messages inline %}" in project.template("base.html")
    for name in ("user_detail.html", "user_form.html"):
        template = project.template(f"users/{name}")
        assert "{% partialdef profile inline %}" in template
        assert '{% include "base.html#messages" %}' in template

    views = project.text(f"{context['project_slug']}/users/views.py")
    assert 'htmx_partial = "profile"' in views
    assert "htmx_template_name" not in views

    # Templates branch on the mixin's context flag, never on the request header: a template
    # that reads the request makes every page including it vary by HX-Request.
    offenders = [
        path
        for path in project.files()
        if path.is_relative_to(templates) and path.suffix == ".html" and "request.htmx" in project.text(path)
    ]
    assert offenders == []


def test_tailwind_and_daisyui(bake, context):
    """django-tailwind-cli builds the stylesheet from a source outside the static directories, and the
    built file is never generated. Nothing here runs the Tailwind CLI: the integration scripts do."""
    project = bake(context)
    slug = context["project_slug"]

    # A runtime dependency: the production image builds the stylesheet without the dev group
    assert "django-tailwind-cli" in {pin.name for pin in project.pins["dependencies"]}
    base = project.settings("base")
    assert "django_tailwind_cli" in base.literal("INSTALLED_APPS")
    assert base.literal("TAILWIND_CLI_USE_DAISY_UI") is True
    # A release of tailwind-cli-extra, never "latest": it fixes Tailwind CSS and daisyUI together
    assert re.fullmatch(r"\d+\.\d+\.\d+", base.literal("TAILWIND_CLI_VERSION"))
    # Outside the static directories: a manifest storage cannot resolve the source's @import "tailwindcss"
    assert base.literal("TAILWIND_CLI_SRC_CSS") == f"{slug}/styles/main.css"
    assert base.value("STATICFILES_DIRS") == [Expression("str(APPS_DIR / 'static')")]
    assert base.literal("TAILWIND_CLI_DIST_CSS") == "css/tailwind.css"
    # The production image builds under the test settings, so no other module may say otherwise
    for environment in ("local", "test", "production"):
        assert "TAILWIND_CLI" not in project.settings(environment).source

    # Explicit sources: the scan is the same with and without the .gitignore that Docker leaves out
    css = project.text(f"{slug}/styles/main.css")
    assert '@import "tailwindcss" source(none);' in css
    assert '@source "../";' in css
    assert RE_DAISYUI_PLUGIN.search(css)

    ignored = project.text(".gitignore").splitlines()
    assert f"{slug}/static/css/tailwind.css" in ignored
    assert ".django_tailwind_cli/" in ignored
    assert not (project.root / slug / "static" / "css" / "tailwind.css").exists()
    assert not (project.root / ".django_tailwind_cli").exists()

    # Django's own template loading again, and its form renderer on the project's overrides
    templates = base.value("TEMPLATES")[0]
    assert templates["APP_DIRS"] is True
    assert set(templates["OPTIONS"]) == {"context_processors"}
    assert base.literal("FORM_RENDERER") == "django.forms.renderers.TemplatesSetting"
    forms = project.root / slug / "templates" / "django" / "forms"
    for name in ("field.html", "errors/list/ul.html", "widgets/input.html", "widgets/attrs_without_class.html"):
        assert (forms / name).is_file()
    # Django's attrs.html stays Django's: the admin's widgets and third-party ones include it
    assert not (forms / "widgets" / "attrs.html").exists()

    # The built stylesheet is the only one a page loads, and the project ships no script of its own
    base_html = project.template("base.html")
    assert "{% tailwind_css %}" in base_html
    assert re.findall(r'<link\b[^>]*\brel="stylesheet"', base_html) == []
    assert "<script" not in base_html
    assert "inline_javascript" not in base_html
    assert not [path for path in project.files() if path.suffix == ".js"]
    # htmx injects no indicator rules under the policy, so the source stylesheet holds them
    assert ".htmx-indicator" in css
    # The project's own theme is the default look, and the style example a developer edits
    assert '@import "./theme.css";' in css
    theme = project.text(f"{slug}/styles/theme.css")
    assert '@plugin "daisyui/theme"' in theme
    assert 'name: "brand";' in theme
    assert theme.count("default: true;") == 1

    for name in ("test_staticfiles.py", "test_error_pages.py", "test_forms.py", "test_allauth.py", "test_pages.py"):
        assert (project.root / slug / "tests" / name).is_file()
    assert "   frontend\n" in project.text("docs/index.rst")


def test_the_page_reloads_itself_in_development(bake, context):
    """django-browser-reload is a development dependency, installed and routed under DEBUG alone, and
    the server command gives Uvicorn what a restart has to be visible through."""
    project = bake(context)

    assert "django-browser-reload" in {pin.name for pin in project.pins["dev"]}
    base = project.settings("base")
    local = project.settings("local")
    assert "django_browser_reload" not in base.literal("INSTALLED_APPS")
    assert 'INSTALLED_APPS += ["django_browser_reload"]' in local.source
    # After the policy's middleware, whose header has to carry the nonce of the written script
    middleware = local.source.index("django_browser_reload.middleware.BrowserReloadMiddleware")
    assert middleware > local.source.index('MIDDLEWARE += ["debug_toolbar')
    assert "csp" not in local.source[middleware:]

    debug_only = project.text("config/urls.py").partition("if settings.DEBUG:")[2]
    assert 'include("django_browser_reload.urls")' in debug_only

    # A rebuilt stylesheet has to restart the server, and the old process has to exit for the
    # page to notice: its own connection to it would otherwise never close. The command says
    # so in the two places a developer reads it, the container's and the guide's
    command = (
        "uvicorn config.asgi:application --host 0.0.0.0 --reload --reload-include '*.html'"
        " --reload-include '*.css' --timeout-graceful-shutdown 1"
    )
    assert command in bake({**context, "use_docker": "y"}).text("compose/local/django/start")
    assert command in bake({**context, "coding_agent": "claude"}).text("CLAUDE.md")


def test_themes(bake, context):
    """Every daisyUI theme is enabled next to the project's own, and the picker's choice is kept by a view
    that is always routed. That the stylesheet and ``THEMES`` agree is the generated suite's to check."""
    project = bake(context)
    slug = context["project_slug"]

    themes = project.module(f"{slug}/themes.py").literal("THEMES")
    own = re.search(r'name: "([^"]+)";', project.text(f"{slug}/styles/theme.css")).group(1)
    assert themes == (own, *DAISYUI_THEMES)
    # Listed one by one: "all" would make daisyUI's light the default, next to the project's own
    enabled = RE_DAISYUI_PLUGIN.search(project.text(f"{slug}/styles/main.css")).group(1)
    assert re.findall(r"^\s+([a-z]+)(?: --prefersdark)?[,;]$", enabled, re.MULTILINE) == list(DAISYUI_THEMES)
    assert "--default" not in enabled

    base = project.settings("base")
    assert base.value("TEMPLATES")[0]["OPTIONS"]["context_processors"][-1] == f"{slug}.themes.theme"
    routed = project.text("config/urls.py").partition("if settings.DEBUG:")[0]
    assert 'path("theme/", set_theme, name="set_theme")' in routed

    # The page is served in the chosen theme, and a checked theme-controller restyles it in CSS alone
    base_html = project.template("base.html")
    assert '{% if current_theme %}data-theme="{{ current_theme }}"{% endif %}' in base_html
    assert "hx-history-elt" in base_html
    navigation = project.template("partials/navigation.html")
    assert "theme-controller" in navigation
    assert "hx-post=\"{% url 'set_theme' %}\"" in navigation
    assert (project.root / slug / "tests" / "test_themes.py").is_file()


def test_examples_page(bake, context):
    """The examples page is routed in every environment, and a project that deletes it needs no other edit."""
    project = bake(context)
    slug = context["project_slug"]

    for name in ("__init__", "content", "forms", "urls", "views"):
        assert (project.root / slug / "examples" / f"{name}.py").is_file()
    # Not an installed app: it has no models, no template tags and no templates of its own
    assert f"{slug}.examples" not in project.settings("base").literal("INSTALLED_APPS")
    templates = project.root / slug / "templates" / "examples"
    names = sorted(path.stem for path in templates.iterdir())
    content = project.module(f"{slug}/examples/content.py")
    static = ["theme", "buttons", "alerts", "badges", "card"]
    assert names == sorted(["index", *static, *content.literal("HTMX_EXAMPLES")])

    # Outside the DEBUG block, unlike the error page previews
    routed, _, debug_only = project.text("config/urls.py").partition("if settings.DEBUG:")
    include = f'include("{slug}.examples.urls", namespace="examples")'
    assert include in routed
    assert include not in debug_only
    # The link asks for the route first, so deleting the page leaves the navigation working
    navigation = project.template("partials/navigation.html")
    assert "{% url 'examples:index' as examples_url %}" in navigation
    assert "{% if examples_url %}" in navigation
    # Where an htmx request puts a dialog
    assert '<div id="modal"></div>' in project.template("base.html")
    # The page keeps nothing on the server: its views open no transaction
    assert "transaction.non_atomic_requests" in project.text(f"{slug}/examples/views.py")


def test_docker_builds_and_watches_the_stylesheet(bake, context):
    """The production image builds the stylesheet in its build stage; only the local stack runs the watcher."""
    project = bake({**context, "use_docker": "y"})
    slug = context["project_slug"]

    build_stage, run_stage = project.text("compose/production/django/Dockerfile").split("AS python-run-stage")
    assert "manage.py tailwind build --skip-checks" in build_stage
    # The CLI lives in a build cache, so no layer and no image holds it
    assert "--mount=type=cache,target=/app/.django_tailwind_cli" in build_stage
    assert "tailwind" not in run_stage
    # A container collects what the image holds, and builds nothing
    start = project.text("compose/production/django/start")
    assert "collectstatic" in start
    assert "tailwind" not in start

    ignored = project.text(".dockerignore").splitlines()
    assert ".django_tailwind_cli/" in ignored
    assert f"{slug}/static/css/tailwind.css" in ignored

    services = project.compose("local")["services"]
    watcher = services["tailwind"]
    assert watcher["command"] == "python manage.py tailwind watch"
    # Tailwind's CLI stops watching once its standard input closes
    assert watcher["tty"] is True
    assert watcher["ports"] == []
    assert f"{slug}_local_tailwind_cli:/app/.django_tailwind_cli" in services["django"]["volumes"]
    for environment in DEPLOYED_ENVIRONMENTS:
        assert "tailwind" not in project.compose(environment)["services"]


@pytest.mark.parametrize("rest_api", ["None", "DRF", "Django Ninja"])
@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_content_security_policy(bake, context, realtime, rest_api):
    """Every project sends a nonce-based CSP; the websocket and API docs exceptions follow the options."""
    context.update({"realtime": realtime, "rest_api": rest_api})
    project = bake(context)

    base = project.settings("base")
    assert "django.middleware.csp.ContentSecurityPolicyMiddleware" in base.literal("MIDDLEWARE")
    context_processors = base.value("TEMPLATES")[0]["OPTIONS"]["context_processors"]
    assert "django.template.context_processors.csp" in context_processors
    assert "SECURE_CSP: dict[str, list[str]] = {" in base.source
    assert "UNSAFE_INLINE" not in base.source
    assert "UNSAFE_EVAL" not in base.source
    assert f"{context['project_slug']}.htmx.HtmxLoginRedirectMiddleware" in base.literal("MIDDLEWARE")
    assert ("ninja" in base.literal("INSTALLED_APPS")) is (rest_api == "Django Ninja")

    uses_channels = realtime == "channels"
    assert ('"ws:"' in project.settings("local").source) is uses_channels
    production = project.settings("production")
    assert ('"wss:"' in production.source) is uses_channels
    report_uri = env_read(production, "DJANGO_CSP_REPORT_URI")
    assert (report_uri.method, report_uri.default) == (None, None)
    # Documented in the env file as a commented-out line, so not a value ``env`` would read
    assert "DJANGO_CSP_REPORT_URI" in project.text(".envs/.production/.django")

    urls = project.text("config/urls.py")
    assert ("csp_override({})" in urls) is (rest_api == "DRF")

    base_html = project.template("base.html")
    assert '<meta name="htmx-config"' in base_html
    assert '"allowEval": false' in base_html
    assert '"includeIndicatorStyles": false' in base_html


@pytest.mark.parametrize("rest_api", ["None", "DRF", "Django Ninja"])
def test_cors_settings_follow_the_rest_api(bake, rest_api):
    """A project with a REST API answers cross-origin requests under its prefix; one without binds no CORS settings."""
    base = bake({"rest_api": rest_api}).settings("base")

    if rest_api == "None":
        assert "CORS" not in base.source
        assert "corsheaders" not in base.literal("INSTALLED_APPS")
    else:
        assert base.literal("CORS_URLS_REGEX") == r"^/api/.*$"
        assert "corsheaders" in base.literal("INSTALLED_APPS")
        assert "corsheaders.middleware.CorsMiddleware" in base.literal("MIDDLEWARE")


@pytest.mark.parametrize("use_celery", ["n", "y"])
def test_tasks_framework(bake, context, use_celery):
    """Django's Tasks framework is configured in every project; Celery stays an opt-in extra."""
    context.update({"use_celery": use_celery, "use_docker": "y"})
    project = bake(context)

    celery = use_celery == "y"
    assert "django-tasks-db" in pinned(project)
    assert "django_tasks_db" in project.settings("base").literal("INSTALLED_APPS")
    immediate = 'TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}'
    assert immediate in project.settings("local").source
    assert immediate in project.settings("test").source
    database = 'TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}'
    assert database in project.settings("production").source

    users = Path(context["project_slug"]) / "users"
    tasks = project.text(users / "tasks.py")
    assert "from django.tasks import task" in tasks
    assert ("shared_task" in tasks) is celery
    tests = project.text(users / "tests" / "test_tasks.py")
    assert "TaskResultStatus.SUCCESSFUL" in tests
    assert ("EagerResult" in tests) is celery
    assert (project.root / "config" / "celery_app.py").exists() is celery

    production_compose = project.compose("production")
    assert production_compose["services"]["taskworker"]["command"] == "/start-taskworker"
    assert ("celeryworker" in production_compose["services"]) is celery
    assert "taskworker" not in project.compose("local")["services"]
    django_compose = Path("compose") / "production" / "django"
    assert "db_worker" in project.text(django_compose / "tasks" / "worker" / "start")
    assert "/start-taskworker" in project.text(django_compose / "Dockerfile")


S3_STORAGE = "storages.backends.s3.S3Storage"
S3_MANIFEST_STORAGE = "storages.backends.s3.S3ManifestStaticStorage"
FILESYSTEM_STORAGE = "django.core.files.storage.FileSystemStorage"
WHITENOISE_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# The static files are hashed under either manifest storage, so a changed file is a new URL
HASHED_STORAGES = {S3_MANIFEST_STORAGE, WHITENOISE_STORAGE}
# (answers, the storage backend for uploads, the one for the static files)
STORAGE_CELLS = [
    ({"cloud_provider": "AWS", "use_whitenoise": "n"}, S3_STORAGE, S3_MANIFEST_STORAGE),
    ({"cloud_provider": "AWS", "use_whitenoise": "y"}, S3_STORAGE, WHITENOISE_STORAGE),
    ({"cloud_provider": "None", "use_whitenoise": "y"}, FILESYSTEM_STORAGE, WHITENOISE_STORAGE),
]


@pytest.mark.parametrize(("context_override", "media", "static"), STORAGE_CELLS, ids=_fixture_id_of_first)
def test_production_storages(bake, context_override, media, static):
    """The cloud provider decides where uploads go, WhiteNoise whether the app serves its own static files."""
    production = bake(context_override).settings("production")

    # value, not literal: the static files' cache control is an f-string over the expiry
    storages = production.value("STORAGES")
    assert storages["default"]["BACKEND"] == media
    assert storages["staticfiles"]["BACKEND"] == static
    # However they are served, the static files are hashed: nothing is served stale
    assert static in HASHED_STORAGES

    uploads_on_s3 = media == S3_STORAGE
    assert ("DJANGO_AWS_STORAGE_BUCKET_NAME" in {read.name for read in production.env_reads()}) is uploads_on_s3
    assert ('MEDIA_URL = f"https://{aws_s3_domain}/media/"' in production.source) is uploads_on_s3
    static_on_s3 = static == S3_MANIFEST_STORAGE
    assert ('STATIC_URL = f"https://{aws_s3_domain}/static/"' in production.source) is static_on_s3
    assert ('INSTALLED_APPS = ["collectfasta", *INSTALLED_APPS]' in production.source) is static_on_s3
    # A hashed file may be cached for as long as a browser likes; an upload keeps its name
    assert ("immutable" in production.source) is static_on_s3
    assert ("must-revalidate" in production.source) is uploads_on_s3


# (mail service, the email backend, the extra of the django-anymail pin, the ANYMAIL settings
# and the environment variables they read)
MAIL_SERVICES = [
    (
        "Mailgun",
        "anymail.backends.mailgun.EmailBackend",
        {"mailgun"},
        {
            "MAILGUN_API_KEY": "MAILGUN_API_KEY",
            "MAILGUN_SENDER_DOMAIN": "MAILGUN_DOMAIN",
            "MAILGUN_API_URL": "MAILGUN_API_URL",
        },
    ),
    ("Amazon SES", "anymail.backends.amazon_ses.EmailBackend", {"amazon-ses"}, {}),
    ("Other SMTP", "django.core.mail.backends.smtp.EmailBackend", set(), {}),
]


@pytest.mark.parametrize(
    ("mail_service", "backend", "extras", "anymail"),
    MAIL_SERVICES,
    ids=[row[0] for row in MAIL_SERVICES],
)
def test_production_mail_service(bake, mail_service, backend, extras, anymail):
    """Mail goes through the chosen service's backend, configured from the environment through Anymail."""
    project = bake({"mail_service": mail_service})
    production = project.settings("production")

    anymail_pin = next(pin for pin in project.pins["dependencies"] if pin.name == "django-anymail")
    assert anymail_pin.extras == extras
    assert 'INSTALLED_APPS += ["anymail"]' in production.source
    assert production.literal("EMAIL_BACKEND") == backend
    assert set(production.value("ANYMAIL")) == set(anymail)
    reads = {read.name: read for read in production.env_reads()}
    assert set(anymail.values()) <= set(reads)
    for variable in anymail.values():
        assert reads[variable].method is None
    if "MAILGUN_API_URL" in reads:
        assert reads["MAILGUN_API_URL"].default == "https://api.mailgun.net/v3"


# (mail catcher, its Compose service, the port it listens on)
MAIL_CATCHERS = [("Mailpit", "mailpit", 1025), ("Mailtrap Local", "mailtrap-local", 3535)]


@pytest.mark.parametrize("use_docker", ["n", "y"])
@pytest.mark.parametrize(("mail_catcher", "service", "port"), MAIL_CATCHERS, ids=[row[0] for row in MAIL_CATCHERS])
def test_local_mail_catcher(bake, mail_catcher, service, port, use_docker):
    """Development mail goes to the chosen catcher: its Compose service with Docker, localhost without."""
    project = bake({"mail_catcher": mail_catcher, "use_docker": use_docker})
    local = project.settings("local")

    assert "EMAIL_BACKEND" not in local.source
    assert f"EMAIL_PORT = {port}" in local.source
    if use_docker == "y":
        # The module is outside the reader's subset with Docker (INTERNAL_IPS += inside an if)
        assert env_read(local, "EMAIL_HOST").default == service
        assert service in project.compose("local")["services"]
    else:
        assert local.literal("EMAIL_HOST") == "localhost"
        assert local.literal("EMAIL_PORT") == port


def test_local_mail_without_a_catcher(bake, context):
    """Without a catcher, development mail is printed to the console unless the environment says otherwise."""
    local = bake({**context, "mail_catcher": "None"}).settings("local")

    assert "EMAIL_HOST" not in local.source
    assert env_read(local, "DJANGO_EMAIL_BACKEND").default == "django.core.mail.backends.console.EmailBackend"


# (identity provider, its allauth provider app, the origin the Content Security Policy
# lets the login form submit to, the credentials read from the environment)
IDENTITY_PROVIDERS = [
    (
        "entra",
        "allauth.socialaccount.providers.openid_connect",
        "https://login.microsoftonline.com",
        ("ENTRA_TENANT_ID", "ENTRA_LOGIN_CLIENT_ID", "ENTRA_LOGIN_CLIENT_SECRET"),
    ),
    (
        "google",
        "allauth.socialaccount.providers.google",
        "https://accounts.google.com",
        ("GOOGLE_LOGIN_CLIENT_ID", "GOOGLE_LOGIN_CLIENT_SECRET"),
    ),
]
# The files that sign-in through a provider adds, relative to the project root; ``{package}``
# stands for the project package
IDENTITY_PROVIDER_FILES = [
    "docs/authentication.rst",
    "{package}/users/checks.py",
    "{package}/users/tests/social.py",
    "{package}/users/tests/test_checks.py",
    "{package}/users/tests/test_social_login.py",
]
# The Entra provider subclass and its test
ENTRA_FILES = ["{package}/users/providers.py", "{package}/users/tests/test_providers.py"]


def generated(project: GeneratedProject, path: str) -> Path:
    """The path of a listed file in ``project``, with the package name filled in."""
    return project.root / path.format(package=project.package)


@pytest.mark.parametrize(
    ("identity_provider", "app", "origin", "credentials"),
    IDENTITY_PROVIDERS,
    ids=[row[0] for row in IDENTITY_PROVIDERS],
)
def test_identity_provider_login(bake, identity_provider, app, origin, credentials):
    """A provider is configured from the environment, and the policy lets the login form reach it."""
    project = bake({"identity_provider": identity_provider})

    base = project.settings("base")
    assert app in base.literal("INSTALLED_APPS")
    assert base.value("SECURE_CSP")["form-action"] == [Expression("CSP.SELF"), origin]
    (provider_settings,) = base.value("SOCIALACCOUNT_PROVIDERS").values()
    (provider_app,) = provider_settings["APPS"]
    # The credentials are the names read from the environment
    assert provider_app["client_id"] == base.value(credentials[-2])
    assert provider_app["secret"] == base.value(credentials[-1])
    reads = {read.name: read for read in base.env_reads()}
    assert all(reads[name].default == "" for name in credentials)
    assert set(credentials) <= set(project.env("production", "django"))
    assert set(credentials) <= set(project.env("local", "django"))

    allauth = next(pin for pin in project.pins["dependencies"] if pin.name == "django-allauth")
    assert allauth.extras == {"mfa", "socialaccount"}
    for path in IDENTITY_PROVIDER_FILES:
        assert generated(project, path).exists(), path
    assert "authentication" in project.text("docs/index.rst")
    entra = identity_provider == "entra"
    for path in ENTRA_FILES:
        assert generated(project, path).exists() is entra, path
    assert ("def get_provider(" in project.text(f"{project.package}/users/adapters.py")) is entra


def test_entra_login_is_keyed_by_the_object_id(bake):
    """Entra goes through the generic OpenID Connect provider with UserInfo off (docs/adr/0007)."""
    project = bake({"identity_provider": "entra"})
    base = project.settings("base")

    (app,) = base.value("SOCIALACCOUNT_PROVIDERS")["openid_connect"]["APPS"]
    assert app["provider_id"] == "entra"
    assert app["name"] == "Microsoft Entra ID"
    assert app["settings"]["uid_field"] == "oid"
    assert app["settings"]["fetch_userinfo"] is False
    assert app["settings"]["scope"] == ["openid", "profile", "email"]
    assert app["settings"]["oauth_pkce_enabled"] is True
    assert app["settings"]["token_auth_method"] == "client_secret_basic"  # noqa: S105 - a method, not a secret
    assert app["settings"]["verified_email"] is True
    assert app["settings"]["server_url"] == Expression(
        "f'https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0'",
    )
    # The adapter hands out the subclass that refuses a token without a usable oid
    providers = project.text(f"{project.package}/users/providers.py")
    assert "class EntraProvider(OpenIDConnectProvider):" in providers
    assert "raise ProviderException(msg)" in providers


def test_google_login_follows_its_own_verified_flag(bake):
    base = bake({"identity_provider": "google"}).settings("base")

    google = base.value("SOCIALACCOUNT_PROVIDERS")["google"]
    (app,) = google["APPS"]
    assert "verified_email" not in app.get("settings", {})
    assert "VERIFIED_EMAIL" not in google
    assert google["SCOPE"] == ["profile", "email"]
    assert google["AUTH_PARAMS"] == {"access_type": "online"}
    assert google["OAUTH_PKCE_ENABLED"] is True


JWT_STRATEGY = "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy"
IDENTITY_APP_FILES = [
    "{package}/identity/__init__.py",
    "{package}/identity/admin.py",
    "{package}/identity/api.py",
    "{package}/identity/apps.py",
    "{package}/identity/auth.py",
    "{package}/identity/checks.py",
    "{package}/identity/frontend.py",
    "{package}/identity/management/commands/revoke_jwt_sessions.py",
    "{package}/identity/migrations/0001_initial.py",
    "{package}/identity/models.py",
    "{package}/identity/permissions.py",
    "{package}/identity/verification.py",
    "{package}/identity/tests/headless.py",
    "{package}/identity/tests/services.py",
    "{package}/identity/tests/test_apps.py",
    "{package}/identity/tests/test_auth.py",
    "{package}/identity/tests/test_frontend.py",
    "{package}/identity/tests/test_login.py",
    "{package}/identity/tests/test_permissions.py",
    "{package}/identity/tests/test_provider_login.py",
    "{package}/identity/tests/test_revoke_jwt_sessions.py",
    "{package}/identity/tests/test_services.py",
    "{package}/identity/tests/test_verification.py",
]
# The pages of the frontend contract, as HEADLESS_FRONTEND_URLS names them
FRONTEND_PAGES = {
    "account_confirm_email": "/account/verify-email/{key}",
    "account_reset_password": "/account/password/reset",
    "account_reset_password_from_key": "/account/password/reset/key/{key}",
    "account_signup": "/account/signup",
    "socialaccount_login_error": "/account/provider/callback",
}


@pytest.mark.parametrize("context_override", HEADLESS_COMBINATIONS, ids=_fixture_id)
def test_headless_login(bake, context_override):
    """Django Ninja with a provider serves allauth's app client with JWTs signed by a key of their own."""
    project = bake(context_override)

    base = project.settings("base")
    apps = base.literal("INSTALLED_APPS")
    assert "allauth.headless" in apps
    assert f"{project.package}.identity" in apps
    assert base.literal("HEADLESS_CLIENTS") == ("app",)
    assert base.literal("HEADLESS_ONLY") is False
    assert base.literal("HEADLESS_TOKEN_STRATEGY") == JWT_STRATEGY
    assert base.literal("HEADLESS_JWT_ALGORITHM") == "HS256"
    assert base.literal("HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED") is True
    assert base.literal("HEADLESS_JWT_ROTATE_REFRESH_TOKEN") is True
    assert base.literal("HEADLESS_SERVE_SPECIFICATION") is False
    reads = {read.name: read for read in base.env_reads()}
    assert (
        reads["DJANGO_HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN"].method,
        reads["DJANGO_HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN"].default,
    ) == ("int", 300)
    assert (
        reads["DJANGO_HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN"].method,
        reads["DJANGO_HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN"].default,
    ) == ("int", 86400)
    assert (reads["DJANGO_FRONTEND_ORIGINS"].method, reads["DJANGO_FRONTEND_ORIGINS"].default) == (
        "list",
        ["http://localhost:5173"],
    )
    assert (reads["DJANGO_FRONTEND_URL"].method, reads["DJANGO_FRONTEND_URL"].default) == (
        None,
        "http://localhost:5173",
    )
    assert "DJANGO_HEADLESS_JWT_PRIVATE_KEY" not in reads
    # The five pages of the frontend contract, at the frontend URL
    frontend_urls = base.value("HEADLESS_FRONTEND_URLS")
    assert set(frontend_urls) == set(FRONTEND_PAGES)
    for name, path in FRONTEND_PAGES.items():
        assert frontend_urls[name] == Expression(f"FRONTEND_URL + '{path}'")
    adapters = project.text(f"{project.package}/users/adapters.py")
    assert "def is_safe_url(self, url: str) -> bool:" in adapters
    # The API and allauth's endpoints answer the frontend, which sends the session token of pending flows
    assert base.literal("CORS_URLS_REGEX") == r"^/(api|_allauth)/.*$"
    assert base.value("CORS_ALLOWED_ORIGINS") == base.value("FRONTEND_ORIGINS")
    assert base.value("CORS_ALLOW_HEADERS") == Expression("[*default_headers, 'x-session-token']")

    # The signing key: drawn per environment, required in production, never SECRET_KEY
    production = project.settings("production")
    assert env_read(production, "DJANGO_HEADLESS_JWT_PRIVATE_KEY").default is NO_DEFAULT
    assert env_read(production, "DJANGO_FRONTEND_ORIGINS").default is NO_DEFAULT
    assert env_read(production, "DJANGO_FRONTEND_URL").default is NO_DEFAULT
    production_env = project.env("production", "django")
    keys = [
        production_env["DJANGO_HEADLESS_JWT_PRIVATE_KEY"],
        env_read(project.settings("local"), "DJANGO_HEADLESS_JWT_PRIVATE_KEY").default,
        env_read(project.settings("test"), "DJANGO_HEADLESS_JWT_PRIVATE_KEY").default,
    ]
    secret_keys = [
        production_env["DJANGO_SECRET_KEY"],
        env_read(project.settings("local"), "DJANGO_SECRET_KEY").default,
        env_read(project.settings("test"), "DJANGO_SECRET_KEY").default,
    ]
    assert all(TOKEN.fullmatch(key) for key in keys)
    assert len(set(keys + secret_keys)) == len(keys + secret_keys)
    assert "DJANGO_FRONTEND_ORIGINS" in production_env
    assert "DJANGO_FRONTEND_URL" in production_env

    assert 'path("_allauth/", include("allauth.headless.urls"))' in project.text("config/urls.py")
    allauth = next(pin for pin in project.pins["dependencies"] if pin.name == "django-allauth")
    assert allauth.extras == {"headless", "mfa", "socialaccount"}
    for path in IDENTITY_APP_FILES:
        assert generated(project, path).exists(), path
    # The API authenticates an app-issued JWT, or the session cookie with its CSRF check
    api = project.text("config/api.py")
    assert f"from {project.package}.identity.auth import user_auth" in api
    assert "auth=user_auth," in api
    assert "SessionAuth" not in api


@pytest.mark.parametrize("context_override", HEADLESS_COMBINATIONS, ids=_fixture_id)
def test_calling_services(bake, context_override):
    """The identity app verifies the provider's tokens for registered services, on settings alone."""
    project = bake(context_override)
    base = project.settings("base")
    reads = {read.name: read for read in base.env_reads()}
    production_env = project.env("production", "django")

    api = project.text("config/api.py")
    assert f'api.add_router("/principal/", "{project.package}.identity.api.router")' in api
    assert "class PrincipalHttpRequest(HttpRequest):" in project.text(f"{project.package}/typedefs.py")
    assert "pyjwt" in pinned(project)
    assert [pin.extras for pin in project.pins["dependencies"] if pin.name == "pyjwt"] == [{"crypto"}]
    assert base.value("IDENTITY_SERVICE_ISSUERS")
    assert "IDENTITY_SERVICE_AUDIENCE" in base.source
    assert "IDENTITY_SERVICE_DISCOVERY_URL" in base.source
    if context_override["identity_provider"] == "entra":
        assert reads["ENTRA_API_CLIENT_ID"].default == ""
        assert reads["ENTRA_SERVICE_ROLE"].default == "Service.Access"
        assert base.value("IDENTITY_SERVICE_AUDIENCE") == base.value("ENTRA_API_CLIENT_ID")
        assert "ENTRA_API_CLIENT_ID" in production_env
    else:
        assert reads["GOOGLE_SERVICE_AUDIENCE"].default == "https://example.com"
        assert base.literal("IDENTITY_SERVICE_ISSUERS") == ["https://accounts.google.com", "accounts.google.com"]


@pytest.mark.parametrize(
    "context_override",
    [{"identity_provider": "entra"}, {"identity_provider": "google", "rest_api": "DRF"}, {"rest_api": "Django Ninja"}],
    ids=_fixture_id,
)
def test_no_headless_login_without_ninja_and_a_provider(bake, context_override):
    project = bake(context_override)

    base = project.settings("base")
    assert "allauth.headless" not in base.literal("INSTALLED_APPS")
    assert "HEADLESS" not in base.source
    assert "FRONTEND" not in base.source
    assert "_allauth" not in project.text("config/urls.py")
    assert not (project.root / project.package / "identity").exists()
    assert "is_safe_url" not in project.text(f"{project.package}/users/adapters.py")
    if context_override.get("rest_api") == "Django Ninja":
        assert "auth=SessionAuth()," in project.text("config/api.py")
    assert "DJANGO_HEADLESS_JWT_PRIVATE_KEY" not in project.env("production", "django")
    allauth = next(pin for pin in project.pins["dependencies"] if pin.name == "django-allauth")
    assert "headless" not in allauth.extras


def test_no_identity_provider(bake):
    """Without a provider the project has password login only, as before the option."""
    project = bake({"identity_provider": "none"})

    base = project.settings("base")
    assert "SOCIALACCOUNT_PROVIDERS" not in base.source
    assert not any("providers" in app for app in base.literal("INSTALLED_APPS"))
    assert base.value("SECURE_CSP")["form-action"] == [Expression("CSP.SELF")]
    allauth = next(pin for pin in project.pins["dependencies"] if pin.name == "django-allauth")
    assert allauth.extras == {"mfa"}
    for path in [*IDENTITY_PROVIDER_FILES, *ENTRA_FILES]:
        assert not generated(project, path).exists(), path
    assert "authentication" not in project.text("docs/index.rst")


@pytest.mark.parametrize("use_sentry", ["n", "y"])
def test_sentry_wiring(bake, context, use_sentry):
    """The production settings configure Sentry and install the app that initialises the SDK."""
    context["use_sentry"] = use_sentry
    project = bake(context)

    selected = use_sentry == "y"
    package = Path(context["project_slug"])
    assert (project.root / package / "sentry" / "apps.py").exists() is selected
    assert (project.root / package / "tests" / "test_sentry.py").exists() is selected
    assert ("sentry-sdk" in pinned(project)) is selected

    # Importing the settings initialises nothing; the app does, once the registry is ready
    production = project.settings("production")
    assert "import sentry_sdk" not in production.source
    assert "sentry_sdk.init" not in production.source
    assert (f'INSTALLED_APPS += ["{package}.sentry"]' in production.source) is selected
    reads = {read.name: read for read in production.env_reads()}
    assert ("SENTRY_DSN" in reads) is selected
    if selected:
        assert reads["SENTRY_DSN"].default is NO_DEFAULT
        assert reads["SENTRY_ENVIRONMENT"].default == "production"
        assert "sentry_sdk.init(" in project.text(package / "sentry" / "apps.py")


BEFORE_MIDDLEWARE = "django_prometheus.middleware.PrometheusBeforeMiddleware"
AFTER_MIDDLEWARE = "django_prometheus.middleware.PrometheusAfterMiddleware"


OBSERVABILITY_ANSWERS = ["none", "prometheus", "opentelemetry"]


@pytest.mark.parametrize("observability", OBSERVABILITY_ANSWERS)
def test_metrics_wiring(bake, context, observability):
    """The metrics of django-prometheus: the app, the middleware pair that wraps the
    chain, the instrumented backends, and the endpoint behind its own credential."""
    context["observability"] = observability
    context["use_docker"] = "y"
    project = bake(context)

    selected = observability == "prometheus"
    package = Path(context["project_slug"])
    assert (project.root / package / "metrics.py").exists() is selected
    assert (project.root / package / "tests" / "test_metrics.py").exists() is selected
    assert ("django-prometheus" in pinned(project)) is selected

    base = project.settings("base")
    assert ("django_prometheus" in base.value("INSTALLED_APPS")) is selected
    middleware = base.value("MIDDLEWARE")
    assert (middleware[0] == BEFORE_MIDDLEWARE) is selected
    assert (middleware[-1] == AFTER_MIDDLEWARE) is selected
    # DATABASES is bound in a branch and then mutated, so the assignment is read as written
    engine = 'DATABASES["default"]["ENGINE"] = "django_prometheus.db.backends.postgresql"'
    assert (engine in base.source) is selected
    reads = {read.name: read for read in base.env_reads()}
    assert ("DJANGO_METRICS_TOKEN" in reads) is selected

    # local.py and production.py each bind their own cache, and both wrap the backend
    for environment, backend in (("local", "locmem.LocMemCache"), ("production", "redis.RedisCache")):
        wrapped = f'"BACKEND": "django_prometheus.cache.backends.{backend}"'
        assert (wrapped in project.settings(environment).source) is selected

    # The endpoint is routed in every environment; nothing about it is conditional at runtime
    assert ('path("metrics", metrics, name="metrics")' in project.text("config/urls.py")) is selected
    services = project.compose("local")["services"]
    assert ("prometheus" in services) is selected
    if selected:
        # The scrape reads the container, not one worker of it
        start = project.text(Path("compose") / "production" / "django" / "start")
        assert "export PROMETHEUS_MULTIPROC_DIR=" in start
        assert "--config /app/config/gunicorn.py" in start
        assert "mark_process_dead" in project.text(Path("config") / "gunicorn.py")
        assert services["prometheus"]["depends_on"] == ["django"]


TASK_WORKER_START = Path("compose") / "production" / "django" / "tasks" / "worker" / "start"
COLLECTOR_CONFIG = Path("compose") / "local" / "otel-collector" / "config.yml"


@pytest.mark.parametrize("observability", OBSERVABILITY_ANSWERS)
def test_telemetry_wiring(bake, context, observability):
    """Traces and metrics over OTLP: the app, the settings with every default off, the
    entry point of each serving process, and the collector that receives them."""
    context["observability"] = observability
    context["use_docker"] = "y"
    project = bake(context)

    selected = observability == "opentelemetry"
    package = Path(context["project_slug"])
    assert (project.root / package / "telemetry" / "configure.py").exists() is selected
    assert (project.root / package / "telemetry" / "asgi.py").exists() is selected
    # A web worker is ended by a re-raised signal, so the lifespan is where it flushes
    assert ("flushing_on_shutdown" in project.text(Path("config") / "asgi.py")) is selected
    assert (project.root / package / "tests" / "test_telemetry.py").exists() is selected
    assert (pinned(project) >= TELEMETRY_PACKAGES) is selected
    # Both arms measure something, and the page says where what they measure is read
    measured = observability != "none"
    assert (project.root / "docs" / "observability.rst").exists() is measured
    assert (project.root / "config" / "gunicorn.py").exists() is measured

    base = project.settings("base")
    assert (f"{context['project_slug']}.telemetry" in base.value("INSTALLED_APPS")) is selected
    reads = {read.name: read for read in base.env_reads()}
    assert ("OTEL_EXPORTER_OTLP_ENDPOINT" in reads) is selected

    services = project.compose("local")["services"]
    assert ("otel-collector" in services) is selected
    if not selected:
        return
    # Nothing is exported until a deployment names a destination
    assert reads["OTEL_EXPORTER_OTLP_ENDPOINT"].default == ""
    assert reads["OTEL_SERVICE_NAME"].default == context["project_slug"]
    # Each process that serves something starts its own exporters, and no command does
    assert "post_fork" in project.text(Path("config") / "gunicorn.py")
    start = project.text(Path("compose") / "production" / "django" / "start")
    assert "--config /app/config/gunicorn.py" in start
    assert "DJANGO_TELEMETRY_COMPONENT=taskworker" in project.text(TASK_WORKER_START)
    # The application exports to the collector, so the collector is up first
    assert "otel-collector" in services["django"]["depends_on"]
    # And the address it is given is the one the collector listens on
    receiver = yaml.safe_load(project.text(COLLECTOR_CONFIG))["receivers"]["otlp"]
    _, _, port = receiver["protocols"]["http"]["endpoint"].rpartition(":")
    assert project.env("local", "django")["OTEL_EXPORTER_OTLP_ENDPOINT"].endswith(f":{port}")


@pytest.mark.parametrize("observability", ["prometheus", "opentelemetry"])
def test_an_arm_that_measures_starts_without_docker(bake, context, observability):
    """The Compose files that start a deployed container are pruned with use_docker=n,
    and both arms are still generated whole. What is left has to be startable: the
    configuration Gunicorn is given is still here, and the page says what the process
    that starts it has to do. That nothing sends a reader to a file this tree does not
    have is ``test_no_file_cites_a_path_its_answers_removed``, for every combination.
    """
    context["observability"] = observability
    context["use_docker"] = "n"
    project = bake(context)

    assert not (project.root / "compose").exists()
    assert (project.root / "config" / "gunicorn.py").exists()

    # Nothing else tells Gunicorn where its hooks are, so the page has to
    page = project.text(Path("docs") / "observability.rst")
    assert "--config config/gunicorn.py" in page
    started = "PROMETHEUS_MULTIPROC_DIR=" if observability == "prometheus" else "DJANGO_TELEMETRY_COMPONENT"
    assert started in page


def test_the_exit_hook_holds_without_the_directory_it_retires_from(bake, context):
    """The hook runs in the arbiter, so what it raises ends the deployment rather than
    the worker that exited; nothing sets the variable where the start script is pruned."""
    project = bake({**context, "observability": "prometheus", "use_docker": "n"})

    hook = project.text(Path("config") / "gunicorn.py")
    assert "MULTIPROCESS_DIRECTORY = " in hook
    # The client is asked only once the deployment has said where the samples go
    guard, _, retire = hook.partition("multiprocess.mark_process_dead")
    assert "if not os.environ.get(MULTIPROCESS_DIRECTORY):" in guard.rpartition("def child_exit")[2]
    assert retire


def test_a_celery_worker_starts_and_stops_its_own_telemetry(bake, context):
    """The prefork pool forks its workers, so they start after the fork rather than
    wherever the parent reaches: ready() would run before it. The pool ends those
    children itself, so what they are still holding goes from the shutdown signal."""
    project = bake({**context, "observability": "opentelemetry", "use_celery": "y"})

    celery_app = project.text(Path("config") / "celery_app.py")
    assert "worker_process_init" in celery_app
    assert "beat_init" in celery_app
    # Under the deadline, which is what a worker child shares with a web worker
    assert "worker_process_shutdown" in celery_app
    assert "telemetry.flush()" in celery_app


# Whether a project has the verifier of calling services, and whether it also has the API
# that reads one: the answers that decide are the provider and what consumes its tokens.
MACHINE_AUTHENTICATION = [
    ({"identity_provider": "none", "rest_api": "Django Ninja"}, False, False),
    ({"identity_provider": "entra"}, False, False),
    ({"identity_provider": "entra", "rest_api": "Django Ninja"}, True, True),
    ({"identity_provider": "google", "observability": "prometheus"}, True, False),
]


@pytest.mark.parametrize(
    ("answers", "verifier", "api"),
    MACHINE_AUTHENTICATION,
    ids=["no provider", "nothing reads a token", "the api reads one", "a scrape reads one"],
)
def test_machine_authentication_wiring(bake, context, answers, verifier, api):
    """The identity app verifies the tokens of calling services wherever something reads
    one, and the policies Django Ninja's routes run under are generated only with it."""
    project = bake({**context, **answers})

    package = Path(context["project_slug"])
    identity = project.root / package / "identity"
    assert (identity / "verification.py").exists() is verifier
    assert (identity / "models.py").exists() is verifier
    assert (identity / "tests" / "services.py").exists() is verifier
    # The API's side: the policies, the routes they guard and what drives them in the tests
    assert (identity / "auth.py").exists() is api
    assert (identity / "tests" / "headless.py").exists() is api
    assert ("pyjwt" in pinned(project)) is verifier

    base = project.settings("base")
    installed = f"{context['project_slug']}.identity"
    assert (installed in base.value("INSTALLED_APPS")) is verifier
    assert ("IDENTITY_SERVICE_ISSUERS" in base.source) is verifier

    # A scrape presents a token of the provider's, and the permission says it may
    scraped = answers.get("observability") == "prometheus"
    permission = identity / "migrations" / "0002_the_metrics_permission.py"
    assert permission.exists() is (verifier and scraped)
    if scraped:
        assert ("identity.read_metrics" in project.text(package / "metrics.py")) is verifier


# The agent guide: where each coding agent reads its instructions, as the agent's own
# convention names the file, written from the options page rather than from the hook's table.
AGENT_FILES = {
    "none": None,
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "cursor": "AGENTS.md",
    "copilot": ".github/copilot-instructions.md",
}
# A row of a guide table: the first cell in backticks, the rest of the row after it.
RE_GUIDE_ROW = re.compile(r"\|\s*`([^`]+)`\s*\|(.*)\|")
RE_ANSWER_CELL = re.compile(r"\s*`([^`]*)`\s*")


def guide_section(guide, heading):
    """The lines of the guide's section under ``heading``, up to the next one."""
    _, marker, rest = guide.partition(f"\n## {heading}\n")
    assert marker, f"the guide has no {heading!r} section"
    return rest.partition("\n## ")[0].splitlines()


def guide_rows(guide, heading):
    """The table rows of the guide's ``heading`` section: first cell to the rest of the row."""
    rows = (RE_GUIDE_ROW.fullmatch(line) for line in guide_section(guide, heading))
    return {row.group(1): row.group(2) for row in rows if row is not None}


def agent_guide(project, answers):
    """The text of the guide the ``answers`` placed, or ``None`` when no agent was chosen."""
    file = AGENT_FILES[answers["coding_agent"]]
    return None if file is None else project.text(file)


def test_agent_files_cover_every_coding_agent():
    """A choice this file does not know would go unchecked below."""
    assert set(AGENT_FILES) == set(OPTIONS["coding_agent"].choices)


@pytest.mark.parametrize("context_override", GROUPED_COMBINATIONS)
def test_agent_guide_is_placed_where_the_chosen_agent_reads_it(bake, context_override):
    """One guide, under the name its agent reads, and no file for any other agent."""
    project = bake(context_override)

    expected = AGENT_FILES[complete_answers(context_override)["coding_agent"]]
    for file in {file for file in AGENT_FILES.values() if file is not None}:
        assert (project.root / file).exists() is (file == expected), file


@pytest.mark.parametrize("context_override", GUIDE_COMBINATIONS)
def test_agent_guide_records_the_answers_the_project_was_generated_from(bake, context_override):
    """The choices table holds every list and flag option, with the answer as given."""
    answers = complete_answers(context_override)
    guide = agent_guide(bake(context_override), answers)

    recorded = guide_rows(guide, "Generation choices")
    assert list(recorded) == list(option_names(LIST, FLAG))
    for name, cell in recorded.items():
        assert RE_ANSWER_CELL.fullmatch(cell).group(1) == answers[name], name


@pytest.mark.parametrize("context_override", GUIDE_COMBINATIONS)
def test_agent_guide_lays_out_the_tree_that_was_generated(bake, context_override):
    """Every path the layout table names is in the project, whatever the answers pruned."""
    project = bake(context_override)
    guide = agent_guide(project, complete_answers(context_override))

    paths = guide_rows(guide, "Layout")
    assert paths
    for path in paths:
        assert (project.root / path).exists(), path
