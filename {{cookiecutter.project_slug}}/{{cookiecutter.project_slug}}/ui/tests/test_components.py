"""The components render ordinary HTML: variants, slots, states and forwarding.

Each test renders a page under ``templates/tests/`` that calls the component, so
Cotton's compiler and loader run as they do in the project.
"""

import pytest
from django.core.paginator import Paginator
from django.template.loader import render_to_string

from {{ cookiecutter.project_slug }}.ui.tests.markup import element
from {{ cookiecutter.project_slug }}.ui.tests.markup import elements

pytestmark = pytest.mark.usefixtures("fixture_templates")

HTMX = {"hx-target": "#items", "hx-swap": "outerHTML", "hx-push-url": "true"}


def render(rf, name, **context):
    return render_to_string(f"tests/{name}.html", context, request=rf.get("/"))


def test_button_variants_sizes_and_forwarding(rf):
    html = render(rf, "button", count=0)
    plain, save, delete, quiet, bogus = elements(html, "button")
    assert plain == {"type": "button", "class": "ui-button ui-button-primary"}
    assert save == {
        "type": "submit",
        "class": "ui-button ui-button-secondary ui-button-small",
        "id": "save",
        "disabled": None,
    }
    assert delete == {
        "type": "button",
        "class": "ui-button ui-button-danger extra",
        "data-count": "0",
    }
    assert quiet["class"] == "ui-button ui-button-quiet"
    # An unknown variant or size gets the default
    assert bogus["class"] == "ui-button ui-button-primary"
    assert "Go" in html


def test_link_appearances(rf):
    html = render(rf, "link", url="https://example.com/?a=1&b=2")
    about, go, bogus = elements(html, "a")
    assert about == {"href": "/about/", "class": "ui-link"}
    assert go == {
        "href": "https://example.com/?a=1&b=2",
        "class": "ui-button ui-button-secondary ui-button-small",
        "hx-get": "/about/",
    }
    assert bogus["class"] == "ui-button ui-button-primary extra"
    assert "role" not in go


def test_a_link_needs_its_href(rf):
    with pytest.raises(ValueError, match="URL is empty"):
        render(rf, "link_missing")


def test_card_slots(rf):
    html = render(rf, "card", show_actions=False)
    full, plain, conditional = html.split("<article")[1:]
    assert elements(html, "article") == [
        {"class": "ui-card", "id": "full"},
        {"class": "ui-card plain"},
        {"class": "ui-card", "id": "conditional"},
    ]
    assert element(full, "header") == {"class": "ui-card-header"}
    assert "<h2>Title</h2>" in full
    assert element(full, "footer") == {"class": "ui-card-actions ui-actions"}
    assert element(full, "button")["class"] == "ui-button ui-button-primary"
    assert elements(plain, "header") == elements(plain, "footer") == []
    assert element(plain, "div") == {"class": "ui-card-body"}
    # A slot inside a template condition is there only when the condition holds
    assert elements(conditional, "footer") == []
    shown = render(rf, "card", show_actions=True).split("<article")[3]
    assert element(shown, "footer") == {"class": "ui-card-actions ui-actions"}


def test_alert_levels_title_dismissal_and_announcement(rf):
    html = render(rf, "alert")
    alerts = [attrs for attrs in elements(html, "div") if "data-ui-alert" in attrs]
    info, success, error, debug, warning = alerts
    assert info == {"class": "ui-alert ui-alert-info", "data-ui-alert": None}
    assert success == {
        "class": "ui-alert ui-alert-success",
        "data-ui-alert": None,
        "role": "status",
    }
    assert error == {
        "class": "ui-alert ui-alert-error",
        "data-ui-alert": None,
        "role": "alert",
    }
    # Django's debug level and an unknown level read as info
    assert debug["class"] == "ui-alert ui-alert-info"
    assert warning == {
        "class": "ui-alert ui-alert-warning extra",
        "data-ui-alert": None,
        "id": "warned",
    }
    assert '<p class="ui-alert-title">Saved</p>' in html
    assert element(html, "button") == {
        "type": "button",
        "class": "ui-alert-dismiss",
        "data-ui-dismiss": None,
        "aria-label": "Dismiss",
    }


