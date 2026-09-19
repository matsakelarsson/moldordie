"""The examples page: every example rendered and shown, and each htmx demo answered
with a fragment for htmx and with the whole page, or a redirect to it, without.

Only the test of a project without the page carries the django_db mark, for the home
page it renders. The examples' views open no transaction and keep nothing on the
server, so a query anywhere else fails the test that caused it.
"""

from __future__ import annotations

import re
import time
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from {{ cookiecutter.project_slug }}.examples import views
from {{ cookiecutter.project_slug }}.examples.content import HTMX_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import STATIC_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import source
from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings

HTMX = {"HX-Request": "true"}
RE_MESSAGES_SWAPPED = re.compile(r'<div[^>]*\bid="messages"[^>]*\bhx-swap-oob="true"')
VALID = {"name": "Ada", "plan": "solo", "seats": "1", "terms": "on"}
ROWS_PER_PAGE = 5
LAST_PAGE_ROWS = 2
POSTS = ["examples:form", "examples:toggle", "examples:modal", "examples:notices"]


def fragment(response):
    """The body of an answer to htmx: a piece of a page, with nothing a page loads."""
    assert response.status_code == HTTPStatus.OK
    assert "HX-Request" in response.headers["Vary"]
    html = response.content.decode()
    for tag in ("<html", "<script", "<style", "<link"):
        assert tag not in html.lower(), tag
    return html


def page(response):
    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert "<html" in html
    return html


def rows(html):
    return re.findall(r"<td>([^<]+)</td>", html)


def test_the_page_renders_every_example_and_shows_it_as_written(client: Client):
    html = page(client.get(reverse("examples:index")))

    sections = {attrs.get("id") for attrs in elements(html, "section")}
    shown = {"form", "results", "toggle", "tabs", "modal", "notices"}
    for name in (*(example.name for example in STATIC_EXAMPLES), *shown):
        assert f"example-{name}" in sections, name
    for name in (*(example.name for example in STATIC_EXAMPLES), *HTMX_EXAMPLES):
        assert escape(source(name)) in html, name
    current = [attrs for attrs in elements(html, "a") if "aria-current" in attrs]
    assert {attrs["href"] for attrs in current} >= {reverse("examples:index")}
    # One container for a dialog, and none open
    assert html.count('id="modal"') == 1
    assert "modal-open" not in html.replace(escape(source("modal")), "")


def test_the_form_shows_a_widget_of_each_kind(client: Client):
    html = page(client.get(reverse("examples:index")))

    inputs = {attrs.get("name"): attrs for attrs in elements(html, "input")}
    assert "toggle" in (inputs["newsletter"]["class"] or "")
    assert "checkbox" in (inputs["terms"]["class"] or "")
    assert "radio" in (inputs["plan"]["class"] or "")
    assert "disabled" in inputs["reference"]
    assert element(html, "textarea")["name"] == "notes"
    assert element(html, "select")["name"] == "contact"


def test_an_invalid_form_comes_back_with_its_errors(client: Client):
    data = {"plan": "team", "seats": "1"}

    html = fragment(client.post(reverse("examples:form"), data, headers=HTMX))

    # 200, which htmx swaps: its default configuration swaps no error response
    assert element(html, "div", "id", "example-form-container")
    invalid = [a["name"] for a in elements(html, "input") if "aria-invalid" in a]
    assert invalid == ["name", "seats", "terms"]
    assert "A team has at least two seats." in html
    assert "alert-success" not in html
    assert "nothing was saved" not in html


def test_a_valid_form_answers_with_its_result_and_a_message(client: Client):
    html = fragment(client.post(reverse("examples:form"), VALID, headers=HTMX))

    assert "Ada: the solo plan with 1 seat(s)." in html
    assert RE_MESSAGES_SWAPPED.search(html)
    assert "The form is valid; nothing was saved." in html
    assert 'role="status"' in html


def test_the_form_works_without_htmx(client: Client):
    html = page(client.post(reverse("examples:form"), VALID))

    assert "Ada: the solo plan with 1 seat(s)." in html
    assert "hx-swap-oob" not in html


