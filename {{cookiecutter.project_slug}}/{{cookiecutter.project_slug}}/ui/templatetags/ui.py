"""The template filters of the UI library, builtins of every template.

``ui_attrs`` writes the attributes a component did not declare onto its element,
``ui_attr`` one declared input in an attribute position, and ``ui_url`` a URL once the
named policy accepts it: ``navigation`` for links, ``local`` for htmx destinations.
The rules are in ``ui/attrs.py`` and ``ui/links.py``. ``ui_label`` writes a bound
field's label for the field component (docs/frontend.rst).
"""

from __future__ import annotations

from collections.abc import Mapping

from django import template
from django.forms import BoundField
from django.utils.html import format_html
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


@register.filter(name="ui_label")
def ui_label(field: object, tag: str = "label") -> SafeString:
    """A bound field's label as a ``<label>``, or a ``<legend>`` with ``tag="legend"``.

    Django writes the ``for`` attribute and the field's own suffix rules; the form's
    label suffix is left out, the library's class put on. Django writes no tag for a
    field without an id, so the text is then wrapped in a span of the same class.
    """
    if not isinstance(field, BoundField):
        msg = f"ui_label takes a bound field, not {type(field).__name__}"
        raise TypeError(msg)
    css_class = "ui-legend" if tag == "legend" else "ui-label"
    label = field.label_tag(attrs={"class": css_class}, label_suffix="", tag=tag)
    if field.field.widget.attrs.get("id") or field.auto_id:
        return label
    return format_html('<span class="{}">{}</span>', css_class, label)
