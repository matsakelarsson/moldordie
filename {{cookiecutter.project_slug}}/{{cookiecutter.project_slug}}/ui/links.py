"""Validation of the URLs the components write, as the browser will receive them.

Two policies. ``navigation_url`` is for links the user follows: a relative reference,
or an absolute http or https URL with a hostname. ``local_url`` is for htmx
destinations, which stay on this origin: a relative reference only. Both refuse what
could smuggle a scheme past a check: control characters, backslashes, surrounding
whitespace and a protocol-relative ``//host``. A value is validated as given; its
percent-encoding and any entities left in it are not decoded here.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_absolute = URLValidator(schemes=["http", "https"])


def _reference(url: str, policy: str) -> None:
    if url == "":
        msg = f"the {policy} URL is empty"
        raise ValueError(msg)
    if url != url.strip():
        msg = f"{url!r} has surrounding whitespace, which browsers strip"
        raise ValueError(msg)
    if _CONTROL.search(url) or "\\" in url:
        msg = f"{url!r} contains control characters or backslashes"
        raise ValueError(msg)
    if url.startswith("//"):
        msg = f"{url!r} is protocol-relative, which leaves this origin"
        raise ValueError(msg)


def navigation_url(url: str) -> str:
    """``url`` when it is a relative reference or an absolute http(s) URL with a host.

    A relative reference whose first segment holds a colon reads as a scheme; write
    it as ``./name:value``.
    """
    _reference(url, "navigation")
    if _SCHEME.match(url):
        try:
            _absolute(url)
        except ValidationError:
            msg = f"{url!r} is not an http or https URL with a hostname"
            raise ValueError(msg) from None
    return url


def local_url(url: str) -> str:
    """``url`` when it is a relative reference on this origin: no scheme, no host."""
    _reference(url, "local")
    if _SCHEME.match(url):
        msg = f"{url!r} names a scheme; an htmx destination stays on this origin"
        raise ValueError(msg)
    return url
