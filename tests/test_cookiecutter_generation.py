import ast  # noqa: EXE002
import hashlib
import json
import os
import re
import shutil
import tomllib
from pathlib import Path

import pytest
import sh
import yaml
from binaryornot.check import is_binary
from cookiecutter.exceptions import FailedHookException

from local_extensions import FLAG
from local_extensions import OPTIONS
from local_extensions import option_names
from tests.generated_project import EnvRead
from tests.generated_project import GeneratedProject
from tests.generated_project import PythonModule

PATTERN = r"{{(\s?cookiecutter)[.](.*?)}}"
RE_OBJ = re.compile(PATTERN)
# A secret the post-generation hook did not fill in
RE_PLACEHOLDER = re.compile(r"!!!SET \w+!!!")
# <script src="http(s)://..."> or <link href="http(s)://...">
RE_REMOTE_ASSET = re.compile(r"<(?:script|link)\b[^>]*\b(?:src|href)=[\"']https?://", re.IGNORECASE)
# Inline code the Content Security Policy would block: <script> without src or nonce,
# any <style> block (style-src allows no nonce), style="..." attributes, on*="..." handlers
RE_INLINE_CODE = re.compile(
    r"<script\b(?![^>]*\b(?:src|nonce)=)[^>]*>|<style\b|\sstyle=[\"']|\son[a-z]+=[\"']",
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

# The style checks that a formatter run after generation would fix: ruff format, djlint's
# formatter and django-upgrade. They take longer than the rest of the suite, so they run
# only with AUTOFIXABLE_STYLES=1; CI runs just them in its own job, selected by the marker.
# A defect they find is fixed in the template, so the generated project starts clean.
AUTOFIXABLE_STYLES = os.getenv("AUTOFIXABLE_STYLES") == "1"


def auto_fixable(test):
    """Mark ``test`` as an auto-fixable style check: skipped without the flag, selectable with ``-m``."""
    return pytest.mark.auto_fixable(pytest.mark.skipif(not AUTOFIXABLE_STYLES, reason="auto-fixable")(test))


@pytest.fixture
def context():
    return {
        "project_name": "My Test Project",
        "project_slug": "my_test_project",
        "author_name": "Test Author",
        "email": "test@example.com",
        "description": "A short description of the project.",
        "domain_name": "example.com",
        "version": "0.1.0",
        "timezone": "UTC",
    }


@pytest.fixture
def hostile_context(context):
    """The context with free-text answers built from the characters that end or escape a string."""
    return {
        **context,
        "project_name": 'My "Test" Project\\',
        "description": 'She said "hi" & <left> C:\\path, it\'s fine.',
        "author_name": 'Tess "Quoted" O\'Brien',
        "email": '"Tess O\'Brien"@example.com',
    }


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
    projects: dict[tuple[tuple[str, str], ...], GeneratedProject] = {}

    def bake(answers: dict[str, str]) -> GeneratedProject:
        key = tuple(sorted({**DEFAULT_ANSWERS, **answers}.items()))
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

# Answers that only show their effect together, baked on top of the derived rows below:
# cloud_provider and use_whitenoise decide the storage backends between them (and None
# with WhiteNoise off is rejected, so no single-answer row can reach cloud_provider=None),
# and Channels has its own wiring in the Docker and Celery files. mail_service shares no
# conditional with cloud_provider anywhere in the template, so the two need no cross
# product: Amazon SES bakes on the default cloud_provider=AWS, the only one it supports.
PAIRED_COMBINATIONS = [
    {"cloud_provider": "AWS", "use_whitenoise": "y"},
    {"cloud_provider": "None", "use_whitenoise": "y"},
    {"realtime": "channels", "use_docker": "y"},
    {"realtime": "channels", "use_celery": "y", "use_docker": "y"},
]

DEFAULT_ANSWERS = {name: option.default for name, option in OPTIONS.items()}


def rejected(answers):
    """Would the pre-generation hook refuse ``answers`` once the defaults fill in the rest?"""
    effective = {**DEFAULT_ANSWERS, **answers}
    return any(all(effective[name] == value for name, value in pair.items()) for pair in UNSUPPORTED_COMBINATIONS)


def supported_combinations():
    """The answers the generation tests bake: the defaults, one row per choice of every list
    and flag option in the catalogue, and the paired rows. A row that the hook would reject,
    or whose answers amount to an earlier row's, is left out, so each project bakes once."""
    per_choice = ({name: choice} for name, option in OPTIONS.items() for choice in option.choices)
    rows = [{}, *per_choice, *PAIRED_COMBINATIONS]
    seen = set()
    unique = []
    for row in rows:
        effective = tuple(sorted({**DEFAULT_ANSWERS, **row}.items()))
        if rejected(row) or effective in seen:
            continue
        seen.add(effective)
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
        if not any({**DEFAULT_ANSWERS, **row}[name] == choice for row in SUPPORTED_COMBINATIONS)
    ]
    assert unbaked == []


