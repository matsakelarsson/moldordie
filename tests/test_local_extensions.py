"""Unit tests for the Jinja filters in local_extensions.py"""

import ast
import json
import tomllib
from pathlib import Path

import yaml
from cookiecutter.environment import StrictEnvironment

from local_extensions import string_escape

REPO = Path(__file__).resolve().parent.parent

# The characters that end or escape a string in one of the generated syntaxes, including a
# trailing backslash, which would otherwise escape the closing delimiter.
HOSTILE = 'She said "hi" & <left> C:\\path, it\'s fine \\'


def test_string_escape_round_trips_through_python():
    assert ast.literal_eval(f'"{string_escape(HOSTILE)}"') == HOSTILE
    assert ast.literal_eval(f'"""{string_escape(HOSTILE)}"""') == HOSTILE
    assert ast.literal_eval(f"'{string_escape(HOSTILE, quote=chr(39))}'") == HOSTILE


def test_string_escape_round_trips_through_toml():
    assert tomllib.loads(f'value = "{string_escape(HOSTILE)}"')["value"] == HOSTILE


def test_string_escape_round_trips_through_yaml():
    assert yaml.safe_load(f'value: "{string_escape(HOSTILE)}"')["value"] == HOSTILE


def test_string_escape_leaves_plain_text_alone():
    assert string_escape("Behold My Awesome Project!") == "Behold My Awesome Project!"


def test_cookiecutter_loads_the_filter():
    """The filter reaches the templates through ``_extensions`` in cookiecutter.json."""
    options = json.loads((REPO / "cookiecutter.json").read_text())
    env = StrictEnvironment(context={"cookiecutter": options})

    assert env.from_string("{{ answer | string_escape }}").render(answer=HOSTILE) == string_escape(HOSTILE)
