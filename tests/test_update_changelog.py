"""The pull request selection and grouping of ``scripts/update_changelog.py``.

The script itself talks to GitHub, so the two decisions it makes about a pull request
are exercised against stand-ins: which ones fall in the release window, and which
section of the release notes each one lands in.
"""

import datetime as dt
from types import SimpleNamespace

import pytest

from scripts.update_changelog import DEFAULT_SECTION
from scripts.update_changelog import EXCLUDED_LABEL
from scripts.update_changelog import SECTION_LABELS
from scripts.update_changelog import SECTIONS
from scripts.update_changelog import generate_md
from scripts.update_changelog import group_pulls_by_change_type
from scripts.update_changelog import iter_pulls
from scripts.update_changelog import todays_release
from scripts.update_changelog import warn_about_missing_labels


def pull(number, *, merged_at=None, updated_at=None, labels=()):
    """A stand-in for the attributes of a pull request that the script reads."""
    return SimpleNamespace(
        number=number,
        merged=merged_at is not None,
        merged_at=merged_at,
        updated_at=updated_at or merged_at,
        labels=[SimpleNamespace(name=name) for name in labels],
    )


def at(day, hour=12):
    return dt.datetime(2026, 9, day, hour, tzinfo=dt.UTC)


class FakeRepo:
    """Returns the pull requests newest-updated first, as the GitHub listing does."""

    def __init__(self, pulls=(), labels=()):
        self.pulls = sorted(pulls, key=lambda p: p.updated_at, reverse=True)
        self.labels = [SimpleNamespace(name=name) for name in labels]

    def get_pulls(self, **_kwargs):
        return self.pulls

    def get_labels(self):
        return self.labels


def test_a_grouping_label_the_tracker_lacks_is_reported():
    """The failure that went unnoticed: the script read "docs", the tracker said
    "documentation", and every documentation pull request landed in Changed instead."""
    repo = FakeRepo(labels=[EXCLUDED_LABEL, *list(SECTION_LABELS)[1:]])
    assert warn_about_missing_labels(repo) == [next(iter(SECTION_LABELS))]


def test_no_warning_when_the_tracker_has_every_grouping_label():
    repo = FakeRepo(labels=[EXCLUDED_LABEL, *SECTION_LABELS, "good first issue"])
    assert warn_about_missing_labels(repo) == []


def test_every_label_maps_to_a_rendered_section():
    """A section the template never renders would swallow the pull requests sent to it."""
    assert set(SECTION_LABELS.values()) | {DEFAULT_SECTION} <= set(SECTIONS)


@pytest.mark.parametrize(("label", "section"), SECTION_LABELS.items())
def test_a_labelled_pull_request_lands_in_its_section(label, section):
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1), labels=[label])])
    assert [p.number for p in grouped[section]] == [1]
    assert not any(pulls for name, pulls in grouped.items() if name != section)


def test_an_unlabelled_pull_request_defaults_to_changed():
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1))])
    assert [p.number for p in grouped[DEFAULT_SECTION]] == [1]


def test_an_unknown_label_defaults_to_changed():
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1), labels=["good first issue"])])
    assert [p.number for p in grouped[DEFAULT_SECTION]] == [1]


def test_project_infrastructure_is_left_out_entirely():
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1), labels=[EXCLUDED_LABEL])])
    assert not any(grouped.values())


def test_project_infrastructure_wins_over_a_section_label():
    """Excluding it has to beat every section, or the pull request reappears."""
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1), labels=["bug", EXCLUDED_LABEL])])
    assert not any(grouped.values())


def test_the_first_matching_label_decides_the_section():
    """Two section labels on one pull request resolve in the order SECTION_LABELS lists."""
    labels = list(SECTION_LABELS)
    grouped = group_pulls_by_change_type([pull(1, merged_at=at(1), labels=labels)])
    assert [p.number for p in grouped[SECTION_LABELS[labels[0]]]] == [1]


def test_only_pull_requests_merged_after_the_cutoff_are_collected():
    pulls = [
        pull(1, merged_at=at(10)),  # before the last release
        pull(2, merged_at=at(12)),  # after it
        pull(3, merged_at=at(13)),
    ]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=at(11))] == [3, 2]


def test_closed_but_unmerged_pull_requests_are_skipped():
    pulls = [pull(1, merged_at=at(12)), pull(2, updated_at=at(13))]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=at(11))] == [1]


def test_a_pull_request_merged_exactly_at_the_cutoff_is_not_collected_twice():
    """The cutoff is the previous release, whose own window already covered it."""
    pulls = [pull(1, merged_at=at(11)), pull(2, merged_at=at(12))]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=at(11))] == [2]


def test_without_a_previous_release_every_merged_pull_request_is_collected():
    pulls = [pull(1, merged_at=at(1)), pull(2, merged_at=at(9)), pull(3, updated_at=at(9))]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=None)] == [2, 1]


def test_the_walk_stops_at_the_cutoff_rather_than_reading_the_whole_history():
    """Walking is lazy, so a long history costs the window, not every closed pull request."""
    pulls = [pull(number, merged_at=at(number)) for number in range(1, 20)]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=at(17))] == [19, 18]


def test_a_pull_request_merged_earlier_but_touched_later_is_still_excluded():
    """Sorting is by update time, so a stale merge can sort first; merge time decides."""
    pulls = [pull(1, merged_at=at(5), updated_at=at(19)), pull(2, merged_at=at(18))]
    assert [p.number for p in iter_pulls(FakeRepo(pulls), since=at(17))] == [2]


def test_the_release_is_the_current_calendar_date_unpadded():
    today = dt.datetime.now(tz=dt.UTC).date()
    assert todays_release() == f"{today.year}.{today.month}.{today.day}"


def test_a_title_is_written_as_markdown_not_html():
    """The 2026.9.14 notes carried "admin&#39;s": the template renders Markdown, which needs no escaping."""
    pull_request = SimpleNamespace(
        title="Wire the admin's login & logout",
        number=1,
        html_url="https://example.invalid/1",
    )
    rendered = generate_md({DEFAULT_SECTION: [pull_request]})
    assert "- Wire the admin's login & logout ([#1](https://example.invalid/1))" in rendered
