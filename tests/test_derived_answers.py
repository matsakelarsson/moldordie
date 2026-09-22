"""The derived answers (a term in ``CONTEXT.md``): what follows from the answers, computed once.

``derived_answers`` in ``local_extensions.py`` is checked against a hand-written truth table over
every combination of the three answers it reads, stated as the sets of combinations where each
name holds, so the one definition is checked by something that is not itself. The guard at the
end keeps the templates reading the names rather than re-deriving them.
"""

import json
import re
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


# The guard against drift back: a template reads a derived answer by name and never re-derives
# it. What it recognises is a statement tag that names the identity provider together with the
# REST API or observability, the condition spelt out again, and a tag binding one of the names
# to anything but the derived answer, which gives the name a meaning of its own. A condition
# split over a local name, or spread over nested tags, is beyond a text guard; it is the
# reviewer's to see.
TEMPLATE = REPO / "{{cookiecutter.project_slug}}"
SHARED_SOURCE = REPO / "templates"
RE_TAG = re.compile(r"\{[%{#].*?[%}#]\}", re.DOTALL)
RE_RE_DERIVED = re.compile(
    r"identity_provider.*(rest_api|observability)|(rest_api|observability).*identity_provider",
    re.DOTALL,
)
RE_BOUND = re.compile(r"\bset\s+(headless|service_tokens)\s*=\s*(.*?)\s*-?%\}", re.DOTALL)


def re_deriving_tags(text: str) -> list[str]:
    """The Jinja tags of ``text`` that re-derive a derived answer, as written."""

    def re_derives(tag: str) -> bool:
        bound = RE_BOUND.search(tag)
        if bound:
            return bound.group(2) != f"cookiecutter.{bound.group(1)}"
        return tag.startswith("{%") and RE_RE_DERIVED.search(tag) is not None

    return [tag for tag in RE_TAG.findall(text) if re_derives(tag)]


RE_DERIVING = "{% if cookiecutter.identity_provider != 'none' and cookiecutter.rest_api == 'Django Ninja' %}"
READING = "{% if cookiecutter.observability == 'prometheus' and cookiecutter.service_tokens %}"


def test_the_guard_recognises_a_tag_that_re_derives_the_condition():
    assert re_deriving_tags(RE_DERIVING) == [RE_DERIVING]
    wrapped = "{%- if cookiecutter.identity_provider != 'none'\n    and cookiecutter.rest_api == 'Django Ninja' %}"
    assert re_deriving_tags(wrapped) == [wrapped]
    assert re_deriving_tags("{%- set headless = cookiecutter.rest_api == 'Django Ninja' -%}")
    assert re_deriving_tags("{%- set service_tokens = provider and prometheus %}")
    assert re_deriving_tags("{% if x %}") == []
    assert re_deriving_tags("{%- set headless = cookiecutter.headless -%}") == []
    assert re_deriving_tags(READING) == []
    assert re_deriving_tags("{# a comment naming identity_provider and rest_api #}") == []


def test_no_template_re_derives_a_derived_answer():
    """Every template reads ``headless`` and ``service_tokens`` from the context, so the two
    concepts mean one thing everywhere (docs/adr/0022)."""
    offending = {}
    for root in (TEMPLATE, SHARED_SOURCE):
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                tags = re_deriving_tags(path.read_text(errors="ignore"))
                if tags:
                    offending[path.relative_to(REPO).as_posix()] = tags
    assert offending == {}
