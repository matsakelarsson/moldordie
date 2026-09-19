"""What the examples page shows: its sources, its sample tasks and its tabs."""

import pytest

from {{ cookiecutter.project_slug }}.examples.content import HTMX_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import STATIC_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import TABS
from {{ cookiecutter.project_slug }}.examples.content import TASKS
from {{ cookiecutter.project_slug }}.examples.content import matching_tasks
from {{ cookiecutter.project_slug }}.examples.content import source
from {{ cookiecutter.project_slug }}.examples.content import tab_for

BLOCKED_TASKS = 2


def test_a_source_is_the_template_as_written():
    written = source("form")

    # Template syntax and all, not what it renders to
    assert "{% raw %}{% csrf_token %}{% endraw %}" in written
    assert "{% raw %}{{ example_form }}{% endraw %}" in written
    assert written == written.strip()


def test_every_example_has_a_template():
    for example in STATIC_EXAMPLES:
        assert example.template_name == f"examples/{example.name}.html"
        assert example.source == source(example.name)
    for name in HTMX_EXAMPLES:
        assert source(name)


@pytest.mark.parametrize("name", ["index", "../base", "base", ""])
def test_only_an_example_has_a_source(name):
    with pytest.raises(ValueError, match="is not an example"):
        source(name)


def test_tasks_match_by_title_or_status_whatever_the_case():
    assert [task.title for task in matching_tasks("LANDING")] == [
        "Draft the landing page",
    ]
    assert len(matching_tasks("blocked")) == BLOCKED_TASKS
    assert matching_tasks("  ") == list(TASKS)
    assert matching_tasks("no such task") == []


def test_an_unknown_tab_is_the_first():
    assert tab_for("activity").title == "Activity"
    assert tab_for("no-such-tab") == TABS[0]
    assert tab_for(None) == TABS[0]
