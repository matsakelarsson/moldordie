"""The shared statement of what a row's answers are: ``tests/answers.py``."""

import pytest

from local_extensions import derived_answers
from tests.answers import DEFAULT_ANSWERS
from tests.answers import complete_answers
from tests.answers import parse_answers
from tests.answers import unknown_answers

# What generation adds to the defaults: none of the derived answers holds for them
DERIVED_FOR_THE_DEFAULTS = {"headless": False, "service_tokens": False}


def test_a_row_is_completed_by_the_defaults():
    assert complete_answers() == complete_answers({}) == {**DEFAULT_ANSWERS, **DERIVED_FOR_THE_DEFAULTS}
    assert complete_answers({"use_docker": "y"}) == {**DEFAULT_ANSWERS, "use_docker": "y", **DERIVED_FOR_THE_DEFAULTS}


def test_a_later_layer_answers_over_an_earlier_one():
    """The hook tests lay one group of answers over another, and a CI row generates from its
    script's own answers and then its own; the last word on an option wins."""
    earlier = {"use_docker": "y", "ci_tool": "Gitlab"}
    later = {"ci_tool": "Github"}

    complete = complete_answers(earlier, later)

    assert complete == {**DEFAULT_ANSWERS, "use_docker": "y", "ci_tool": "Github", **DERIVED_FOR_THE_DEFAULTS}
    assert earlier == {"use_docker": "y", "ci_tool": "Gitlab"}


def test_a_group_of_answers_is_read_as_a_shell_would_split_it():
    assert parse_answers("use_celery=y rest_api='Django Ninja' project_name='a=b'") == {
        "use_celery": "y",
        "rest_api": "Django Ninja",
        "project_name": "a=b",
    }


def test_a_word_that_is_no_answer_is_refused():
    with pytest.raises(ValueError, match="'use_docker' is not name=value"):
        parse_answers("use_celery=y use_docker")


def test_answers_the_catalogue_does_not_have_are_named():
    """A misspelt option or choice would otherwise generate the default project and pass."""
    answers = {"use_dokcer": "y", "use_docker": "yes", "rest_api": "DRF", "timezone": "Mars/Olympus"}

    assert unknown_answers(answers) == ["'use_dokcer' is not an option", "'yes' is not a choice of use_docker"]


def test_a_row_is_completed_with_the_derived_answers_as_generation_completes_it():
    """The pre-generation hook binds the derived answers after the defaults and the row, so a
    context in a test is a context the hook could really receive."""
    row = {"identity_provider": "entra", "rest_api": "Django Ninja"}

    complete = complete_answers(row)

    assert {name: complete[name] for name in derived_answers(complete)} == derived_answers({**DEFAULT_ANSWERS, **row})
    assert complete["headless"] is True
    assert set(complete) == set(DEFAULT_ANSWERS) | {"headless", "service_tokens"}
