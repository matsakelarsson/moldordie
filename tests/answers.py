"""The answers a row of the tests stands for.

A row, whether of the generation tests, of the hook tests or of the CI workflow, names the
answers it changes. What Cookiecutter generates from is the row's complete answers: the
catalogue's defaults with the row's answers on top, then the derived answers the pre-generation
hook binds from them (Bake in ``CONTEXT.md``). Every test that needs them gets them here, so
that "the defaults" and "what generation adds" are one statement. So is reading a row written
as text and checking it against the catalogue, which the CI rows, the integration scripts' own
answers and the extra rows of ``scripts/compare_generated.py`` all need.
"""

import shlex
from collections.abc import Mapping

from local_extensions import OPTIONS
from local_extensions import derived_answers

DEFAULT_ANSWERS = {name: option.default for name, option in OPTIONS.items()}
Answers = dict[str, str | bool]


def complete_answers(*layers: Mapping[str, str]) -> Answers:
    """The catalogue's defaults with each of ``layers`` on top, a later layer over an earlier
    one, and then the derived answers, as the pre-generation hook completes them.

    A free-text default that is a Jinja expression, the project slug's say, stays as declared:
    a caller that reads one supplies it in a layer.
    """
    answers: Answers = dict(DEFAULT_ANSWERS)
    for layer in layers:
        answers.update(layer)
    answers.update(derived_answers(answers))
    return answers


def parse_answers(text: str) -> dict[str, str]:
    """The answers in a group of ``name=value`` words, split as a shell would split them."""
    answers = {}
    for word in shlex.split(text):
        name, separator, value = word.partition("=")
        if not separator:
            msg = f"{word!r} is not name=value"
            raise ValueError(msg)
        answers[name] = value
    return answers


def unknown_answers(answers: dict[str, str]) -> list[str]:
    """What the catalogue does not have of ``answers``: an option, or a choice of a list or flag option.

    Cookiecutter ignores an option it does not know, so a misspelt one generates the default
    project without a word.
    """
    complaints = []
    for name, value in answers.items():
        if name not in OPTIONS:
            complaints.append(f"{name!r} is not an option")
        elif OPTIONS[name].choices and value not in OPTIONS[name].choices:
            complaints.append(f"{value!r} is not a choice of {name}")
    return complaints
