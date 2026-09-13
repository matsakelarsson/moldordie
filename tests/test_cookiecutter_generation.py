import ast  # noqa: EXE002
import glob
import hashlib
import json
import os
import re
import tomllib
from collections.abc import Iterable
from pathlib import Path

import pytest
import sh
import yaml
from binaryornot.check import is_binary
from cookiecutter.exceptions import FailedHookException

PATTERN = r"{{(\s?cookiecutter)[.](.*?)}}"
RE_OBJ = re.compile(PATTERN)
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


SUPPORTED_COMBINATIONS = [
    {"username_type": "username"},
    {"username_type": "email"},
    {"open_source_license": "MIT"},
    {"open_source_license": "BSD"},
    {"open_source_license": "GPLv3"},
    {"open_source_license": "Apache Software License 2.0"},
    {"open_source_license": "Not open source"},
    {"use_docker": "y"},
    {"use_docker": "n"},
    {"postgresql_version": "18"},
    {"postgresql_version": "17"},
    {"postgresql_version": "16"},
    {"postgresql_version": "15"},
    {"postgresql_version": "14"},
    # cloud_provider and use_whitenoise decide together which storage backends are configured.
    {"cloud_provider": "AWS", "use_whitenoise": "y"},
    {"cloud_provider": "AWS", "use_whitenoise": "n"},
    {"cloud_provider": "None", "use_whitenoise": "y"},
    # Note: cloud_provider=None AND use_whitenoise=n is not supported
    # mail_service shares no conditional with cloud_provider anywhere in the template, so the two
    # need no cross product. Amazon SES bakes on the default cloud_provider=AWS, the only one it
    # supports.
    {"mail_service": "Mailgun"},
    {"mail_service": "Amazon SES"},
    {"mail_service": "Other SMTP"},
    {"rest_api": "None"},
    {"rest_api": "DRF"},
    {"rest_api": "Django Ninja"},
    {"realtime": "none"},
    {"realtime": "channels"},
    {"realtime": "channels", "use_docker": "y"},
    {"realtime": "channels", "use_celery": "y", "use_docker": "y"},
    {"use_celery": "y"},
    {"use_celery": "n"},
    {"mail_catcher": "None"},
    {"mail_catcher": "Mailpit"},
    {"mail_catcher": "Mailtrap Local"},
    {"use_sentry": "y"},
    {"use_sentry": "n"},
    {"ci_tool": "None"},
    {"ci_tool": "Gitlab"},
    {"ci_tool": "Github"},
    {"keep_local_envs_in_vcs": "y"},
    {"keep_local_envs_in_vcs": "n"},
    {"debug": "y"},
    {"debug": "n"},
]

UNSUPPORTED_COMBINATIONS = [
    {"cloud_provider": "None", "use_whitenoise": "n"},
    {"cloud_provider": "None", "mail_service": "Amazon SES"},
]

# The yes/no answers: typed as text, so the pre-generation hook validates them.
FLAG_OPTIONS = ["use_docker", "use_celery", "use_sentry", "use_whitenoise", "keep_local_envs_in_vcs", "debug"]


def _fixture_id(ctx):
    """Helper to get a user-friendly test name from the parametrized context."""
    return "-".join(f"{key}:{value}" for key, value in ctx.items())


def _fixture_id_of_first(value):
    """Name a parametrized case after its context override, and nothing after the other arguments."""
    return _fixture_id(value) if isinstance(value, dict) else ""


def build_files_list(base_path: Path):
    """Build a list containing absolute paths to the generated files."""
    excluded_dirs = {".venv", "__pycache__"}

    f = []
    for dirpath, subdirs, files in base_path.walk():
        subdirs[:] = [d for d in subdirs if d not in excluded_dirs]

        f.extend(dirpath / file_path for file_path in files)
    return f


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


