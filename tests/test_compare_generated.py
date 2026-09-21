"""What ``scripts/compare_generated.py`` decides, without baking the matrix.

The script bakes every supported combination from two revisions, so running it is not a test
of this suite. What it decides is exercised on hand-written input: which extra rows it
accepts, and what it reports for two generated trees. One test bakes, two rows from the
working tree against itself, to hold the two things only a bake shows: the masking is
complete, and a row that does not generate is reported.
"""

import pytest

from scripts.compare_generated import ROOT
from scripts.compare_generated import Bake
from scripts.compare_generated import Difference
from scripts.compare_generated import compare
from scripts.compare_generated import differences
from scripts.compare_generated import parse_row


def test_an_extra_row_is_a_group_of_answers():
    assert parse_row("use_docker=y postgresql_version=14") == {"use_docker": "y", "postgresql_version": "14"}


def test_an_extra_row_quotes_an_answer_with_spaces_as_the_ci_rows_do():
    assert parse_row("rest_api='Django Ninja' domain_name=app.example.com") == {
        "rest_api": "Django Ninja",
        "domain_name": "app.example.com",
    }


@pytest.mark.parametrize(
    ("row", "complaint"),
    [
        ("use_dokcer=y", "'use_dokcer' is not an option"),
        ("use_docker=yes", "'yes' is not a choice of use_docker"),
        ("use_docker", "'use_docker' is not name=value"),
    ],
)
def test_an_extra_row_is_checked_against_the_catalogue(row, complaint):
    """A misspelt option would bake the default project twice and report no difference."""
    with pytest.raises(ValueError, match=complaint):
        parse_row(row)


# Two output directories as the two sides baked them, each holding the project under its slug,
# and a value as each side drew it.
SLUG = "my_project"
DRAWN_BY_BASE = "k3" * 32
DRAWN_BY_WORKING_TREE = "Zx9q" * 16


def env_file(drawn, concurrency=4):
    """A file that holds a drawn value, and a value nothing draws."""
    return {".envs/.production/.django": f"DJANGO_SECRET_KEY={drawn}\nWEB_CONCURRENCY={concurrency}\n"}


def generated(root, files):
    """Write ``files``, contents by path relative to the project, as the project baked into ``root``."""
    for path, content in files.items():
        target = root / SLUG / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content)
    return root


@pytest.fixture
def base(tmp_path):
    return tmp_path / "base"


@pytest.fixture
def working_tree(tmp_path):
    return tmp_path / "working-tree"


def test_the_same_tree_twice_has_no_differences(base, working_tree):
    files = {"README.md": "# My Project\n", "config/settings/base.py": "DEBUG = False\n"}

    assert differences(generated(base, files), generated(working_tree, files)) == []


def test_a_changed_file_is_reported_with_its_path_and_a_unified_diff(base, working_tree):
    generated(base, {"README.md": "# My Project\n", "config/urls.py": "urlpatterns = []\n"})
    generated(working_tree, {"README.md": "# My Project\n", "config/urls.py": "urlpatterns = [admin]\n"})

    [difference] = differences(base, working_tree)

    assert (difference.path, difference.change) == (f"{SLUG}/config/urls.py", "differs")
    assert "-urlpatterns = []" in difference.diff
    assert "+urlpatterns = [admin]" in difference.diff


def test_a_file_only_one_revision_generates_is_missing_or_new(base, working_tree):
    generated(base, {"README.md": "# My Project\n", "justfile": "default:\n"})
    generated(working_tree, {"README.md": "# My Project\n", "compose/local/prometheus/prometheus.yml": "global: {}\n"})

    assert differences(base, working_tree) == [
        Difference(f"{SLUG}/compose/local/prometheus/prometheus.yml", "is new"),
        Difference(f"{SLUG}/justfile", "is missing"),
    ]


def test_values_drawn_on_generation_are_no_difference(base, working_tree):
    """Two bakes never draw the same secrets, so the files that hold them compare masked."""
    generated(base, env_file(DRAWN_BY_BASE))
    generated(working_tree, env_file(DRAWN_BY_WORKING_TREE))

    assert differences(base, working_tree) == []


