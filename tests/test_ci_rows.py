"""The projects the CI integration jobs generate: the rows of ``.github/workflows/ci.yml``
completed with the answers each integration script passes to Cookiecutter itself, checked
against the catalogue and held to the removal rules (docs/adr/0021)."""

import re
import shlex
from collections.abc import Iterator
from pathlib import Path

import yaml

from hooks.post_gen_project import REMOVALS
from tests.answers import complete_answers
from tests.answers import parse_answers
from tests.answers import unknown_answers
from tests.removal_coverage import coverage_gaps
from tests.removal_coverage import paths_kept

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
# The jobs that run an integration script, each on a matrix of rows
INTEGRATION_JOBS = ("docker", "bare")


def integration_script(job: dict) -> Path:
    """The script ``job`` runs its rows through, read from the step that runs it."""
    [run] = [step["run"] for step in job["steps"] if step.get("run", "").startswith("sh tests/")]
    return REPO / run.split()[1]


def script_answers(script: Path) -> dict[str, str]:
    """The answers ``script`` passes to Cookiecutter itself: the ``name=value`` words of the
    command that also takes the row's, which it spells ``"$@"``."""
    [command] = [line for line in script.read_text().splitlines() if "cookiecutter" in line and '"$@"' in line]
    return parse_answers(shlex.join(word for word in shlex.split(command) if re.fullmatch(r"\w+=.*", word)))


def ci_integration_rows() -> Iterator[tuple[str, dict[str, str], dict[str, str]]]:
    """Every row of the integration jobs: its name, the answers its script passes, its own."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    for name in INTEGRATION_JOBS:
        job = workflow["jobs"][name]
        own = script_answers(integration_script(job))
        for row in job["strategy"]["matrix"]["script"]:
            yield f"{name} {row['name']}", own, parse_answers(row["args"])


def test_the_integration_scripts_pass_their_own_answer_to_use_docker():
    """The rows never say whether they use Docker: the script they run under does."""
    assert script_answers(REPO / "tests" / "test_docker.sh") == {"use_docker": "y"}
    assert script_answers(REPO / "tests" / "test_bare.sh") == {"use_docker": "n"}


def test_ci_integration_jobs_pass_options_of_the_catalogue():
    """A misspelt option in ci.yml, or in a script's own answers, would bake the default project and pass.

    The script's answers are checked on their own, so a row cannot hide a misspelling by
    answering the same option.
    """
    for name, own, row in ci_integration_rows():
        assert unknown_answers(own) == [], name
        assert unknown_answers(row) == [], name


# The removable paths no CI integration row has to keep, each with the reason: what the
# integration scripts run reads none of these. An exemption that a row makes unnecessary fails
# below, so the list cannot outlive its reasons.
CI_EXEMPTIONS = {
    "COPYING": "the GPL's text: no check of the integration scripts reads a licence",
    "AGENTS.md": "the agent guide is prose for a coding agent; the generation tests check its tables against the tree",
}


def test_every_removable_path_is_generated_by_some_ci_row():
    """The integration scripts' checks run only on what some CI row generates. A row that is
    replaced or narrowed fails here when it was the only one keeping a path the removal rules
    list, instead of passing silently (docs/adr/0021).

    What a row reaching a path shows is narrow: its script's checks ran on a project that has
    it. It needs no bake: the rules are evaluated on the rows' complete answers, the defaults,
    then the script's answers, then the row's, which is what Cookiecutter generates from.
    """
    kept = paths_kept(REMOVALS, [complete_answers(own, row) for _, own, row in ci_integration_rows()])

    gaps, stale = coverage_gaps(kept, CI_EXEMPTIONS)

    assert not gaps, f"no CI integration row generates {gaps}: add the answers to a row of ci.yml, or exempt the path"
    assert not stale, f"exempted from CI coverage without need, a row keeps it or no rule lists it: {stale}"
