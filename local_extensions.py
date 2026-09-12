"""Jinja filters for the template, loaded by Cookiecutter through ``_extensions`` in ``cookiecutter.json``."""

from jinja2 import Environment
from jinja2.ext import Extension


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
