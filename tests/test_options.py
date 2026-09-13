"""The option catalogue in local_extensions.py: what it reads from cookiecutter.json, and who reads it."""

import json
import shlex
from pathlib import Path

import yaml
from cookiecutter.environment import StrictEnvironment

from local_extensions import FLAG
from local_extensions import FREE_TEXT
from local_extensions import LIST
from local_extensions import OPTIONS
from local_extensions import option_names

REPO = Path(__file__).resolve().parent.parent

# Every option with the kind its declaration shows, written by hand: a declaration that changes
# kind, say a free-text default that reads "y", fails here rather than silently becoming a flag.
KINDS = {
    "project_name": FREE_TEXT,
    "project_slug": FREE_TEXT,
    "description": FREE_TEXT,
    "author_name": FREE_TEXT,
    "domain_name": FREE_TEXT,
    "email": FREE_TEXT,
    "version": FREE_TEXT,
    "open_source_license": LIST,
    "username_type": LIST,
    "timezone": FREE_TEXT,
    "use_docker": FLAG,
    "postgresql_version": LIST,
    "cloud_provider": LIST,
    "mail_service": LIST,
    "rest_api": LIST,
    "realtime": LIST,
    "use_celery": FLAG,
    "mail_catcher": LIST,
    "use_sentry": FLAG,
    "use_whitenoise": FLAG,
    "ci_tool": LIST,
    "keep_local_envs_in_vcs": FLAG,
    "debug": FLAG,
}


def test_every_option_has_the_kind_its_declaration_shows():
    assert {name: option.kind for name, option in OPTIONS.items()} == KINDS


def test_choices_and_defaults_follow_the_declaration():
    assert OPTIONS["cloud_provider"].choices == ("AWS", "None")
    assert OPTIONS["cloud_provider"].default == "AWS"
    assert OPTIONS["use_docker"].choices == ("y", "n")
    assert OPTIONS["use_docker"].default == "n"
    assert OPTIONS["timezone"].choices == ()
    assert OPTIONS["timezone"].default == "UTC"
    assert OPTIONS["project_slug"].default.startswith("{{ cookiecutter.project_name")


def test_option_names_partition_the_catalogue_by_kind():
    by_kind = {kind: option_names(kind) for kind in (LIST, FLAG, FREE_TEXT)}
    assert by_kind[FLAG] == (
        "use_docker",
        "use_celery",
        "use_sentry",
        "use_whitenoise",
        "keep_local_envs_in_vcs",
        "debug",
    )
    assert sorted(name for names in by_kind.values() for name in names) == sorted(OPTIONS)


def test_cookiecutter_exposes_option_names_to_the_templates_and_hooks():
    """The hooks run as standalone scripts and cannot import the catalogue; this global reaches them."""
    declarations = json.loads((REPO / "cookiecutter.json").read_text())
    env = StrictEnvironment(context={"cookiecutter": declarations})

    rendered = env.from_string('{{ option_names("flag") | tojson }}').render()

    assert json.loads(rendered) == list(option_names(FLAG))


def ci_integration_answers():
    """The answers each Docker and bare-metal CI job passes to cookiecutter, by job."""
    workflow = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    for job in ("docker", "bare"):
        for script in workflow["jobs"][job]["strategy"]["matrix"]["script"]:
            answers = {}
            for token in shlex.split(script["args"]):
                assert "=" in token, f"{job} {script['name']}: {token!r} is not name=value"
                name, value = token.split("=", 1)
                answers[name] = value
            yield f"{job} {script['name']}", answers


def test_ci_integration_jobs_pass_options_of_the_catalogue():
    """A misspelt option in ci.yml would bake the default project and pass."""
    for job, answers in ci_integration_answers():
        for name, value in answers.items():
            assert name in OPTIONS, f"{job}: {name!r} is not an option"
            if OPTIONS[name].choices:
                assert value in OPTIONS[name].choices, f"{job}: {value!r} is not a choice of {name}"
