"""The library's stylesheets read tokens: each one named exists, no colour is literal.

Colours belong to the palettes in ui/palettes.py and reach the page through the theme
stylesheet; every other token is declared in static/css/ui/tokens.css.
"""

import re
from pathlib import Path

from {{ cookiecutter.project_slug }}.ui.palettes import TOKENS

CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "ui"
STYLESHEETS = ("base.css", "components.css")

RE_READ = re.compile(r"var\(--ui-([a-z0-9-]+)")
RE_DECLARED = re.compile(r"--ui-([a-z0-9-]+)\s*:")
RE_LITERAL_COLOUR = re.compile(r"#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?)\(", re.IGNORECASE)


def test_every_token_read_is_declared_or_a_colour_of_the_palettes():
    declared = set(RE_DECLARED.findall((CSS / "tokens.css").read_text()))
    known = declared | set(TOKENS)
    for name in STYLESHEETS:
        read = set(RE_READ.findall((CSS / name).read_text()))
        assert read, name
        assert read - known == set(), name


def test_the_stylesheets_repeat_no_colour_value():
    for name in STYLESHEETS:
        assert RE_LITERAL_COLOUR.findall((CSS / name).read_text()) == [], name
