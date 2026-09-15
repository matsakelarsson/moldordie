"""The template filters of the UI library, builtins of every template.

``ui_attrs`` writes the attributes a component did not declare onto its element,
``ui_attr`` one declared input in an attribute position, and ``ui_url`` a URL once the
named policy accepts it: ``navigation`` for links, ``local`` for htmx destinations.
The rules are in ``ui/attrs.py`` and ``ui/links.py`` (docs/frontend.rst).
"""

from __future__ import annotations

from collections.abc import Mapping

from django import template
from django.utils.safestring import SafeString
from django.utils.safestring import mark_safe

from {{ cookiecutter.project_slug }}.ui.attrs import attribute_value
from {{ cookiecutter.project_slug }}.ui.attrs import serialize_attrs
from {{ cookiecutter.project_slug }}.ui.attrs import url_value
from {{ cookiecutter.project_slug }}.ui.links import local_url
from {{ cookiecutter.project_slug }}.ui.links import navigation_url

register = template.Library()

POLICIES = {"navigation": navigation_url, "local": local_url}


@register.filter(name="ui_attrs")
def ui_attrs(attrs: object) -> SafeString:
    """The attributes a component did not declare, serialised for its element."""
    attrs_dict = getattr(attrs, "attrs_dict", None)
    forwarded = attrs_dict() if callable(attrs_dict) else attrs
    if not isinstance(forwarded, Mapping):
        msg = f"ui_attrs takes a component's attrs, not {type(attrs).__name__}"
        raise TypeError(msg)
    return serialize_attrs(forwarded)


@register.filter(name="ui_attr")
def ui_attr(value: object) -> SafeString:
    """One declared input as attribute text; None writes nothing."""
    if value is None:
        return mark_safe("")
    return mark_safe(attribute_value(value))  # noqa: S308


@register.filter(name="ui_url")
def ui_url(value: object, policy: str = "navigation") -> SafeString:
    """A URL as attribute text once ``policy`` accepts what the browser will receive."""
    try:
        validate = POLICIES[policy]
    except KeyError:
        msg = f"{policy!r} is not a URL policy: {' or '.join(POLICIES)}"
        raise ValueError(msg) from None
    return mark_safe(url_value(value, validate))  # noqa: S308
