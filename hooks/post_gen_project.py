import json
import random
import shutil
import string
from pathlib import Path

try:
    # Inspired by
    # https://github.com/django/django/blob/main/django/utils/crypto.py
    random = random.SystemRandom()
    using_sysrandom = True
except NotImplementedError:
    using_sysrandom = False

TERMINATOR = "\x1b[0m"
WARNING = "\x1b[1;33m [WARNING]: "
INFO = "\x1b[1;33m [INFO]: "
HINT = "\x1b[3;33m"
SUCCESS = "\x1b[1;32m [SUCCESS]: "

DEBUG_VALUE = "debug"

# The yes/no answers this hook reads. Cookiecutter validates list-typed options
# against their choices, so only these free-text answers need normalising.
FLAG_OPTIONS = (
    "debug",
    "keep_local_envs_in_vcs",
    "use_celery",
    "use_docker",
)


def normalize_context(context):
    """Return a copy of ``context`` with the yes/no answers lowercased."""
    normalized = dict(context)
    for option in FLAG_OPTIONS:
        if option in normalized:
            normalized[option] = normalized[option].lower()
    return normalized


# Removal rules. When a rule's condition holds for the normalised answers, the paths
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
    # Docker Compose is the only consumer of the ``.envs`` files.
    (
        lambda c: c["use_docker"] == "n" and c["keep_local_envs_in_vcs"] == "n",
        (".envs", "merge_production_dotenvs_in_dotenv.py", "tests"),
    ),
    # users/tasks.py and its tests stay: they also hold the Django Tasks example.
    (lambda c: c["use_celery"] == "n", ("config/celery_app.py",)),
    (
        lambda c: c["use_celery"] == "n" and c["use_docker"] == "y",
        ("compose/local/django/celery", "compose/production/django/celery"),
    ),
    (lambda c: c["ci_tool"] != "Gitlab", (".gitlab-ci.yml",)),
    (lambda c: c["ci_tool"] != "Github", (".github",)),
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
)


def generate_random_string(length, using_digits=False, using_ascii_letters=False, using_punctuation=False):  # noqa: FBT002
    """
    Example:
        opting out for 50 symbol-long, [a-z][A-Z][0-9] string
        would yield log_2((26+26+50)^50) ~= 334 bit strength.
    """
    if not using_sysrandom:
        return None

    symbols = []
    if using_digits:
        symbols += string.digits
    if using_ascii_letters:
        symbols += string.ascii_letters
    if using_punctuation:
        all_punctuation = set(string.punctuation)
        # These symbols can cause issues in environment variables
        unsuitable = {"'", '"', "\\", "$"}
        suitable = all_punctuation.difference(unsuitable)
        symbols += "".join(suitable)
    return "".join([random.choice(symbols) for _ in range(length)])


def set_flag(file_path: Path, flag, value=None, formatted=None, *args, **kwargs):
    if value is None:
        random_string = generate_random_string(*args, **kwargs)
        if random_string is None:
            print(
                "We couldn't find a secure pseudo-random number generator on your "
                f"system. Please, make sure to manually {flag} later.",
            )
            random_string = flag
        if formatted is not None:
            random_string = formatted.format(random_string)
        value = random_string

    with file_path.open("r+") as f:
        file_contents = f.read().replace(flag, value)
        f.seek(0)
        f.write(file_contents)
        f.truncate()

    return value


def set_django_secret_key(file_path: Path):
    return set_flag(
        file_path,
        "!!!SET DJANGO_SECRET_KEY!!!",
        length=64,
        using_digits=True,
        using_ascii_letters=True,
    )


def set_django_admin_url(file_path: Path):
    return set_flag(
        file_path,
        "!!!SET DJANGO_ADMIN_URL!!!",
        formatted="{}/",
        length=32,
        using_digits=True,
        using_ascii_letters=True,
    )


def generate_random_user():
    return generate_random_string(length=32, using_ascii_letters=True)


def generate_postgres_user(debug=False):  # noqa: FBT002
    return DEBUG_VALUE if debug else generate_random_user()


