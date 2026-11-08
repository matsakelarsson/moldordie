"""What ``scripts/python_dependency_version.py`` writes, on hand-written files."""

import tomllib
from types import SimpleNamespace

import pytest
import yaml

from scripts import python_dependency_version as script

CONFIG = """\
repos:
  - repo: https://github.com/tox-dev/pyproject-fmt
    rev: v2.0.0
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v1.0.0
"""


def pyproject(*dependencies):
    """A ``pyproject.toml`` that pins ``dependencies``."""
    lines = "".join(f'  "{dependency}",\n' for dependency in dependencies)
    return f"[project]\ndependencies = [\n{lines}]\n"


def pins(path):
    """The dependencies a ``pyproject.toml`` lists."""
    return tomllib.loads(path.read_text())["project"]["dependencies"]


def hook_revs(path):
    """The rev of each hook repository in a pre-commit configuration."""
    return {hook["repo"].rsplit("/", 1)[1]: hook["rev"] for hook in yaml.safe_load(path.read_text())["repos"]}


@pytest.fixture
def files(tmp_path, monkeypatch):
    """The files the script reads and writes, and the commands it runs. The hooks are at
    pyproject-fmt 2.0.0 and ruff 1.0.0, the generated project pins ruff 3.0.0, and this
    repository pins pyproject-fmt 1.0.0 and ruff 1.0.0."""
    written = SimpleNamespace(
        pyproject=tmp_path / "pyproject.toml",
        generated_pyproject=tmp_path / "generated-pyproject.toml",
        config=tmp_path / "pre-commit-config.yaml",
        generated_config=tmp_path / "generated-pre-commit-config.yaml",
        commands=[],
    )
    written.pyproject.write_text(pyproject("pyproject-fmt==1.0.0", "ruff==1.0.0"))
    written.generated_pyproject.write_text(pyproject("ruff==3.0.0"))
    written.config.write_text(CONFIG)
    written.generated_config.write_text(CONFIG)

    monkeypatch.setattr(script, "PYPROJECT_TOML", written.pyproject)
    monkeypatch.setattr(script, "TEMPLATE_PYPROJECT_TOML", written.generated_pyproject)
    monkeypatch.setattr(script, "TEMPLATE_PRE_COMMIT_CONFIG", written.config)
    monkeypatch.setattr(script, "PRE_COMMIT_CONFIG", written.generated_config)
    monkeypatch.setattr(
        script.subprocess,
        "run",
        lambda command, **kwargs: written.commands.append((command, kwargs["check"])),
    )
    return written


def test_a_tool_only_the_hook_runs_is_pinned_at_the_hooks_rev(files):
    """The generated project does not pin it, so the pin follows the rev, and a lock that
    cannot be refreshed stops the run instead of leaving a stale ``uv.lock``."""
    script.main("pyproject-fmt")

    assert pins(files.pyproject) == ["pyproject-fmt==2.0.0", "ruff==1.0.0"]
    assert hook_revs(files.generated_config)["pyproject-fmt"] == "v2.0.0"
    assert files.commands == [(["uv", "lock", "--no-upgrade"], True)]


def test_a_tool_already_at_the_hooks_rev_is_left_alone(files):
    files.pyproject.write_text(pyproject("pyproject-fmt==2.0.0", "ruff==1.0.0"))

    script.main("pyproject-fmt")

    assert pins(files.pyproject) == ["pyproject-fmt==2.0.0", "ruff==1.0.0"]
    assert files.commands == []


def test_a_hook_that_is_gone_stops_the_run(files):
    files.generated_config.write_text("repos: []\n")

    with pytest.raises(RuntimeError, match="pyproject-fmt"):
        script.main("pyproject-fmt")

    assert pins(files.pyproject) == ["pyproject-fmt==1.0.0", "ruff==1.0.0"]
    assert files.commands == []


def test_a_tool_the_generated_project_pins_follows_that_pin(files):
    """The hook is written from the generated project's pin here, the other way round."""
    script.main("ruff")

    assert pins(files.pyproject) == ["pyproject-fmt==1.0.0", "ruff==3.0.0"]
    assert hook_revs(files.config)["ruff-pre-commit"] == "v3.0.0"
    assert hook_revs(files.generated_config)["ruff-pre-commit"] == "v3.0.0"
