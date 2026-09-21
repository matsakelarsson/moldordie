"""The shared statement of what a row's answers are: ``tests/answers.py``."""

import pytest

from tests.answers import DEFAULT_ANSWERS
from tests.answers import complete_answers
from tests.answers import parse_answers
from tests.answers import unknown_answers


def test_a_row_is_completed_by_the_defaults():
    assert complete_answers() == complete_answers({}) == DEFAULT_ANSWERS
    assert complete_answers({"use_docker": "y"}) == {**DEFAULT_ANSWERS, "use_docker": "y"}


def test_a_later_layer_answers_over_an_earlier_one():
    """The hook tests lay one group of answers over another, and a CI row generates from its
    script's own answers and then its own; the last word on an option wins."""
    earlier = {"use_docker": "y", "ci_tool": "Gitlab"}
    later = {"ci_tool": "Github"}

    assert complete_answers(earlier, later) == {**DEFAULT_ANSWERS, "use_docker": "y", "ci_tool": "Github"}
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