def test_combinations_name_options_of_the_catalogue():
    """A misspelt option or choice in a hand-written row would bake the default project and pass."""
    for row in [*PAIRED_COMBINATIONS, *UNSUPPORTED_COMBINATIONS]:
        for name, value in row.items():
            assert name in OPTIONS, f"{name!r} is not an option: {row}"
            assert value in OPTIONS[name].choices, f"{value!r} is not a choice of {name}: {row}"


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


# The generated files that hold a secret drawn on each bake, so two bakes never agree on them.
SECRET_FILES = {
    ".envs/.local/.django",
    ".envs/.local/.postgres",
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
    assert ("sentry_sdk" in uppercase.settings("production").source) is selected
    assert (uppercase.root / "docker-compose.local.yml").exists() is selected
    assert (uppercase.root / ".envs").exists() is selected
    assert ("!.envs/.local/" in uppercase.text(".gitignore")) is selected
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
    ({"use_whitenoise": "y"}, {"whitenoise"}, {"collectfasta"}),
    ({"cloud_provider": "AWS", "use_whitenoise": "n"}, {"django-storages", "collectfasta"}, {"whitenoise"}),
    ({"cloud_provider": "None", "use_whitenoise": "y"}, {"whitenoise"}, {"django-storages", "collectfasta"}),
    ({"mail_service": "Other SMTP"}, {"django-anymail"}, set()),
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
        "docker-compose.production.yml",
        "docker-compose.docs.yml",
    ]
    for compose_file in compose_files:
        assert (project.root / compose_file).exists() is (use_docker == "y")


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
    """Generated project uses django-htmx + vendored Pico CSS and has no Node.js/asset pipeline leftovers."""
    project = bake(context)

    for path in FRONTEND_TOOLCHAIN_PATHS:
        assert not (project.root / path).exists(), f"{path} should not be generated"

    offenders = []
    for path in project.files():
        if "static/vendor/" in path.as_posix() or is_binary(str(project.root / path)):
            continue
        content = project.text(path).lower()
        offenders.extend(f"{path}: {token}" for token in FRONTEND_TOOLCHAIN_TOKENS if token in content)
    assert offenders == []

    base = project.settings("base")
    assert "django_htmx" in base.literal("INSTALLED_APPS")
    assert "django_htmx.middleware.HtmxMiddleware" in base.literal("MIDDLEWARE")
    assert "django-htmx" in pinned(project)

    base_html = project.template("base.html")
    assert "{% htmx_script %}" in base_html
    assert 'hx-headers=\'{"X-CSRFToken": "{{ csrf_token }}"}\'' in base_html
    assert "vendor/pico/pico.min.css" in base_html


def test_no_remote_assets(bake, context):
    """No stylesheet or script is loaded from a CDN or any other remote host."""
    project = bake(context)

    offenders = [
        path for path in project.files() if path.suffix == ".html" and RE_REMOTE_ASSET.search(project.text(path))
    ]
    assert offenders == []


def test_vendored_pico_intact(bake, context):
    """The vendored Pico CSS is copied byte-for-byte and matches its recorded checksum."""
    project = bake(context)

    vendor_dir = Path("my_test_project") / "static" / "vendor" / "pico"
    metadata = project.json(vendor_dir / "pico.json")
    css = project.bytes(vendor_dir / metadata["file"])

    assert hashlib.sha256(css).hexdigest() == metadata["sha256"]
    assert f"v{metadata['version']}".encode() in css[:300]
    assert project.text(vendor_dir / "LICENSE.md").startswith("MIT License")


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
