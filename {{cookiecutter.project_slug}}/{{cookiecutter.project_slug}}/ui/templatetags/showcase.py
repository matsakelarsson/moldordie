"""The showcase's tags: an example as written and a component's contract, for the
examples and components ``ui/showcase.py`` names (docs/frontend.rst).

The showcase loads the library by name; the tags are not builtins, since no other
template needs them.
"""

from __future__ import annotations

from django import template

from {{ cookiecutter.project_slug }}.ui import showcase

register = template.Library()


@register.simple_tag
def example_source(name: str) -> str:
    """The source of the showcase's example ``name``, escaped where it is written."""
    return showcase.example_source(name)


@register.simple_tag
def component_contract(name: str) -> str:
    """The comment a component's template opens with, as one paragraph."""
    return showcase.component_contract(name)