def check_paths(paths: Iterable[Path]):
    """Every text file is fully rendered and, if it has a syntax, parses."""
    for path in paths:
        if is_binary(str(path)):
            continue

        content = path.read_text()
        match = RE_OBJ.search(content)
        assert match is None, f"cookiecutter variable not replaced in {path}"
        parse = PARSERS.get(path.suffix)
        if parse is not None:
            try:
                parse(content)
            except (SyntaxError, ValueError, yaml.YAMLError) as e:
                pytest.fail(f"{path} does not parse: {e}")


def literal_assignments(path: Path) -> dict[str, object]:
    """The module-level names a Python file binds to literals, with their values."""
    values = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    continue
    return values


@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_project_generation(cookies, hostile_context, context_override):
    """The project is generated, fully rendered and parseable, whatever the free-text answers."""

    result = cookies.bake(extra_context={**hostile_context, **context_override})
    assert result.exit_code == 0
    assert result.exception is None
    assert result.project_path.name == hostile_context["project_slug"]
    assert result.project_path.is_dir()

    paths = build_files_list(result.project_path)
    assert paths
    check_paths(paths)


@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_ruff_check_passes(cookies, context_override):
    """Generated project should pass ruff check."""
    result = cookies.bake(extra_context=context_override)

    try:
        sh.ruff("check", ".", _cwd=str(result.project_path))
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_ruff_format_passes(cookies, context_override):
    """The generated project is formatted as ruff format would leave it."""
    result = cookies.bake(extra_context=context_override)

    try:
        sh.ruff("format", "--check", ".", _cwd=str(result.project_path))
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_django_upgrade_passes(cookies, context_override):
    """django-upgrade, for the Django the project pins, would rewrite nothing in it."""
    result = cookies.bake(extra_context=context_override)

    python_files = [
        file_path.removeprefix(f"{result.project_path}/")
        for file_path in glob.glob(str(result.project_path / "**" / "*.py"), recursive=True)  # noqa: PTH207
    ]
    try:
        sh.django_upgrade(
            "--target-version",
            "6.0",
            *python_files,
            _cwd=str(result.project_path),
        )
    except sh.ErrorReturnCode as e:
        # django-upgrade names the files it rewrote on stderr.
        pytest.fail(e.stdout.decode() + e.stderr.decode())


@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_djlint_lint_passes(cookies, context_override):
    """Check whether generated project passes djLint --lint."""
    result = cookies.bake(extra_context=context_override)

    autofixable_rules = "H014,T001"
    # TODO: remove T002 when fixed https://github.com/Riverside-Healthcare/djLint/issues/687
    ignored_rules = "H006,H030,H031,T002"
    try:
        sh.djlint(
            "--lint",
            "--ignore",
            f"{autofixable_rules},{ignored_rules}",
            ".",
            _cwd=str(result.project_path),
        )
    except sh.ErrorReturnCode as e:
        pytest.fail(e.stdout.decode())


@auto_fixable
@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_djlint_check_passes(cookies, context_override):
    """Check whether generated project passes djLint --check."""
    result = cookies.bake(extra_context=context_override)

    try:
        sh.djlint("--check", ".", _cwd=str(result.project_path))
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
    cookies,
    context,
    use_docker,
    expected_typecheck_script,
    expected_test_script,
):
    context.update({"ci_tool": "Gitlab", "use_docker": use_docker})
    result = cookies.bake(extra_context=context)

    assert result.exit_code == 0
    assert result.exception is None
    assert result.project_path.name == context["project_slug"]
    assert result.project_path.is_dir()

    with (result.project_path / ".gitlab-ci.yml").open() as gitlab_yml:
        try:
            gitlab_config = yaml.safe_load(gitlab_yml)
            assert gitlab_config["precommit"]["script"] == [
                "uv run pre-commit run --show-diff-on-failure --color=always --all-files",
            ]
            assert gitlab_config["pytest"]["script"] == [
                expected_typecheck_script,
                expected_test_script,
            ]
        except yaml.YAMLError as e:
            pytest.fail(e)


