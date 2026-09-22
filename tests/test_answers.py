"""The shared statement of what a row's answers are: ``tests/answers.py``."""

from tests.answers import DEFAULT_ANSWERS
from tests.answers import complete_answers


def test_a_row_is_completed_by_the_defaults():
    assert complete_answers() == complete_answers({}) == DEFAULT_ANSWERS
    assert complete_answers({"use_docker": "y"}) == {**DEFAULT_ANSWERS, "use_docker": "y"}


def test_a_later_layer_answers_over_an_earlier_one():
    """The hook tests lay one group of answers over another; the last word on an option wins."""
    earlier = {"use_docker": "y", "ci_tool": "Gitlab"}
    later = {"ci_tool": "Github"}

    assert complete_answers(earlier, later) == {**DEFAULT_ANSWERS, "use_docker": "y", "ci_tool": "Github"}
    assert earlier == {"use_docker": "y", "ci_tool": "Gitlab"}