def test_the_table_is_filtered_for_htmx(client: Client):
    url = reverse("examples:index")

    html = fragment(client.get(url, {"q": "blocked"}, headers=HTMX))

    assert element(html, "div", "id", "example-results-container")
    assert rows(html) == ["Set up the staging server", "Review the privacy policy"]
    assert "<nav" in html


def test_the_page_links_keep_the_filter(client: Client):
    url = reverse("examples:index")

    html = fragment(client.get(url, {"q": "e", "page": "2"}, headers=HTMX))

    links = [attrs for attrs in elements(html, "a") if "hx-get" in attrs]
    assert [attrs["hx-get"] for attrs in links][:2] == [
        f"{url}?q=e&page=1",
        f"{url}?q=e&page=2",
    ]
    assert links[0]["href"] == f"{url}?q=e&page=1#example-results"
    assert [attrs["hx-get"] for attrs in links if "aria-current" in attrs] == [
        f"{url}?q=e&page=2",
    ]
    assert all(attrs["hx-push-url"] == "true" for attrs in links)


def test_the_last_page_holds_the_rest(client: Client):
    url = reverse("examples:index")

    first = fragment(client.get(url, headers=HTMX))
    last = fragment(client.get(url, {"page": "3"}, headers=HTMX))

    assert len(rows(first)) == ROWS_PER_PAGE
    assert len(rows(last)) == LAST_PAGE_ROWS


def test_a_filter_that_matches_nothing_says_so(client: Client):
    url = reverse("examples:index")

    html = fragment(client.get(url, {"q": "<zebra>"}, headers=HTMX))

    assert 'No task matches "&lt;zebra&gt;".' in html
    assert rows(html) == []
    assert "<nav" not in html
    assert element(html, "a")["hx-get"] == url


def test_a_page_htmx_restores_is_whole(client: Client):
    # The back button on a page htmx's history no longer holds: HX-Request is set, and
    # htmx puts the answer where the page was, so a fragment would be all that is left
    headers = {**HTMX, "HX-History-Restore-Request": "true"}

    html = page(client.get(reverse("examples:index"), {"page": "2"}, headers=headers))

    assert "hx-swap-oob" not in html
    assert rows(html)[0] == "Order the domain name"


def test_the_filter_works_without_htmx(client: Client):
    html = page(client.get(reverse("examples:index"), {"q": "celebrate"}))

    assert rows(html) == ["Celebrate"]
    assert element(html, "form", "role", "search") is not None


@pytest.mark.parametrize(
    ("data", "state", "is_checked"),
    [({"enabled": "on"}, "on", True), ({}, "off", False)],
)
def test_the_toggle_posts_its_state(client: Client, data, state, is_checked):
    response = client.post(reverse("examples:toggle"), data, headers=HTMX)

    html = fragment(response)
    assert element(html, "form")["id"] == "example-toggle-form"
    toggle = element(html, "input", "name", "enabled")
    assert ("checked" in toggle) is is_checked
    assert f"Notifications are {state}." in html
    assert RE_MESSAGES_SWAPPED.search(html)
    cookie = response.cookies[views.NOTIFICATIONS_COOKIE]
    assert cookie.value == state
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"


def test_the_toggle_works_without_htmx(client: Client):
    response = client.post(reverse("examples:toggle"), {"enabled": "on"})

    assert response.status_code == HTTPStatus.FOUND
    url = f"{reverse('examples:index')}#example-toggle"
    assert response.headers["Location"] == url
    # The cookie the redirect set is what the page reads
    html = page(client.get(reverse("examples:index")))
    assert "checked" in element(html, "input", "name", "enabled")
    assert "Notifications are on." in html


def test_a_tab_is_fetched_when_it_is_chosen(client: Client):
    url = reverse("examples:tabs")

    html = fragment(client.get(url, {"tab": "activity"}, headers=HTMX))

    assert element(html, "div", "role", "tablist") is not None
    tabs = elements(html, "a")
    selected = [attrs for attrs in tabs if attrs["aria-selected"] == "true"]
    assert [attrs["hx-get"] for attrs in selected] == [f"{url}?tab=activity"]
    assert "only this panel came from the server" in html
    assert "A tab is a link" not in html


