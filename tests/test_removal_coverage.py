"""The coverage computation on hand-written rules and rows, never on the hook's table.

A bug here would make the real checks vacuous: the test that every removable path is baked
(``tests/test_cookiecutter_generation.py``) passes when this says every path is kept.
"""

from tests.removal_coverage import MOST_CHANGED_ANSWERS
from tests.removal_coverage import fewest_answers_keeping
from tests.removal_coverage import paths_kept

# Rules in the shape of the hook's table: the images go without Docker, the receiver's
# directory goes unless Prometheus is chosen with it, and the router module is listed twice,
# by the two answers that do not use it.
RULES = (
    (lambda c: c["use_docker"] == "n", ("compose", "justfile")),
    (lambda c: c["use_docker"] == "y" and c["observability"] != "prometheus", ("compose/local/prometheus",)),
    (lambda c: c["rest_api"] == "None", ("config/api_router.py", "config/api.py")),
    (lambda c: c["rest_api"] == "Django Ninja", ("config/api_router.py",)),
)
# The defaults of the options those rules read, and the choices each offers.
DEFAULTS = {
    "use_docker": "n",
    "cloud_provider": "AWS",
    "rest_api": "None",
    "observability": "none",
    "use_whitenoise": "n",
}
CHOICES = {
    "use_docker": ("y", "n"),
    "cloud_provider": ("AWS", "None"),
    "rest_api": ("None", "DRF", "Django Ninja"),
    "observability": ("none", "prometheus", "opentelemetry"),
    "use_whitenoise": ("y", "n"),
}


def complete(row):
    """A row's complete answers, over the hand-written defaults."""
    return {**DEFAULTS, **row}


def test_a_path_is_kept_when_some_row_escapes_every_rule_that_lists_it():
    rows = [complete({"use_docker": "y"}), complete({"rest_api": "DRF"})]

    kept = paths_kept(RULES, rows)

    assert kept["compose"] is True  # by the Docker row
    assert kept["config/api.py"] is True  # by the DRF row


def test_a_path_no_row_keeps_is_reported_as_such():
    kept = paths_kept(RULES, [complete({"use_docker": "y"})])

    assert kept["config/api.py"] is False


def test_every_listed_path_is_answered_for_once():
    assert list(paths_kept(RULES, [])) == [
        "compose",
        "justfile",
        "compose/local/prometheus",
        "config/api_router.py",
        "config/api.py",
    ]


def test_a_path_goes_with_a_directory_above_it_that_another_rule_removes():
    """Prometheus alone keeps no receiver: without Docker the whole ``compose`` directory goes."""
    without_docker = paths_kept(RULES, [complete({"observability": "prometheus"})])
    with_docker = paths_kept(RULES, [complete({"observability": "prometheus", "use_docker": "y"})])

    assert without_docker["compose/local/prometheus"] is False
    assert with_docker["compose/local/prometheus"] is True


def test_a_directory_written_with_its_slash_still_takes_what_is_below_it():
    """A spelling the hook deletes just as well must not count as kept by every row."""
    rules = (
        (lambda c: c["use_docker"] == "n", ("compose/",)),
        (lambda c: c["observability"] != "prometheus", ("compose/local/prometheus",)),
    )

    kept = paths_kept(rules, [complete({"observability": "prometheus"})])

    assert kept == {"compose/": False, "compose/local/prometheus": False}


def test_a_path_two_rules_list_is_kept_only_where_neither_applies():
    assert paths_kept(RULES, [complete({"rest_api": "Django Ninja"})])["config/api_router.py"] is False
    assert paths_kept(RULES, [complete({"rest_api": "None"})])["config/api_router.py"] is False
    assert paths_kept(RULES, [complete({"rest_api": "DRF"})])["config/api_router.py"] is True


def test_an_empty_row_means_the_defaults():
    """The defaults have no Docker and no REST API, so the row that names nothing keeps neither's files."""
    assert paths_kept(RULES, [complete({})]) == dict.fromkeys(
        ["compose", "justfile", "compose/local/prometheus", "config/api_router.py", "config/api.py"],
        False,
    )


# What a failure tells a contributor: the row to write.


def test_the_missing_row_changes_as_few_answers_as_keep_the_path():
    assert fewest_answers_keeping("compose", RULES, complete, CHOICES) == {"use_docker": "y"}
    assert fewest_answers_keeping("compose/local/prometheus", RULES, complete, CHOICES) == {
        "use_docker": "y",
        "observability": "prometheus",
    }


def test_the_missing_row_is_one_that_generates():
    """nginx needs no cloud provider, which the pre-generation hook refuses without WhiteNoise."""
    rules = ((lambda c: c["use_docker"] == "n" or c["cloud_provider"] != "None", ("compose/production/nginx",)),)

    def supported(answers):
        return not (answers["cloud_provider"] == "None" and answers["use_whitenoise"] == "n")

    row = fewest_answers_keeping("compose/production/nginx", rules, complete, CHOICES, supported=supported)

    assert row == {"use_docker": "y", "cloud_provider": "None", "use_whitenoise": "y"}
    assert len(row) <= MOST_CHANGED_ANSWERS


def test_the_missing_row_is_judged_on_answers_completed_as_the_caller_completes_them():
    """The rules may read what only completing adds, as they will a derived answer; a search
    that merged the defaults itself would hand them a row without it."""
    rules = ((lambda c: not c["measured"], ("docs/observability.rst",)),)

    def complete_with_derived(row):
        answers = complete(row)
        return {**answers, "measured": answers["observability"] != "none"}

    assert fewest_answers_keeping("docs/observability.rst", rules, complete_with_derived, CHOICES) == {
        "observability": "prometheus",
    }


def test_no_row_is_missing_for_a_path_that_no_answers_keep():
    rules = ((lambda c: True, ("orphan.py",)),)

    assert fewest_answers_keeping("orphan.py", rules, complete, CHOICES) is None
