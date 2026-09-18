"""The theme picker: the themes it offers, the cookie that keeps the choice, and the
attribute a page is served with.

Only the tests that render a page carry the django_db mark, for the transaction every
page view opens. Choosing a theme opens none, so a query there fails its tests: the
choice lives in a cookie, never in the session or on the user.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements
from {{ cookiecutter.project_slug }}.themes import COOKIE_MAX_AGE
from {{ cookiecutter.project_slug }}.themes import COOKIE_NAME
from {{ cookiecutter.project_slug }}.themes import OWN_THEME
from {{ cookiecutter.project_slug }}.themes import SYSTEM
from {{ cookiecutter.project_slug }}.themes import THEMES

# The themes daisyUI's plugin enables in styles/main.css, each with its flags
RE_THEMES = re.compile(r"^\s*themes:\s*(?P<list>[^;]+);", re.MULTILINE)
# The name of a theme block of the project's own, in styles/theme.css
RE_NAME = re.compile(r'^\s*name:\s*"(?P<name>[^"]+)";', re.MULTILINE)
HTMX = {"HX-Request": "true"}


def inputs(html, name):
    """The inputs of the page that are named ``name``."""
    return [attrs for attrs in elements(html, "input") if attrs.get("name") == name]


def checked(html):
    return [attrs["value"] for attrs in inputs(html, "theme") if "checked" in attrs]


def test_the_stylesheet_and_the_picker_name_the_same_themes():
    main = Path(settings.BASE_DIR) / settings.TAILWIND_CLI_SRC_CSS
    enabled = RE_THEMES.search(main.read_text())
    assert enabled
    entries = [entry.split() for entry in enabled["list"].split(",")]
    own = RE_NAME.findall((main.parent / "theme.css").read_text())

    assert own[0] == OWN_THEME
    assert (*own, *(name for name, *_ in entries)) == THEMES
    # One theme answers a dark colour scheme, and none of daisyUI's is the default
    assert [flags for _, *flags in entries if flags] == [["--prefersdark"]]


@pytest.mark.django_db
def test_a_page_is_served_in_the_chosen_theme(client: Client):
    client.cookies[COOKIE_NAME] = "dracula"

    html = client.get(reverse("home")).content.decode()

    assert element(html, "html")["data-theme"] == "dracula"
    assert checked(html) == ["dracula"]


@pytest.mark.django_db
@pytest.mark.parametrize("cookie", [None, "no-such-theme", ""])
def test_without_a_choice_the_browser_decides(client: Client, cookie: str | None):
    if cookie is not None:
        client.cookies[COOKIE_NAME] = cookie

    html = client.get(reverse("home")).content.decode()

    # No attribute at all: an empty one would switch the dark colour scheme off
    assert "data-theme" not in element(html, "html")
    assert checked(html) == [SYSTEM]


@pytest.mark.django_db
def test_the_picker_offers_every_theme_and_posts_through_htmx(client: Client):
    html = client.get(reverse("about")).content.decode()

    forms = {attrs.get("action"): attrs for attrs in elements(html, "form")}
    picker = forms[reverse("set_theme")]
    assert picker["method"] == "post"
    assert picker["hx-post"] == reverse("set_theme")
    assert picker["hx-trigger"] == "change"
    assert picker["hx-swap"] == "none"
    # Browsers restore a form's state on reload: the radio of an older choice
    assert picker["autocomplete"] == "off"
    radios = inputs(html, "theme")
    assert [attrs["value"] for attrs in radios] == [SYSTEM, *THEMES]
    # daisyUI applies the theme of a checked theme-controller in CSS; system names none
    controllers = [
        attrs["value"]
        for attrs in radios
        if "theme-controller" in (attrs["class"] or "")
    ]
    assert controllers == list(THEMES)
    assert [attrs["value"] for attrs in inputs(html, "next")] == [reverse("about")]


def test_htmx_keeps_the_choice_in_a_cookie(client: Client):
    response = client.post(reverse("set_theme"), {"theme": "dracula"}, headers=HTMX)

    # The checked radio has restyled the page already: there is nothing to swap
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""
    cookie = response.cookies[COOKIE_NAME]
    assert cookie.value == "dracula"
    assert cookie["max-age"] == COOKIE_MAX_AGE
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"


def test_system_forgets_the_choice_and_refreshes_the_page(client: Client):
    client.cookies[COOKIE_NAME] = "dracula"

    response = client.post(reverse("set_theme"), {"theme": SYSTEM}, headers=HTMX)

    # Nothing on the page can undo the data-theme it was served with
    assert response.status_code == HTTPStatus.OK
    assert response.headers["HX-Refresh"] == "true"
    cookie = response.cookies[COOKIE_NAME]
    assert cookie.value == ""
    assert cookie["max-age"] == 0


def test_a_post_without_htmx_returns_to_the_page_it_came_from(client: Client):
    data = {"theme": OWN_THEME, "next": reverse("about")}

    response = client.post(reverse("set_theme"), data)

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == reverse("about")
    assert response.cookies[COOKIE_NAME].value == OWN_THEME


def test_a_post_is_never_sent_to_another_host(client: Client):
    data = {"theme": OWN_THEME, "next": "https://elsewhere.example/"}

    response = client.post(reverse("set_theme"), data)

    assert response.headers["Location"] == reverse("home")


@pytest.mark.parametrize("name", ["no-such-theme", "", 'dracula"><script>'])
def test_an_unknown_theme_is_refused(client: Client, name: str):
    response = client.post(reverse("set_theme"), {"theme": name}, headers=HTMX)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert COOKIE_NAME not in response.cookies


def test_a_theme_is_chosen_by_post_with_the_token():
    client = Client(enforce_csrf_checks=True)

    assert client.get(reverse("set_theme")).status_code == HTTPStatus.METHOD_NOT_ALLOWED
    response = client.post(reverse("set_theme"), {"theme": OWN_THEME}, headers=HTMX)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert COOKIE_NAME not in response.cookies
