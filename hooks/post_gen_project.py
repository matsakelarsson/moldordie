import json
import os
import random
import shutil
import string
import subprocess
import sys
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
    "use_heroku",
)


def normalize_context(context):
    """Return a copy of ``context`` with the yes/no answers lowercased."""
    normalized = dict(context)
    for option in FLAG_OPTIONS:
        if option in normalized:
            normalized[option] = normalized[option].lower()
    return normalized


def envs_unused(context):
    """Docker Compose and Heroku are the only consumers of the ``.envs`` files."""
    return context["use_docker"] == "n" and context["use_heroku"] == "n"


def remove_open_source_files(root):
    file_names = ["CONTRIBUTORS.txt", "LICENSE"]
    for file_name in file_names:
        (root / file_name).unlink()


def remove_gplv3_files(root):
    (root / "COPYING").unlink()


def remove_custom_user_manager_files(root, project_slug):
    users_path = root / project_slug / "users"
    (users_path / "managers.py").unlink()
    (users_path / "tests" / "test_managers.py").unlink()


def remove_docker_files(root):
    shutil.rmtree(root / "compose")

    file_names = [
        "docker-compose.local.yml",
        "docker-compose.production.yml",
        "docker-compose.docs.yml",
        ".dockerignore",
        "justfile",
    ]
    for file_name in file_names:
        (root / file_name).unlink()


def remove_nginx_docker_files(root):
    shutil.rmtree(root / "compose" / "production" / "nginx")


def remove_utility_files(root):
    shutil.rmtree(root / "utility")


def remove_heroku_files(root):
    (root / "Procfile").unlink()
    shutil.rmtree(root / "bin")


def remove_celery_files(root):
    # users/tasks.py and its tests stay: they also hold the Django Tasks example
    (root / "config" / "celery_app.py").unlink()


def remove_channels_files(root, project_slug):
    (root / "config" / "websocket.py").unlink()
    tests_path = root / project_slug / "tests"
    (tests_path / "test_websocket.py").unlink()
    # Keep the package when it holds tests that are not tied to Channels.
    if all(path.name == "__init__.py" for path in tests_path.iterdir()):
        shutil.rmtree(tests_path)


def remove_dottravisyml_file(root):
    (root / ".travis.yml").unlink()


def remove_dotgitlabciyml_file(root):
    (root / ".gitlab-ci.yml").unlink()


def remove_dotgithub_folder(root):
    shutil.rmtree(root / ".github")


def remove_dotdrone_file(root):
    (root / ".drone.yml").unlink()


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


def remove_envs_and_associated_files(root):
    shutil.rmtree(root / ".envs")
    (root / "merge_production_dotenvs_in_dotenv.py").unlink()
    shutil.rmtree(root / "tests")


def remove_celery_compose_dirs(root):
    shutil.rmtree(root / "compose" / "local" / "django" / "celery")
    shutil.rmtree(root / "compose" / "production" / "django" / "celery")


def remove_aws_dockerfile(root):
    shutil.rmtree(root / "compose" / "production" / "aws")


def remove_drf_starter_files(root, project_slug):
    (root / "config" / "api_router.py").unlink()
    (root / project_slug / "users" / "api" / "serializers.py").unlink()


def remove_ninja_starter_files(root, project_slug):
    (root / "config" / "api.py").unlink()
    (root / project_slug / "users" / "api" / "schema.py").unlink()


def remove_rest_api_files(root, project_slug):
    remove_drf_starter_files(root, project_slug)
    remove_ninja_starter_files(root, project_slug)
    shutil.rmtree(root / project_slug / "users" / "api")
    shutil.rmtree(root / project_slug / "users" / "tests" / "api")