@pytest.mark.parametrize(
    ("use_docker", "expected_typecheck_script", "expected_test_script"),
    CI_SCRIPT_CASES,
)
def test_github_invokes_linter_mypy_and_pytest(
    cookies,
    context,
    use_docker,
    expected_typecheck_script,
    expected_test_script,
):
    context.update({"ci_tool": "Github", "use_docker": use_docker})
    result = cookies.bake(extra_context=context)

    assert result.exit_code == 0
    assert result.exception is None
    assert result.project_path.name == context["project_slug"]
    assert result.project_path.is_dir()

    with (result.project_path / ".github" / "workflows" / "ci.yml").open() as github_yml:
        try:
            github_config = yaml.safe_load(github_yml)
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
        except yaml.YAMLError as e:
            pytest.fail(e)


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


def test_trim_domain_email(cookies, context):
    """Check that leading and trailing spaces are trimmed in domain and email."""
    context.update(
        {
            "use_docker": "y",
            "domain_name": "   example.com   ",
            "email": "  me@example.com  ",
        },
    )
    result = cookies.bake(extra_context=context)

    assert result.exit_code == 0

    prod_django_env = result.project_path / ".envs" / ".production" / ".django"
    assert "DJANGO_ALLOWED_HOSTS=.example.com" in prod_django_env.read_text()

    base_settings = result.project_path / "config" / "settings" / "base.py"
    assert "<me@example.com>" in base_settings.read_text()


# The generated files that hold a secret drawn on each bake, so two bakes never agree on them.
SECRET_FILES = {
    ".envs/.local/.django",
    ".envs/.local/.postgres",
    ".envs/.production/.django",
    ".envs/.production/.postgres",
    "config/settings/local.py",
    "config/settings/test.py",
}


def project_contents(project_path: Path) -> dict[str, bytes]:
    """Every generated file by its path relative to the project root, with its content."""
    return {str(path.relative_to(project_path)): path.read_bytes() for path in build_files_list(project_path)}


@pytest.mark.parametrize("answer", ["y", "n"])
def test_uppercase_flag_answers_select_the_same_features(cookies, context, answer):
    """Every yes/no answer typed in uppercase generates the project its lowercase spelling does.

    The answers are lowercased before rendering, so every reader sees one spelling: the
    templates (dependencies, settings), the post-generation hook (secrets, ``.gitignore``)
    and pruning. Each is checked on the uppercase project so that the comparison cannot
    pass on two projects that ignored the answers alike.
    """
    answers = dict.fromkeys(FLAG_OPTIONS, answer)
    lowercase = cookies.bake(extra_context={**context, **answers})
    uppercase = cookies.bake(extra_context={**context, **dict.fromkeys(FLAG_OPTIONS, answer.upper())})
    assert lowercase.exit_code == 0
    assert uppercase.exit_code == 0

    expected = project_contents(lowercase.project_path)
    generated = project_contents(uppercase.project_path)
    assert generated.keys() == expected.keys()
    differing = {path for path in expected if generated[path] != expected[path]}
    assert differing <= SECRET_FILES

    project = uppercase.project_path
    selected = answer == "y"
    pinned = {package_name(requirement) for array in pinned_dependencies(project).values() for requirement in array}
    assert ({"celery", "sentry-sdk", "whitenoise"} <= pinned) is selected
    assert ("sentry_sdk" in (project / "config" / "settings" / "production.py").read_text()) is selected
    assert (project / "docker-compose.local.yml").exists() is selected
    assert (project / ".envs").exists() is selected
    assert ("!.envs/.local/" in (project / ".gitignore").read_text()) is selected
    if selected:
        assert "POSTGRES_USER=debug" in (project / ".envs" / ".local" / ".postgres").read_text()


def test_pyproject_toml(cookies, context):
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
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    pyproject_toml = result.project_path / "pyproject.toml"

    data = tomllib.loads(pyproject_toml.read_text())

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


