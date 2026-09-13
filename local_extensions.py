"""The option catalogue and the Jinja filter of the template.

Cookiecutter loads ``OptionsExtension`` and ``StringEscapeExtension`` through ``_extensions`` in
``cookiecutter.json``. The catalogue is importable by the tests; the hooks, which run as standalone
scripts, read it through the ``option_names`` Jinja global that ``OptionsExtension`` registers.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment
from jinja2.ext import Extension

OPTIONS_PATH = Path(__file__).with_name("cookiecutter.json")

# The kinds of option (see Option in CONTEXT.md), as the declarations in cookiecutter.json
# show them: a list of choices, a yes/no default, or any other text.
LIST = "list"
FLAG = "flag"
FREE_TEXT = "free text"


@dataclass(frozen=True)
class Option:
    """One question of ``cookiecutter.json``: its kind, the answers it takes and its default."""

    name: str
    kind: str
    choices: tuple[str, ...]
    """Every answer a list or flag option accepts, in declaration order; empty for free text."""
    default: str
    """As declared: the first choice, ``y`` or ``n``, or the text, which may be a Jinja expression."""


def load_options(path: Path = OPTIONS_PATH) -> dict[str, Option]:
    """The catalogue: every option declared in ``path``, keyed by name, in declaration order."""
    declarations = json.loads(path.read_text())
    options = {}
    for name, declaration in declarations.items():
        if name.startswith("_"):  # Cookiecutter's own settings
            continue
        if isinstance(declaration, list):
            options[name] = Option(name, LIST, tuple(declaration), declaration[0])
        elif declaration in ("y", "n"):
            options[name] = Option(name, FLAG, ("y", "n"), declaration)
        else:
            options[name] = Option(name, FREE_TEXT, (), declaration)
    return options


OPTIONS = load_options()


def option_names(kind: str) -> tuple[str, ...]:
    """The names of the options of ``kind``, in declaration order."""
    return tuple(option.name for option in OPTIONS.values() if option.kind == kind)


class OptionsExtension(Extension):
    """Register ``option_names`` in the Jinja environment Cookiecutter renders the files and hooks with."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        environment.globals["option_names"] = option_names


def string_escape(value: str, quote: str = '"') -> str:
    """Escape ``value`` to sit inside a string literal delimited by ``quote``.

    Covers the syntaxes with backslash escapes that the template writes answers into: Python,
    TOML basic strings, YAML double-quoted scalars and gettext ``.po`` strings. TOML and YAML
    have no other escaped form, so ``quote`` may be ``'`` in Python alone. Control characters
    need no escaping because the pre-generation hook rejects them.
    """
    return value.replace("\\", "\\\\").replace(quote, "\\" + quote)


class StringEscapeExtension(Extension):
    """Register ``string_escape`` in the Jinja environment Cookiecutter renders with."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        environment.filters["string_escape"] = string_escape
