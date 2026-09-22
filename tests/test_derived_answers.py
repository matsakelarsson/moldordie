"""The derived answers (a term in ``CONTEXT.md``): what follows from the answers, computed once.

``derived_answers`` in ``local_extensions.py`` is checked against a hand-written truth table over
every combination of the three answers it reads, stated as the sets of combinations where each
name holds, so the one definition is checked by something that is not itself.
"""

import json
from itertools import product
from pathlib import Path

from cookiecutter.environment import StrictEnvironment

from local_extensions import OPTIONS
from local_extensions import derived_answers

REPO = Path(__file__).resolve().parent.parent

# Every combination of the answers the derivation reads: 3 providers x 3 APIs x 3 arms
COMBINATIONS = [
    {"identity_provider": provider, "rest_api": api, "observability": observability}
    for provider, api, observability in product(
        OPTIONS["identity_provider"].choices,
        OPTIONS["rest_api"].choices,
        OPTIONS["observability"].choices,
    )
]

# Where each name holds, written by hand from ADR 0019. Headless: Django Ninja with a
# provider, whatever measures. Service tokens: a provider whose tokens something reads,
# Django Ninja's routes or the metrics endpoint.
HEADLESS = {
    (provider, "Django Ninja", observability)
    for provider in ("entra", "google")
    for observability in ("none", "prometheus", "opentelemetry")
}
SERVICE_TOKENS = HEADLESS | {
    (provider, api, "prometheus") for provider in ("entra", "google") for api in ("None", "DRF", "Django Ninja")
}


def test_the_truth_table():
    """At the plain-data seam: the three answers the derivation reads, and nothing completes them."""
    assert len(COMBINATIONS) == 3 * 3 * 3
    for answers in COMBINATIONS:
        key = (answers["identity_provider"], answers["rest_api"], answers["observability"])
        derived = derived_answers(answers)

        assert derived == {"headless": key in HEADLESS, "service_tokens": key in SERVICE_TOKENS}, key
        assert all(isinstance(value, bool) for value in derived.values()), key


def test_cookiecutter_exposes_derived_answers_to_the_hooks():
    """The pre-generation hook binds them through this global, as it reads the catalogue through
    ``option_names``; a template could read it too, though none needs to."""
    declarations = json.loads((REPO / "cookiecutter.json").read_text())
    env = StrictEnvironment(context={"cookiecutter": declarations})
    answers = {"identity_provider": "google", "rest_api": "None", "observability": "prometheus"}

    rendered = env.from_string("{{ derived_answers(answers) | tojson }}").render(answers=answers)

    assert json.loads(rendered) == derived_answers(answers) == {"headless": False, "service_tokens": True}