def pinned_dependencies(project_path: Path) -> dict[str, list[str]]:
    """The requirements each array of the generated ``pyproject.toml`` lists."""
    data = tomllib.loads((project_path / "pyproject.toml").read_text())
    return {"dependencies": data["project"]["dependencies"], **data["dependency-groups"]}


def package_name(requirement: str) -> str:
    """The distribution name of a pinned requirement, without its extras."""
    return requirement.split("==", maxsplit=1)[0].split("[", maxsplit=1)[0]


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
def test_pyproject_pins_the_dependencies_of_the_chosen_options(cookies, context_override, expected, unexpected):
    """The dependencies an option needs are pinned in pyproject.toml, and only then."""
    result = cookies.bake(extra_context=context_override)
    assert result.exit_code == 0

    pinned = {
        package_name(requirement)
        for array in pinned_dependencies(result.project_path).values()
        for requirement in array
    }
    assert expected <= pinned
    assert not unexpected & pinned


@pytest.mark.parametrize("context_override", SUPPORTED_COMBINATIONS, ids=_fixture_id)
def test_pyproject_dependencies_are_pinned_and_sorted(cookies, context_override):
    """Every dependency is pinned to one version, and the arrays are in the order pyproject-fmt keeps."""
    result = cookies.bake(extra_context=context_override)
    assert result.exit_code == 0

    arrays = pinned_dependencies(result.project_path)
    assert set(arrays) == {"dependencies", "dev"}
    for name, requirements in arrays.items():
        unpinned = [requirement for requirement in requirements if "==" not in requirement]
        assert not unpinned, f"{name} does not pin {unpinned}"
        expected = sorted(requirements, key=lambda requirement: (package_name(requirement), requirement))
        assert requirements == expected, f"{name} is not sorted"


def test_generation_writes_no_lock_file(cookies, context):
    """Generation resolves nothing: the developer's first ``uv sync`` writes the lock file."""
    result = cookies.bake(extra_context={**context, "use_docker": "y"})
    assert result.exit_code == 0

    assert not (result.project_path / "uv.lock").exists()
    assert not (result.project_path / ".venv").exists()
    assert not (result.project_path / "requirements").exists()
    assert not (result.project_path / "compose" / "local" / "uv").exists()


def test_free_text_answers_survive_escaping(cookies, hostile_context):
    """Each free-text answer reads back unchanged from the generated file it was escaped into."""
    hostile_context.update(
        {
            "use_docker": "y",  # generates the Traefik configuration
            "rest_api": "DRF",  # generates SPECTACULAR_SETTINGS
            "timezone": 'Zone/"Quoted"',  # nothing here starts Django, which would reject it
        },
    )
    result = cookies.bake(extra_context=hostile_context)
    assert result.exit_code == 0
    project_slug = hostile_context["project_slug"]
    project_name = hostile_context["project_name"]
    author_name = hostile_context["author_name"]
    email = hostile_context["email"]

    settings = literal_assignments(result.project_path / "config" / "settings" / "base.py")
    assert settings["TIME_ZONE"] == hostile_context["timezone"]
    assert settings["ADMINS"] == [f'"{author_name}" <{email}>']
    assert settings["SPECTACULAR_SETTINGS"]["TITLE"] == f"{project_name} API"

    sphinx = literal_assignments(result.project_path / "docs" / "conf.py")
    assert sphinx["project"] == project_name
    assert sphinx["author"] == author_name
    assert sphinx["copyright"].endswith(f", {author_name}")

    package = literal_assignments(result.project_path / project_slug / "__init__.py")
    assert package["__version__"] == hostile_context["version"]

    traefik = yaml.safe_load((result.project_path / "compose" / "production" / "traefik" / "traefik.yml").read_text())
    assert traefik["certificatesResolvers"]["letsencrypt"]["acme"]["email"] == email

    base_html = (result.project_path / project_slug / "templates" / "base.html").read_text()
    assert "My &#34;Test&#34; Project\\" in base_html
    assert 'content="She said &#34;hi&#34; &amp; &lt;left&gt; C:\\path, it&#39;s fine."' in base_html
    assert 'content="Tess &#34;Quoted&#34; O&#39;Brien"' in base_html


