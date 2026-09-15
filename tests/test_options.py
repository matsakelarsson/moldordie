"""The option catalogue in local_extensions.py: what it reads from cookiecutter.json, and who reads it."""

import json
import re
import shlex
from dataclasses import dataclass
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
    "identity_provider": LIST,
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


@dataclass(frozen=True)
class Prompt:
    """One prompt of the README's example session, as Cookiecutter shows it."""

    index: int
    total: int
    name: str
    choices: tuple[str, ...]
    """The numbered choices of a list option; empty otherwise."""
    default: str
    """The default in parentheses, or for a list option the choice its default number selects."""


def readme_transcript():
    """The prompts of the README's example session, in order."""
    lines = (REPO / "README.md").read_text().splitlines()
    prompts = []
    at = 0
    while at < len(lines):
        header = re.fullmatch(r"\s+\[(\d+)/(\d+)\] (?:Select (\w+)|(\w+) \((.*)\): .*)", lines[at])
        at += 1
        if header is None:
            continue
        index, total, list_name, name, default = header.groups()
        if list_name is None:
            prompts.append(Prompt(int(index), int(total), name, (), default))
            continue
        choices = []
        while (choice := re.fullmatch(r"\s+(\d+) - (.*)", lines[at])) is not None:
            assert int(choice.group(1)) == len(choices) + 1, f"{list_name}: {lines[at]!r} is out of sequence"
            choices.append(choice.group(2))
            at += 1
        chosen = re.fullmatch(r"\s+Choose from \[([\d/]+)\] \((\d+)\): \d+", lines[at])
        assert chosen is not None, f"{list_name}: {lines[at]!r} should offer the choices"
        assert chosen.group(1) == "/".join(str(n) for n in range(1, len(choices) + 1)), list_name
        prompts.append(Prompt(int(index), int(total), list_name, tuple(choices), choices[int(chosen.group(2)) - 1]))
        at += 1
    return prompts


def test_readme_transcript_prompts_every_option_as_cookiecutter_does():
    """The example session shows every option in declaration order, with its choices and default."""
    prompts = readme_transcript()

    assert [prompt.name for prompt in prompts] == list(OPTIONS)
    assert [prompt.index for prompt in prompts] == list(range(1, len(OPTIONS) + 1))
    assert {prompt.total for prompt in prompts} == {len(OPTIONS)}
    for prompt in prompts:
        option = OPTIONS[prompt.name]
        assert prompt.choices == (option.choices if option.kind == LIST else ()), prompt.name
        if "{{" not in option.default:  # a default rendered from earlier answers cannot be compared
            assert prompt.default == option.default, prompt.name


def documented_options():
    """The entries of the options page's definition list: name to the lines of its body, in order."""
    entries = {}
    current = None
    for line in (REPO / "docs" / "1-getting-started" / "project-generation-options.rst").read_text().splitlines():
        term = re.fullmatch(r"(\w+):", line)
        if term is not None:
            current = term.group(1)
            entries[current] = []
        elif current is not None and line.startswith("    "):
            entries[current].append(line.strip())
        elif line.strip():
            current = None  # the link targets after the list
    return entries


def test_options_page_documents_every_option_in_order():
    assert list(documented_options()) == list(OPTIONS)


def test_options_page_lists_the_choices_of_every_list_option():
    """Each list option's entry enumerates its choices, every item starting with the answer as typed."""
    documented = documented_options()
    for name in option_names(LIST):
        items = [match for line in documented[name] if (match := re.fullmatch(r"(\d+)\. (.*)", line))]
        choices = OPTIONS[name].choices
        assert [int(item.group(1)) for item in items] == list(range(1, len(choices) + 1)), name
        for item, choice in zip(items, choices, strict=True):
            text = item.group(2).replace("`", "")  # rst link and literal markup
            assert re.match(rf"{re.escape(choice)}(?:[_,:\s]|$)", text), f"{name}: {item.group(0)!r} is not {choice!r}"
