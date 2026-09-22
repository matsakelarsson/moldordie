"""The answers a row of the tests stands for.

A row of the generation tests or of the hook tests names the answers it changes. What
Cookiecutter generates from is the row's complete answers: the catalogue's defaults with the
row's answers on top (Bake in ``CONTEXT.md``). Every test that needs them gets them here, so
that "the defaults" is one statement.
"""

from local_extensions import OPTIONS

DEFAULT_ANSWERS = {name: option.default for name, option in OPTIONS.items()}


def complete_answers(*layers: dict[str, str]) -> dict[str, str]:
    """The catalogue's defaults with each of ``layers`` on top, a later layer over an earlier one.

    A free-text default that is a Jinja expression, the project slug's say, stays as declared:
    a caller that reads one supplies it in a layer.
    """
    answers = dict(DEFAULT_ANSWERS)
    for layer in layers:
        answers.update(layer)
    return answers
