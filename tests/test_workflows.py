"""The repository's own workflows against the files they read."""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
AUTOUPDATE = REPO / ".github" / "workflows" / "pre-commit-autoupdate.yml"


def autoupdate_directories():
    """The directories the auto-update workflow runs ``pre-commit autoupdate`` in."""
    workflow = yaml.safe_load(AUTOUPDATE.read_text())
    steps = workflow["jobs"]["auto-update"]["steps"]
    return [step.get("working-directory", ".") for step in steps if "pre-commit autoupdate" in step.get("run", "")]


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