def set_postgres_user(file_path, value):
    return set_flag(file_path, "!!!SET POSTGRES_USER!!!", value=value)


def set_postgres_password(file_path, value=None):
    return set_flag(
        file_path,
        "!!!SET POSTGRES_PASSWORD!!!",
        value=value,
        length=64,
        using_digits=True,
        using_ascii_letters=True,
    )


def set_celery_flower_user(file_path, value):
    return set_flag(file_path, "!!!SET CELERY_FLOWER_USER!!!", value=value)


def set_celery_flower_password(file_path, value=None):
    return set_flag(
        file_path,
        "!!!SET CELERY_FLOWER_PASSWORD!!!",
        value=value,
        length=64,
        using_digits=True,
        using_ascii_letters=True,
    )


def append_to_gitignore_file(ignored_line):
    with Path(".gitignore").open("a") as gitignore_file:
        gitignore_file.write(ignored_line)
        gitignore_file.write("\n")


def set_flags_in_envs(postgres_user, celery_flower_user, debug=False):  # noqa: FBT002
    local_django_envs_path = Path(".envs", ".local", ".django")
    production_django_envs_path = Path(".envs", ".production", ".django")
    local_postgres_envs_path = Path(".envs", ".local", ".postgres")
    production_postgres_envs_path = Path(".envs", ".production", ".postgres")

    set_django_secret_key(production_django_envs_path)
    set_django_admin_url(production_django_envs_path)

    set_postgres_user(local_postgres_envs_path, value=postgres_user)
    set_postgres_password(local_postgres_envs_path, value=DEBUG_VALUE if debug else None)
    set_postgres_user(production_postgres_envs_path, value=postgres_user)
    set_postgres_password(production_postgres_envs_path, value=DEBUG_VALUE if debug else None)

    set_celery_flower_user(local_django_envs_path, value=celery_flower_user)
    set_celery_flower_password(local_django_envs_path, value=DEBUG_VALUE if debug else None)
    set_celery_flower_user(production_django_envs_path, value=celery_flower_user)
    set_celery_flower_password(production_django_envs_path, value=DEBUG_VALUE if debug else None)


def set_flags_in_settings_files():
    set_django_secret_key(Path("config", "settings", "local.py"))
    set_django_secret_key(Path("config", "settings", "test.py"))


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
    """Remove the files the chosen options do not need from the project at ``root``."""
    context = normalize_context(context)
    project_slug = context["project_slug"]
    for applies, paths in REMOVALS:
        if applies(context):
            for path in paths:
                remove(root / path.format(project_slug=project_slug))
    if context["realtime"] != "channels":
        remove_channels_tests(root, project_slug)


def main(context):
    context = normalize_context(context)
    debug = context["debug"] == "y"

    set_flags_in_envs(
        DEBUG_VALUE if debug else generate_random_user(),
        DEBUG_VALUE if debug else generate_random_user(),
        debug=debug,
    )
    set_flags_in_settings_files()

    if context["use_docker"] == "n":
        if context["keep_local_envs_in_vcs"] == "y":
            print(
                INFO + ".env(s) are only utilized when Docker Compose is enabled. "
                "Keeping them as requested, but they may not be useful "
                "in your current setup." + TERMINATOR,
            )
    else:
        append_to_gitignore_file(".env")
        append_to_gitignore_file(".envs/*")
        if context["keep_local_envs_in_vcs"] == "y":
            append_to_gitignore_file("!.envs/.local/")

    if context["cloud_provider"] == "None" and context["use_docker"] == "n":
        print(
            WARNING + "You chose to not use any cloud providers nor Docker, "
            "media files won't be served in production." + TERMINATOR,
        )

    prune(context, Path.cwd())

    print(SUCCESS + "Project initialized, keep up the good work!" + TERMINATOR)


if __name__ == "__main__":
    # Cookiecutter renders this file through Jinja before running it. The answers
    # enter here and nowhere else, as JSON so that free-text answers cannot break
    # the source, and the unrendered module stays importable for the tests.
    main(json.loads(r"""{{ cookiecutter | tojson }}"""))