@pytest.mark.parametrize("rest_api", ["None", "DRF", "Django Ninja"])
def test_strict_typing_setup(cookies, context, rest_api):
    """The generated project is type checked in strict mode with the right plugins and request types."""
    context.update({"rest_api": rest_api})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    pyproject = (result.project_path / "pyproject.toml").read_text()
    assert "strict = true" in pyproject
    assert "mypy_django_plugin.main" in pyproject
    assert ("mypy_drf_plugin.main" in pyproject) is (rest_api == "DRF")
    assert ("runtime-evaluated-decorators" in pyproject) is (rest_api == "Django Ninja")

    typedefs = (result.project_path / context["project_slug"] / "typedefs.py").read_text()
    assert "class AuthenticatedHttpRequest(HttpRequest):" in typedefs
    assert "class AuthenticatedHtmxRequest(" in typedefs
    assert ("class AuthenticatedApiRequest(Request):" in typedefs) is (rest_api == "DRF")


@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_asgi_entrypoint(cookies, context, realtime):
    """Every project is served through ASGI; the Channels wiring is only generated on request."""
    context.update({"realtime": realtime})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    config = result.project_path / "config"
    assert (config / "asgi.py").exists()
    assert not (config / "wsgi.py").exists()
    base_settings = (config / "settings" / "base.py").read_text()
    assert 'ASGI_APPLICATION = "config.asgi.application"' in base_settings
    assert "WSGI_APPLICATION" not in base_settings

    uses_channels = realtime == "channels"
    assert (config / "websocket.py").exists() is uses_channels
    websocket_test = result.project_path / context["project_slug"] / "tests" / "test_websocket.py"
    assert websocket_test.exists() is uses_channels
    assert ('"channels",' in base_settings) is uses_channels
    assert "CHANNEL_LAYERS" not in base_settings
    local_settings = (config / "settings" / "local.py").read_text()
    assert ("InMemoryChannelLayer" in local_settings) is uses_channels
    test_settings = (config / "settings" / "test.py").read_text()
    assert ("InMemoryChannelLayer" in test_settings) is uses_channels
    production_settings = (config / "settings" / "production.py").read_text()
    assert ("channels_redis.core.RedisChannelLayer" in production_settings) is uses_channels
    pyproject = (result.project_path / "pyproject.toml").read_text()
    assert "uvicorn[standard]" in pyproject
    assert "uvicorn-worker" in pyproject
    assert ("channels-redis" in pyproject) is uses_channels
    assert ("types-channels" in pyproject) is uses_channels
    base_html = (result.project_path / context["project_slug"] / "templates" / "base.html").read_text()
    assert ('{% htmx_script extensions="hx-ws" %}' in base_html) is uses_channels
    assert ("{% htmx_script %}" in base_html) is not uses_channels


@pytest.mark.parametrize("use_docker", ["y", "n"])
def test_docker_compose_files_match_use_docker(cookies, context, use_docker):
    """All docker-compose files, including the docs one, are only generated with use_docker=y."""
    context.update({"use_docker": use_docker})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    compose_files = [
        "docker-compose.local.yml",
        "docker-compose.production.yml",
        "docker-compose.docs.yml",
    ]
    for compose_file in compose_files:
        assert (result.project_path / compose_file).exists() is (use_docker == "y")


