"""The showcase: absent without DEBUG, every component with its contract, example and
source, the sample form, the paged results and the theme preview.

The tests run without DEBUG, so those of the page itself use ``ui/tests/urls.py``.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils.html import escape

from {{ cookiecutter.project_slug }}.ui.palettes import PALETTES
from {{ cookiecutter.project_slug }}.ui.showcase import COMPONENTS
from {{ cookiecutter.project_slug }}.ui.showcase import EXAMPLES
from {{ cookiecutter.project_slug }}.ui.showcase import component_contract
from {{ cookiecutter.project_slug }}.ui.showcase import example_source
from {{ cookiecutter.project_slug }}.ui.tests.markup import element
from {{ cookiecutter.project_slug }}.ui.tests.markup import elements
from {{ cookiecutter.project_slug }}.ui.themes import PREVIEW_SESSION_KEY

if TYPE_CHECKING:
    from django.test import Client

HTMX = {"HX-Request": "true"}
SAMPLE = {"name": "Ada", "plan": "team", "seats": "3", "terms": "on"}
# The messages container marked for htmx's out-of-band swap
RE_MESSAGES_SWAPPED = re.compile(r'<div[^>]*\bid="messages"[^>]*\bhx-swap-oob="true"')
with_showcase = pytest.mark.urls("{{ cookiecutter.project_slug }}.ui.tests.urls")


def assert_fragment(html: str) -> None:
    """Content for the target only: no page, no script, no style, no stylesheet."""
    for tag in ("<html", "<script", "<style", "<link"):
        assert tag not in html.lower()


def inputs(html: str, name: str) -> list[dict[str, str | None]]:
    return [attrs for attrs in elements(html, "input") if attrs.get("name") == name]


def test_the_tags_read_only_what_the_showcase_names():
    assert example_source("badge").startswith('<div class="ui-actions">')
    assert component_contract("badge").startswith("A short status label")
    with pytest.raises(ValueError, match="not an example"):
        example_source("../../base")
    with pytest.raises(ValueError, match="not a component"):
        component_contract("../base")


@pytest.mark.django_db
def test_without_debug_there_is_no_showcase(client: Client):
    with pytest.raises(NoReverseMatch):
        reverse("showcase:index")

    assert client.get("/ui/components/").status_code == HTTPStatus.NOT_FOUND
    assert b"Components" not in client.get(reverse("home")).content


@with_showcase
@pytest.mark.django_db
class TestShowcase:
    def test_every_component_with_its_contract_and_source(self, client: Client):
        url = reverse("showcase:index")

        response = client.get(url)

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert "<c-" not in html
        for name in COMPONENTS:
            assert escape(component_contract(name)) in html
        for name in EXAMPLES:
            assert escape(example_source(name)) in html
        (link,) = [attrs for attrs in elements(html, "a") if attrs.get("href") == url]
        assert link["aria-current"] == "page"

    def test_an_invalid_sample_comes_back_with_its_errors(self, client: Client):
        response = client.post(
            reverse("showcase:index"),
            {"plan": "team", "seats": "1"},
            headers=HTMX,
        )

        assert response.status_code == HTTPStatus.OK
        assert "HX-Request" in response["Vary"]
        html = response.content.decode()
        assert_fragment(html)
        assert html.count('id="showcase-sample"') == 1
        (name,) = inputs(html, "name")
        assert name["aria-invalid"] == "true"
        assert "A team plan needs at least two seats." in html

    def test_a_valid_sample_shows_its_result_and_a_message(self, client: Client):
        response = client.post(reverse("showcase:index"), SAMPLE, headers=HTMX)

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert_fragment(html)
        assert "Ada chose the Team plan; seats: 3." in html
        assert RE_MESSAGES_SWAPPED.search(html)
        assert 'role="status"' in html
        assert "nothing was saved" in html

    def test_the_sample_form_works_without_javascript(self, client: Client):
        url = reverse("showcase:index")

        invalid = client.post(url, {"name": "Ada"})
        valid = client.post(url, SAMPLE)

        assert invalid.status_code == HTTPStatus.OK
        assert "<html" in invalid.content.decode()
        (terms,) = inputs(invalid.content.decode(), "terms")
        assert terms["aria-invalid"] == "true"
        assert valid.status_code == HTTPStatus.OK
        assert "Ada chose the Team plan; seats: 3." in valid.content.decode()
        assert b"hx-swap-oob" not in valid.content

    def test_the_results_page_through_htmx(self, client: Client):
        url = reverse("showcase:index")

        response = client.get(url, {"page": "2"}, headers=HTMX)

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert_fragment(html)
        assert html.count('id="showcase-results"') == 1
        (current,) = [attrs for attrs in elements(html, "a") if "aria-current" in attrs]
        assert current["href"] == f"{url}?page=2#showcase-pagination"
        assert current["hx-get"] == current["href"]
        assert current["hx-target"] == "#showcase-results"
        assert "Sample task 4" in html

    def test_a_filter_keeps_its_query_and_can_match_nothing(self, client: Client):
        url = reverse("showcase:index")

        blocked = client.get(url, {"q": "blocked"}, headers=HTMX).content.decode()
        nothing = client.get(url, {"q": "no such task"}, headers=HTMX).content.decode()

        links = [attrs["href"] for attrs in elements(blocked, "a")]
        assert f"{url}?q=blocked&page=2#showcase-pagination" in links
        assert "Sample task 9" in blocked
        assert "Sample task 3" not in blocked
        assert "No tasks match" in nothing
        assert "no such task" in nothing

    def test_a_preview_applies_to_the_session_until_reset(
        self,
        client: Client,
        settings,
    ):
        settings.DEBUG = True
        accent = "#0b57d0"

        stored = client.post(
            reverse("showcase:preview"),
            {"palette": "teal", "mode": "dark", "light_accent": accent},
        )

        assert stored.status_code == HTTPStatus.FOUND
        assert stored["Location"] == f"{reverse('showcase:index')}#showcase-theme"
        assert client.session[PREVIEW_SESSION_KEY] == {
            "palette": "teal",
            "mode": "dark",
            "light": {"accent": accent},
            "dark": {},
        }
        css = client.get(reverse("ui:theme")).content.decode()
        assert f"--ui-accent:{accent};" in css
        hover = PALETTES["teal"]["light"]["accent-hover"]
        assert f"--ui-accent-hover:{hover};" in css
        page = client.get(reverse("showcase:index")).content.decode()
        assert element(page, "html")["data-ui-mode"] == "dark"

        reset = client.post(reverse("showcase:reset"))

        assert reset.status_code == HTTPStatus.FOUND
        assert PREVIEW_SESSION_KEY not in client.session
        css = client.get(reverse("ui:theme")).content.decode()
        assert f"--ui-accent:{accent};" not in css

    def test_an_invalid_preview_leaves_the_theme(self, client: Client, settings):
        settings.DEBUG = True
        url = reverse("showcase:preview")
        theme = {"palette": "blue", "mode": "system"}

        colour = client.post(url, {**theme, "light_bg": "white"})
        contrast = client.post(url, {**theme, "dark_fg": "#1a1f2a"})

        assert colour.status_code == HTTPStatus.OK
        assert "Enter a colour as #RRGGBB." in colour.content.decode()
        assert contrast.status_code == HTTPStatus.OK
        expected = "dark: fg on surface is 1.00:1, below 4.5:1 for text"
        assert expected in contrast.content.decode()
        assert PREVIEW_SESSION_KEY not in client.session
        # The page links go to the showcase, not to the preview the form posted to
        links = [attrs["href"] for attrs in elements(contrast.content.decode(), "a")]
        assert f"{reverse('showcase:index')}?page=2#showcase-pagination" in links

    def test_the_preview_takes_a_post_only(self, client: Client):
        preview = client.get(reverse("showcase:preview"))
        reset = client.get(reverse("showcase:reset"))

        assert preview.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert reset.status_code == HTTPStatus.METHOD_NOT_ALLOWED
