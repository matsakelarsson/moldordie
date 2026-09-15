"""Serialisation of the attributes a component forwards to its element.

``serialize_attrs`` is the contract behind the ``ui_attrs`` filter: which names are
forwarded, how a value becomes attribute text, and which values are refused rather
than written in a form that means something else. ``attribute_value`` and ``url_value``
are the same rules for one declared input, behind ``ui_attr`` and ``ui_url``.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from django.utils.functional import Promise
from django.utils.html import escape
from django.utils.safestring import SafeString
from django.utils.safestring import mark_safe

from .links import local_url

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$", re.ASCII)
_FORBIDDEN_NAMES = frozenset({"class"})
_FORBIDDEN_PREFIXES = ("on", "hx-on", "data-hx-on")
# HTML's boolean attributes: present or absent, never "true" or "false"
BOOLEAN_ATTRIBUTES = frozenset(
    {
        "allowfullscreen",
        "async",
        "autofocus",
        "autoplay",
        "checked",
        "controls",
        "default",
        "defer",
        "disabled",
        "formnovalidate",
        "inert",
        "ismap",
        "itemscope",
        "loop",
        "multiple",
        "muted",
        "nomodule",
        "novalidate",
        "open",
        "playsinline",
        "readonly",
        "required",
        "reversed",
        "selected",
    },
)
# Prefixes whose attributes take the words "true" and "false"
_TEXTUAL_BOOLEAN_PREFIXES = ("aria-", "data-", "hx-")
_DESTINATIONS = frozenset({"hx-get", "hx-post", "hx-put", "hx-patch", "hx-delete"})
_HISTORY = frozenset({"hx-push-url", "hx-replace-url"})
_TEXT_TYPES = (str, int, float, Promise)


def attribute_value(value: object) -> str:
    """``value`` as attribute text: a marked-safe string keeps its entities and has its
    literal double quotes encoded, anything else is escaped."""
    if isinstance(value, SafeString):
        return value.replace('"', "&quot;")
    return escape(str(value))


def url_value(value: object, policy: Callable[[str], str]) -> str:
    """``value`` as attribute text once ``policy`` accepts the URL the browser will get.

    A marked-safe value is decoded once, so an entity cannot hide a scheme from the
    policy, and the validated text is escaped again. Any other value is validated as
    its literal text, entity-looking sequences included, and escaped.
    """
    if value is None:
        msg = "the URL is missing"
        raise ValueError(msg)
    text = str(value)
    if isinstance(value, SafeString):
        text = html.unescape(text)
    policy(text)
    return escape(text)


def serialize_attrs(attrs: Mapping[str, object]) -> SafeString:
    """The attributes in ``attrs`` as ``name="value"`` text for an element.

    Raises ``ValueError`` for a name that is not an attribute name, a name that is
    forwarded by no component (``class``, ``style``, event handlers, ``hx-on``), a
    name given twice, a boolean where text is expected or text where a boolean is,
    and an htmx destination that leaves this origin; ``TypeError`` for a value that
    is not text, a dict or a list for one.
    """
    seen: set[str] = set()
    parts: list[str] = []
    for name, value in attrs.items():
        lower = _valid_name(name, seen)
        if value is None:
            continue
        rendered = _render(name, lower, value)
        if rendered is not None:
            parts.append(rendered)
    return mark_safe(" ".join(parts))  # noqa: S308


def _valid_name(name: object, seen: set[str]) -> str:
    if not isinstance(name, str) or not _NAME.match(name):
        msg = f"{name!r} is not an attribute name"
        raise ValueError(msg)
    lower = name.lower()
    if lower in _FORBIDDEN_NAMES:
        msg = f"{name} is not forwarded: a component declares and writes it itself"
        raise ValueError(msg)
    if lower == "style" or lower.startswith(_FORBIDDEN_PREFIXES):
        msg = f"{name} is not forwarded: the policy forbids inline code"
        raise ValueError(msg)
    if lower in seen:
        msg = f"{name} is given twice"
        raise ValueError(msg)
    seen.add(lower)
    return lower


def _render(name: str, lower: str, value: object) -> str | None:
    if lower in BOOLEAN_ATTRIBUTES:
        if isinstance(value, bool):
            return name if value else None
        msg = f"{name} is a boolean attribute: True, False or None, not {value!r}"
        raise ValueError(msg)
    if lower == "hidden":
        if isinstance(value, bool):
            return name if value else None
        if value == "until-found":
            return f'{name}="until-found"'
        msg = f"hidden takes True, False, None or 'until-found', not {value!r}"
        raise ValueError(msg)
    if isinstance(value, bool):
        if lower.startswith(_TEXTUAL_BOOLEAN_PREFIXES):
            return f'{name}="{"true" if value else "false"}"'
        msg = f"{name} takes text, not {value!r}"
        raise ValueError(msg)
    if not isinstance(value, _TEXT_TYPES):
        msg = f"{name} takes text, not a {type(value).__name__}"
        raise TypeError(msg)
    htmx = lower.removeprefix("data-") if lower.startswith("data-hx-") else lower
    history = htmx in _HISTORY and str(value) not in ("true", "false")
    if htmx in _DESTINATIONS or history:
        return f'{name}="{url_value(value, local_url)}"'
    return f'{name}="{attribute_value(value)}"'