def test_a_secret_file_still_differs_in_what_was_not_drawn(base, working_tree):
    generated(base, env_file(DRAWN_BY_BASE))
    generated(working_tree, env_file(DRAWN_BY_WORKING_TREE, concurrency=8))

    [difference] = differences(base, working_tree)

    assert difference.path == f"{SLUG}/.envs/.production/.django"
    assert "-WEB_CONCURRENCY=4" in difference.diff
    assert "+WEB_CONCURRENCY=8" in difference.diff
    # The diff is of the masked contents, so it shows the change and no drawn value.
    assert DRAWN_BY_BASE not in difference.diff
    assert DRAWN_BY_WORKING_TREE not in difference.diff


def test_a_long_run_outside_the_secret_files_is_compared_as_it_stands(base, working_tree):
    """A pinned digest is a long run of letters and digits too; masking it everywhere would hide its change."""
    generated(base, {"compose/production/django/Dockerfile": f"FROM python@sha256:{DRAWN_BY_BASE}\n"})
    generated(working_tree, {"compose/production/django/Dockerfile": f"FROM python@sha256:{DRAWN_BY_WORKING_TREE}\n"})

    assert [difference.path for difference in differences(base, working_tree)] == [
        f"{SLUG}/compose/production/django/Dockerfile",
    ]


def test_a_binary_file_differs_without_a_diff(base, working_tree):
    generated(base, {f"{SLUG}/static/images/favicon.ico": b"\x00\x01\xff\xfe"})
    generated(working_tree, {f"{SLUG}/static/images/favicon.ico": b"\x00\x01\xff\xfd"})

    assert differences(base, working_tree) == [Difference(f"{SLUG}/{SLUG}/static/images/favicon.ico", "differs")]


@pytest.mark.parametrize(
    ("before", "after", "change"),
    [(0o755, 0o644, "is no longer executable"), (0o644, 0o755, "is now executable")],
)
def test_a_file_that_gains_or_loses_its_executable_bit_is_reported(base, working_tree, before, after, change):
    """Git records the bit, and an entrypoint that loses it no longer starts its container."""
    generated(base, {"compose/production/django/start": "#!/bin/bash\n"})
    generated(working_tree, {"compose/production/django/start": "#!/bin/bash\n"})
    (base / SLUG / "compose/production/django/start").chmod(before)
    (working_tree / SLUG / "compose/production/django/start").chmod(after)

    assert differences(base, working_tree) == [Difference(f"{SLUG}/compose/production/django/start", change)]


def test_a_directory_left_empty_on_one_side_is_reported(base, working_tree):
    """No file shows it: pruning that leaves a package's directory behind generates a different tree."""
    generated(base, {"README.md": "# My Project\n"})
    generated(working_tree, {"README.md": "# My Project\n"})
    (working_tree / SLUG / "my_project" / "tests").mkdir(parents=True)

    assert differences(base, working_tree) == [Difference(f"{SLUG}/my_project/tests", "is new")]


def test_the_working_tree_against_itself_reports_a_refused_row_and_nothing_else(tmp_path):
    """The one test that bakes. The defaults baked twice draw different secrets and differ in
    nothing once masked, and a row the pre-generation hook refuses is reported in the hook's
    words rather than skipped: a row that was not compared proves nothing."""
    refused = Bake({"cloud_provider": "None", "use_whitenoise": "n"}, hostile=False)
    defaults = Bake({}, hostile=True)

    report = compare(ROOT, ROOT, [refused, defaults], tmp_path, jobs=4)

    assert [bake for bake, _ in report] == [refused, defaults]
    assert report[1][1] == []
    said_by_base, said_by_working_tree = report[0][1]
    assert said_by_base.startswith("the base revision fails to bake it:")
    assert said_by_working_tree.startswith("the working tree fails to bake it:")
    assert "You should either use Whitenoise or select a Cloud Provider" in said_by_base
