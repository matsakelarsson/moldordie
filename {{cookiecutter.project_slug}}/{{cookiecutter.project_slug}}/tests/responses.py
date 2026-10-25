"""Reading a response in the tests: the page or the fragment it carries, and where an
anonymous request is sent."""

from __future__ import annotations

import re
from http import HTTPStatus

from django.conf import settings
from django.urls import reverse

# The messages container marked for htmx's out-of-band swap
RE_MESSAGES_SWAPPED = re.compile(r'<div[^>]*\bid="messages"[^>]*\bhx-swap-oob="true"')
# What a page loads and a fragment never carries
LOADS = ("<html", "<script", "<style", "<link")


def page(response) -> str:
    """The whole page a response carries, with the messages container in it once."""
    assert response.status_code == HTTPStatus.OK
    html: str = response.content.decode()
    assert "<html" in html
    assert html.count('id="messages"') == 1
    assert "hx-swap-oob" not in html
    return html


def fragment(response) -> str:
    """The fragment a response to htmx carries: a piece of a page with nothing a page
    loads, the messages container marked for the out-of-band swap, once, and the
    header it varies on."""
    assert response.status_code == HTTPStatus.OK
    assert "HX-Request" in response.headers["Vary"]
    html: str = response.content.decode()
    lowered = html.lower()
    for tag in LOADS:
        assert tag not in lowered, tag
    assert RE_MESSAGES_SWAPPED.search(html)
    assert html.count('id="messages"') == 1
    return html


def login_redirect(next_url: str) -> str:
    """The login page an anonymous request for ``next_url`` is sent to."""
    return f"{reverse(settings.LOGIN_URL)}?next={next_url}"