@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_docker_serves_asgi(cookies, context, realtime):
    """The Docker start scripts run Uvicorn; local development needs no Redis for Channels."""
    context.update({"realtime": realtime, "use_docker": "y"})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    local_start = (result.project_path / "compose" / "local" / "django" / "start").read_text()
    assert "exec uvicorn config.asgi:application" in local_start
    production_start = (result.project_path / "compose" / "production" / "django" / "start").read_text()
    assert "exec gunicorn config.asgi" in production_start
    assert "uvicorn_worker.UvicornWorker" in production_start

    compose = yaml.safe_load((result.project_path / "docker-compose.local.yml").read_text())
    assert "redis" not in compose["services"]
    assert "taskworker" not in compose["services"]


def test_frontend_stack(cookies, context):
    """Generated project uses django-htmx + vendored Pico CSS and has no Node.js/asset pipeline leftovers."""
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    for path in FRONTEND_TOOLCHAIN_PATHS:
        assert not (result.project_path / path).exists(), f"{path} should not be generated"

    offenders = []
    for path in build_files_list(result.project_path):
        if "static/vendor/" in path.as_posix() or is_binary(str(path)):
            continue
        content = path.read_text().lower()
        offenders.extend(f"{path}: {token}" for token in FRONTEND_TOOLCHAIN_TOKENS if token in content)
    assert offenders == []

    settings = (result.project_path / "config" / "settings" / "base.py").read_text()
    assert '"django_htmx",' in settings
    assert '"django_htmx.middleware.HtmxMiddleware",' in settings
    assert "django-htmx==" in (result.project_path / "pyproject.toml").read_text()

    base_html = (result.project_path / "my_test_project" / "templates" / "base.html").read_text()
    assert "{% htmx_script %}" in base_html
    assert 'hx-headers=\'{"X-CSRFToken": "{{ csrf_token }}"}\'' in base_html
    assert "vendor/pico/pico.min.css" in base_html


def test_no_remote_assets(cookies, context):
    """No stylesheet or script is loaded from a CDN or any other remote host."""
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    offenders = [
        path
        for path in build_files_list(result.project_path)
        if path.suffix == ".html" and RE_REMOTE_ASSET.search(path.read_text())
    ]
    assert offenders == []


def test_vendored_pico_intact(cookies, context):
    """The vendored Pico CSS is copied byte-for-byte and matches its recorded checksum."""
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    vendor_dir = result.project_path / "my_test_project" / "static" / "vendor" / "pico"
    metadata = json.loads((vendor_dir / "pico.json").read_text())
    css = (vendor_dir / metadata["file"]).read_bytes()

    assert hashlib.sha256(css).hexdigest() == metadata["sha256"]
    assert f"v{metadata['version']}".encode() in css[:300]
    assert (vendor_dir / "LICENSE.md").read_text().startswith("MIT License")


def test_no_inline_code_in_templates(cookies, context):
    """Templates contain no inline scripts, styles or event handlers, which the CSP would block."""
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    offenders = []
    for path in build_files_list(result.project_path):
        if path.suffix != ".html":
            continue
        match = RE_INLINE_CODE.search(path.read_text())
        if match:
            offenders.append(f"{path}: {match.group(0)}")
    assert offenders == []


def test_template_partials(cookies, context):
    """htmx fragments are Django template partials selected by HtmxTemplateMixin."""
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    templates = result.project_path / context["project_slug"] / "templates"
    assert not (templates / "users" / "partials").exists()
    assert not (templates / "partials" / "messages.html").exists()
    assert "{% partialdef messages inline %}" in (templates / "base.html").read_text()
    for name in ("user_detail.html", "user_form.html"):
        template = (templates / "users" / name).read_text()
        assert "{% partialdef profile inline %}" in template
        assert '{% include "base.html#messages" %}' in template

    views = (result.project_path / context["project_slug"] / "users" / "views.py").read_text()
    assert 'htmx_partial = "profile"' in views
    assert "htmx_template_name" not in views

    # Templates branch on the mixin's context flag, never on the request header: a template
    # that reads the request makes every page including it vary by HX-Request.
    offenders = [
        path
        for path in build_files_list(result.project_path / context["project_slug"] / "templates")
        if path.suffix == ".html" and "request.htmx" in path.read_text()
    ]
    assert offenders == []