def test_a_tab_works_without_htmx_and_an_unknown_one_is_the_first(client: Client):
    url = reverse("examples:index")

    chosen = page(client.get(url, {"tab": "settings"}))
    unknown = page(client.get(url, {"tab": "no-such-tab"}))

    assert "marks the tab it rendered as selected" in chosen
    assert "A tab is a link" in unknown


def test_the_tabs_are_slow_under_debug_alone(
    client: Client,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    naps: list[float] = []
    monkeypatch.setattr(time, "sleep", naps.append)
    url = reverse("examples:tabs")

    client.get(url, headers=HTMX)
    assert naps == []
    settings.DEBUG = True
    client.get(url)
    assert naps == []
    client.get(url, headers=HTMX)
    assert naps == [views.DEBUG_DELAY]


def test_the_dialog_comes_from_the_server(client: Client):
    html = fragment(client.get(reverse("examples:modal"), headers=HTMX))

    dialog = element(html, "div", "role", "dialog")
    assert dialog["class"] == "modal modal-open"
    assert dialog["aria-modal"] == "true"
    assert dialog["aria-labelledby"] == element(html, "h3")["id"]
    answers = [attrs["value"] for attrs in elements(html, "button")]
    assert answers == ["cancel", "confirm"]
    assert element(html, "form")["hx-target"] == "#modal"


@pytest.mark.parametrize(("answer", "archived"), [("confirm", True), ("cancel", False)])
def test_an_answer_closes_the_dialog(client: Client, answer, archived):
    data = {"answer": answer}

    html = fragment(client.post(reverse("examples:modal"), data, headers=HTMX))

    # What is left empties the container: the messages go out of band
    assert "modal-open" not in html
    assert RE_MESSAGES_SWAPPED.search(html)
    assert ("Archived, or it would have been." in html) is archived


def test_the_dialog_works_without_htmx(client: Client):
    opened = page(client.get(reverse("examples:modal")))
    response = client.post(reverse("examples:modal"), {"answer": "confirm"})

    assert element(opened, "div", "role", "dialog")["class"] == "modal modal-open"
    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"].endswith("#example-modal")
    after = page(client.get(reverse("examples:index")))
    assert "Archived, or it would have been." in after


@pytest.mark.parametrize(
    ("level", "css_class", "role"),
    [
        ("info", "alert-info", "status"),
        ("success", "alert-success", "status"),
        ("warning", "alert-warning", "alert"),
        ("error", "alert-error", "alert"),
    ],
)
def test_a_notice_arrives_out_of_band(client: Client, level, css_class, role):
    data = {"level": level}

    html = fragment(client.post(reverse("examples:notices"), data, headers=HTMX))

    assert RE_MESSAGES_SWAPPED.search(html)
    alert = element(html, "div", "role", role)
    assert css_class in (alert["class"] or "").split()
    # Nothing but the messages: the form asked for no swap of its own
    assert html.strip().startswith("<div")
    assert "<form" not in html


def test_a_notice_is_chosen_not_written(client: Client):
    url = reverse("examples:notices")

    unknown = client.post(url, {"level": "<script>"}, headers=HTMX)
    plain = client.post(url, {"level": "info"})

    assert unknown.status_code == HTTPStatus.BAD_REQUEST
    assert client.get(url).status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert plain.status_code == HTTPStatus.FOUND
    assert plain.headers["Location"].endswith("#example-notices")


@pytest.mark.parametrize("name", POSTS)
def test_every_post_needs_the_token(name: str):
    client = Client(enforce_csrf_checks=True)

    response = client.post(reverse(name), VALID, headers=HTMX)

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
@pytest.mark.urls("{{ cookiecutter.project_slug }}.examples.tests.urls")
def test_a_project_without_the_page_has_no_link_to_it(client: Client):
    html = page(client.get(reverse("home")))

    assert "Examples" not in html
    assert "/examples/" not in html