def test_badge_levels(rf):
    html = render(rf, "badge", title='T "q" <x>')
    badges = elements(html, "span")
    assert [badge["class"] for badge in badges] == [
        "ui-badge ui-badge-neutral",
        "ui-badge ui-badge-info",
        "ui-badge ui-badge-success",
        "ui-badge ui-badge-warning",
        "ui-badge ui-badge-error extra",
        "ui-badge ui-badge-neutral",
    ]
    assert badges[2]["title"] == 'T "q" <x>'


def test_table_slots(rf):
    html = render(rf, "table")
    people, bare = html.split("</table>")[:2]
    assert elements(html, "table") == [
        {"class": "ui-table", "id": "people"},
        {"class": "ui-table"},
    ]
    assert elements(html, "div") == [{"class": "ui-table-scroll"}] * 2
    assert "<caption>People</caption>" in people
    assert element(people, "thead") == {}
    assert "<th>Name</th>" in people
    assert element(people, "tbody") == {}
    assert elements(bare, "thead") == []
    assert element(bare, "tbody") == {}


def test_pagination(rf):
    paginator = Paginator(range(30), 10)
    page_urls = [
        (1, "/items/?page=1"),
        (2, "/items/?page=2"),
        ("…", ""),
        (3, "/items/?page=3"),
    ]
    html = render(
        rf,
        "pagination",
        page=paginator.page(2),
        first=paginator.page(1),
        page_urls=page_urls,
    )
    plain, targeted, first = html.split("</nav>")[:3]
    assert elements(html, "nav") == [
        {"class": "ui-pagination", "aria-label": "Pagination"},
        {"class": "ui-pagination", "aria-label": "Items", "id": "paged"},
        {"class": "ui-pagination", "aria-label": "Pagination"},
    ]

    # Without page URLs: previous and next, and the page's position as text
    assert elements(plain, "a") == [
        {"class": "ui-pagination-link", "rel": "prev", "href": "/items/?page=1"},
        {"class": "ui-pagination-link", "rel": "next", "href": "/items/?page=3"},
    ]
    assert "Page 2 of 3" in plain
    assert 'aria-current="page"' in plain

    # With page URLs and a target: every link also asks htmx to replace the target
    links = elements(targeted, "a")
    assert [link["href"] for link in links] == [
        "/items/?page=1",
        "/items/?page=1",
        "/items/?page=2",
        "/items/?page=3",
        "/items/?page=3",
    ]
    for link in links:
        assert link["hx-get"] == link["href"]
        assert {name: link[name] for name in HTMX} == HTMX
    assert [link for link in links if "aria-current" in link] == [
        {
            "class": "ui-pagination-link ui-pagination-current",
            "aria-current": "page",
            "href": "/items/?page=2",
            "hx-get": "/items/?page=2",
            **HTMX,
        },
    ]
    assert element(targeted, "span") == {
        "class": "ui-pagination-ellipsis",
        "aria-hidden": "true",
    }

    # On the first page the previous control is text, not a link
    assert element(first, "span") == {
        "class": "ui-pagination-link ui-pagination-unavailable",
        "aria-disabled": "true",
    }
    assert [link["rel"] for link in elements(first, "a")] == ["next"]


def test_an_htmx_destination_stays_on_this_origin(rf):
    page = Paginator(range(30), 10).page(2)
    with pytest.raises(ValueError, match="names a scheme"):
        render(rf, "pagination_remote", page=page)


def test_empty_state(rf):
    html = render(rf, "empty_state")
    full, bare = html.split('<div class="ui-empty-state"')[1:]
    roots = [a for a in elements(html, "div") if a["class"] == "ui-empty-state"]
    assert roots == [
        {"class": "ui-empty-state", "id": "empty"},
        {"class": "ui-empty-state"},
    ]
    assert '<p class="ui-empty-state-title">Nothing yet</p>' in full
    assert "No items match." in full
    assert element(full, "a") == {
        "href": "/new/",
        "class": "ui-button ui-button-primary",
    }
    assert [a["class"] for a in elements(bare, "div")] == ["ui-empty-state-body"]