@pytest.mark.parametrize("rest_api", ["None", "DRF", "Django Ninja"])
@pytest.mark.parametrize("realtime", ["none", "channels"])
def test_content_security_policy(cookies, context, realtime, rest_api):
    """Every project sends a nonce-based CSP; the websocket and API docs exceptions follow the options."""
    context.update({"realtime": realtime, "rest_api": rest_api})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    settings_dir = result.project_path / "config" / "settings"
    base_settings = (settings_dir / "base.py").read_text()
    assert '"django.middleware.csp.ContentSecurityPolicyMiddleware",' in base_settings
    assert '"django.template.context_processors.csp",' in base_settings
    assert "SECURE_CSP: dict[str, list[str]] = {" in base_settings
    assert "UNSAFE_INLINE" not in base_settings
    assert "UNSAFE_EVAL" not in base_settings
    assert f'"{context["project_slug"]}.htmx.HtmxLoginRedirectMiddleware",' in base_settings
    assert ('"ninja",' in base_settings) is (rest_api == "Django Ninja")

    uses_channels = realtime == "channels"
    assert ('"ws:"' in (settings_dir / "local.py").read_text()) is uses_channels
    production_settings = (settings_dir / "production.py").read_text()
    assert ('"wss:"' in production_settings) is uses_channels
    assert 'env("DJANGO_CSP_REPORT_URI", default=None)' in production_settings
    assert "DJANGO_CSP_REPORT_URI" in (result.project_path / ".envs" / ".production" / ".django").read_text()

    urls = (result.project_path / "config" / "urls.py").read_text()
    assert ("csp_override({})" in urls) is (rest_api == "DRF")

    base_html = (result.project_path / context["project_slug"] / "templates" / "base.html").read_text()
    assert '<meta name="htmx-config"' in base_html
    assert '"allowEval": false' in base_html
    assert '"includeIndicatorStyles": false' in base_html


@pytest.mark.parametrize("use_celery", ["n", "y"])
def test_tasks_framework(cookies, context, use_celery):
    """Django's Tasks framework is configured in every project; Celery stays an opt-in extra."""
    context.update({"use_celery": use_celery, "use_docker": "y"})
    result = cookies.bake(extra_context=context)
    assert result.exit_code == 0

    celery = use_celery == "y"
    assert "django-tasks-db==" in (result.project_path / "pyproject.toml").read_text()
    settings_dir = result.project_path / "config" / "settings"
    assert '"django_tasks_db",' in (settings_dir / "base.py").read_text()
    immediate = 'TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}'
    assert immediate in (settings_dir / "local.py").read_text()
    assert immediate in (settings_dir / "test.py").read_text()
    database = 'TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}'
    assert database in (settings_dir / "production.py").read_text()

    users = result.project_path / context["project_slug"] / "users"
    tasks = (users / "tasks.py").read_text()
    assert "from django.tasks import task" in tasks
    assert ("shared_task" in tasks) is celery
    tests = (users / "tests" / "test_tasks.py").read_text()
    assert "TaskResultStatus.SUCCESSFUL" in tests
    assert ("EagerResult" in tests) is celery
    assert (result.project_path / "config" / "celery_app.py").exists() is celery

    production_compose = yaml.safe_load((result.project_path / "docker-compose.production.yml").read_text())
    assert production_compose["services"]["taskworker"]["command"] == "/start-taskworker"
    assert ("celeryworker" in production_compose["services"]) is celery
    local_compose = yaml.safe_load((result.project_path / "docker-compose.local.yml").read_text())
    assert "taskworker" not in local_compose["services"]
    django_compose = result.project_path / "compose" / "production" / "django"
    assert "db_worker" in (django_compose / "tasks" / "worker" / "start").read_text()
    assert "/start-taskworker" in (django_compose / "Dockerfile").read_text()