def prune(context, root):  # noqa: C901, PLR0912
    """Remove the files the chosen options do not need from the project at ``root``."""
    context = normalize_context(context)
    project_slug = context["project_slug"]

    if context["open_source_license"] == "Not open source":
        remove_open_source_files(root)
    if context["open_source_license"] != "GPLv3":
        remove_gplv3_files(root)

    if context["username_type"] == "username":
        remove_custom_user_manager_files(root, project_slug)

    if context["use_docker"] == "y":
        remove_utility_files(root)
        if context["cloud_provider"] != "None":
            remove_nginx_docker_files(root)
    else:
        remove_docker_files(root)

    if context["use_docker"] == "y" and context["cloud_provider"] != "AWS":
        remove_aws_dockerfile(root)

    if context["use_heroku"] == "n":
        remove_heroku_files(root)

    if envs_unused(context) and context["keep_local_envs_in_vcs"] == "n":
        remove_envs_and_associated_files(root)

    if context["use_celery"] == "n":
        remove_celery_files(root)
        if context["use_docker"] == "y":
            remove_celery_compose_dirs(root)

    if context["ci_tool"] != "Travis":
        remove_dottravisyml_file(root)

    if context["ci_tool"] != "Gitlab":
        remove_dotgitlabciyml_file(root)

    if context["ci_tool"] != "Github":
        remove_dotgithub_folder(root)

    if context["ci_tool"] != "Drone":
        remove_dotdrone_file(root)

    if context["rest_api"] == "DRF":
        remove_ninja_starter_files(root, project_slug)
    elif context["rest_api"] == "Django Ninja":
        remove_drf_starter_files(root, project_slug)
    else:
        remove_rest_api_files(root, project_slug)

    if context["realtime"] != "channels":
        remove_channels_files(root, project_slug)


def main(context):
    context = normalize_context(context)
    debug = context["debug"] == "y"

    set_flags_in_envs(
        DEBUG_VALUE if debug else generate_random_user(),
        DEBUG_VALUE if debug else generate_random_user(),
        debug=debug,
    )
    set_flags_in_settings_files()

    if envs_unused(context):
        if context["keep_local_envs_in_vcs"] == "y":
            print(
                INFO + ".env(s) are only utilized when Docker Compose and/or "
                "Heroku support is enabled. Keeping them as requested, but they may not be useful "
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

    setup_dependencies(use_docker=context["use_docker"] == "y")

    print(SUCCESS + "Project initialized, keep up the good work!" + TERMINATOR)


def setup_dependencies(*, use_docker):
    print("Installing python dependencies using uv...")

    if use_docker:
        # Build a trimmed down Docker image add dependencies with uv
        uv_docker_image_path = Path("compose/local/uv/Dockerfile")
        uv_image_tag = "moldordie-uv-runner:latest"
        try:
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "docker",
                    "build",
                    "--load",
                    "-t",
                    uv_image_tag,
                    "-f",
                    str(uv_docker_image_path),
                    "-q",
                    ".",
                ],
                check=True,
                env={
                    **os.environ,
                    "DOCKER_BUILDKIT": "1",
                },
            )
        except subprocess.CalledProcessError as e:
            print(f"Error building Docker image: {e}", file=sys.stderr)
            sys.exit(1)

        current_path = Path.cwd().absolute()
        # Use Docker to run the uv command
        uv_cmd = ["docker", "run", "--rm", "-v", f"{current_path}:/app", uv_image_tag, "uv"]
    else:
        # Use uv command directly
        uv_cmd = ["uv"]

    # Install production dependencies
    try:
        subprocess.run([*uv_cmd, "add", "--no-sync", "-r", "requirements/production.txt"], check=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        print(f"Error installing production dependencies: {e}", file=sys.stderr)
        sys.exit(1)

    # Install local (development) dependencies
    try:
        subprocess.run([*uv_cmd, "add", "--no-sync", "--dev", "-r", "requirements/local.txt"], check=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        print(f"Error installing local dependencies: {e}", file=sys.stderr)
        sys.exit(1)

    # Remove the requirements directory
    requirements_dir = Path("requirements")
    if requirements_dir.exists():
        try:
            shutil.rmtree(requirements_dir)
        except Exception as e:  # noqa: BLE001
            print(f"Error removing 'requirements' folder: {e}", file=sys.stderr)
            sys.exit(1)

    uv_image_parent_dir_path = Path("compose/local/uv")
    if uv_image_parent_dir_path.exists():
        shutil.rmtree(str(uv_image_parent_dir_path))

    print("Setup complete!")


if __name__ == "__main__":
    # Cookiecutter renders this file through Jinja before running it. The answers
    # enter here and nowhere else, as JSON so that free-text answers cannot break
    # the source, and the unrendered module stays importable for the tests.
    main(json.loads(r"""{{ cookiecutter | tojson }}"""))
