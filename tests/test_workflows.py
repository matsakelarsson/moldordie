"""The repository's own workflows against the files they read."""

import re
from pathlib import Path

import pytest
import yaml

from scripts.python_dependency_version import PRE_COMMIT_REPOS

REPO = Path(__file__).resolve().parent.parent
AUTOUPDATE = REPO / ".github" / "workflows" / "pre-commit-autoupdate.yml"


def autoupdate_steps():
    """The steps of the auto-update workflow, in order."""
    return yaml.safe_load(AUTOUPDATE.read_text())["jobs"]["auto-update"]["steps"]


def autoupdate_directories():
    """The directories the auto-update workflow runs ``pre-commit autoupdate`` in."""
    return [step.get("working-directory", ".") for step in autoupdate_steps() if is_autoupdate(step)]


def is_autoupdate(step):
    """Whether the step runs ``pre-commit autoupdate``."""
    return "pre-commit autoupdate" in step.get("run", "")


def test_the_workflow_updates_the_template_and_the_generated_project():
    """Both configurations are updated; without this, the parse test below could cover nothing."""
    assert autoupdate_directories() == [".", "{{cookiecutter.project_slug}}"]


@pytest.mark.parametrize("directory", autoupdate_directories())
def test_autoupdate_can_parse_the_config_it_updates(directory):
    """``pre-commit`` reads the file as it stands, so the one under the template has to be YAML
    before Cookiecutter renders it: bare ``{%`` there ends the daily run with an InvalidConfigError.
    """
    config = yaml.safe_load((REPO / directory / ".pre-commit-config.yaml").read_text())

    assert config["repos"]


def test_the_workflow_moves_the_pin_of_each_tool_it_updates():
    """A hook the workflow bumps whose tool this repository pins moves that pin in the same run,
    after the bump and before the pull request opens. Otherwise the next update breaks
    ``test_auto_fixable_checks_run_the_versions_the_generated_hooks_pin``.
    """
    steps = autoupdate_steps()
    runs = [step.get("run", "") for step in steps]
    updated = set(re.findall(r"--repo (\S+)", "\n".join(runs)))
    tools = [tool for tool, repo in PRE_COMMIT_REPOS.items() if repo in updated]
    last_bump = max(index for index, step in enumerate(steps) if is_autoupdate(step))
    pull_request = next(index for index, step in enumerate(steps) if "create-pull-request" in step.get("uses", ""))

    assert tools
    for tool in tools:
        assert last_bump < runs.index(f"uv run scripts/python_dependency_version.py {tool}") < pull_request
