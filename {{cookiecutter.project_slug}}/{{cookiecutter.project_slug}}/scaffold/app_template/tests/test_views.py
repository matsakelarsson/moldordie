"""The app's pages: the list, filtered and paged, one record and the forms that create,
change and delete one, each as a whole page and as the fragment htmx receives; every
one of them needs a signed-in user."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from django.urls import reverse

from {{ cookiecutter.project_slug }}.scaffold.app_template import views
from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item
from {{ cookiecutter.project_slug }}.scaffold.app_template.tests.factories import ItemFactory
from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements
from {{ cookiecutter.project_slug }}.tests.responses import fragment
from {{ cookiecutter.project_slug }}.tests.responses import login_redirect
from {{ cookiecutter.project_slug }}.tests.responses import page

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

HTMX = {"HX-Request": "true"}
# The model's names, as the pages spell them
OPTS = Item._meta  # noqa: SLF001
RE_ROW_LINK = re.compile(r'<a class="link" href="[^"]+">([^<]+)</a>')


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def rows(html: str) -> list[str]:
    """The names in the table, in order."""
    return RE_ROW_LINK.findall(html)


def delete_url(item: Item) -> str:
    return reverse("app_template:delete", kwargs={"pk": item.pk})


def test_every_page_needs_a_signed_in_user(client: Client):
    item = ItemFactory.create()
    urls = [
        reverse("app_template:list"),
        reverse("app_template:create"),
        item.get_absolute_url(),
        reverse("app_template:update", kwargs={"pk": item.pk}),
        delete_url(item),
    ]

    for url in urls:
        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND, url
        assert response["Location"] == login_redirect(url)


def test_the_list_shows_the_records_newest_first(signed_in: Client):
    ItemFactory.create(name="First")
    second = ItemFactory.create(name="Second")

    html = page(signed_in.get(reverse("app_template:list")))

    assert rows(html) == ["Second", "First"]
    assert element(html, "form", "role", "search")["hx-target"] == "#item-results"
    hrefs = [attrs["href"] for attrs in elements(html, "a")]
    assert second.get_absolute_url() in hrefs
    assert reverse("app_template:create") in hrefs


def test_the_list_is_filtered_for_htmx(signed_in: Client):
    ItemFactory.create(name="Apple")
    ItemFactory.create(name="Banana")

    url = reverse("app_template:list")

    html = fragment(signed_in.get(url, {"q": "ban"}, headers=HTMX))

    assert element(html, "div", "id", "item-results")
    assert rows(html) == ["Banana"]


def test_an_empty_list_and_a_filter_that_matches_nothing_say_so(signed_in: Client):
    url = reverse("app_template:list")

    empty = page(signed_in.get(url))
    ItemFactory.create(name="Apple")
    unmatched = fragment(signed_in.get(url, {"q": "<zebra>"}, headers=HTMX))

    assert f"No {OPTS.verbose_name} yet." in empty
    assert f'No {OPTS.verbose_name} matches "&lt;zebra&gt;".' in unmatched
    assert rows(unmatched) == []
    assert element(unmatched, "a")["hx-get"] == url


def test_the_page_links_keep_the_filter(signed_in: Client):
    ItemFactory.create_batch(views.PER_PAGE + 1)
    url = reverse("app_template:list")

    html = fragment(signed_in.get(url, {"q": "item", "page": "2"}, headers=HTMX))

    assert len(rows(html)) == 1
    links = [attrs for attrs in elements(html, "a") if "hx-get" in attrs]
    assert links[0]["hx-get"] == f"{url}?q=item&page=1"
    current = [a["hx-get"] for a in links if "aria-current" in a]
    assert current == [f"{url}?q=item&page=2"]
    assert all(attrs["hx-push-url"] == "true" for attrs in links)


def test_a_record_is_shown_as_a_page_and_as_its_card(signed_in: Client):
    item = ItemFactory.create(name="Apple", notes="Green")

    whole = page(signed_in.get(item.get_absolute_url()))
    card = fragment(signed_in.get(item.get_absolute_url(), headers=HTMX))

    for html in (whole, card):
        assert element(html, "article")["id"] == "item-card"
        assert "Green" in html
    edit = element(card, "a", "hx-target", "#item-card")
    assert edit["hx-get"] == reverse("app_template:update", kwargs={"pk": item.pk})
    assert element(card, "a", "hx-target", "#modal")["href"] == delete_url(item)


@pytest.mark.parametrize("header", ["HX-Boosted", "HX-History-Restore-Request"])
def test_a_boosted_request_and_a_restored_page_are_whole(signed_in: Client, header):
    item = ItemFactory.create()

    response = signed_in.get(item.get_absolute_url(), headers={**HTMX, header: "true"})

    assert element(page(response), "article")["id"] == "item-card"


def test_a_record_is_created_from_the_form(signed_in: Client):
    url = reverse("app_template:create")

    # The page has the theme picker's form too; the record's posts to its own address
    form = element(page(signed_in.get(url)), "form", "hx-post", url)
    data = {"name": "Apple", "notes": ""}
    response = signed_in.post(url, data, headers=HTMX, follow=True)

    assert form["hx-target"] == "#item-card"
    item = Item.objects.get()
    assert response.redirect_chain == [(item.get_absolute_url(), HTTPStatus.FOUND)]
    html = fragment(response)
    assert element(html, "article")["id"] == "item-card"
    assert "Apple was created." in html


def test_an_invalid_form_comes_back_with_its_errors(signed_in: Client):
    url = reverse("app_template:create")

    html = fragment(signed_in.post(url, {"name": ""}, headers=HTMX))

    invalid = [a["name"] for a in elements(html, "input") if "aria-invalid" in a]
    assert invalid == ["name"]
    assert not Item.objects.exists()


def test_a_record_is_changed_from_the_form(signed_in: Client):
    item = ItemFactory.create(name="Apple")
    url = reverse("app_template:update", kwargs={"pk": item.pk})

    response = signed_in.post(url, {"name": "Pear", "notes": "Ripe"})

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == item.get_absolute_url()
    item.refresh_from_db()
    assert (item.name, item.notes) == ("Pear", "Ripe")
    assert "Pear was saved." in page(signed_in.get(item.get_absolute_url()))


def test_the_deletion_is_confirmed_in_a_dialog(signed_in: Client):
    item = ItemFactory.create(name="Apple")

    dialog = fragment(signed_in.get(delete_url(item), headers=HTMX))
    whole = page(signed_in.get(delete_url(item)))

    assert "open" in element(dialog, "dialog")
    assert element(dialog, "form", "method", "post")["hx-post"] == delete_url(item)
    assert element(dialog, "form", "method", "dialog")
    # The record stays under the dialog on the whole page
    assert element(whole, "article")["id"] == "item-card"
    assert Item.objects.filter(pk=item.pk).exists()


def test_a_record_is_deleted_and_the_browser_sent_to_the_list(signed_in: Client):
    item = ItemFactory.create(name="Apple")

    response = signed_in.post(delete_url(item), headers=HTMX)

    assert response.status_code == HTTPStatus.OK
    assert response["HX-Redirect"] == reverse("app_template:list")
    assert not Item.objects.filter(pk=item.pk).exists()
    assert "Apple was deleted." in page(signed_in.get(reverse("app_template:list")))


def test_a_deletion_without_htmx_redirects_to_the_list(signed_in: Client):
    item = ItemFactory.create()

    response = signed_in.post(delete_url(item))

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == reverse("app_template:list")
    assert not Item.objects.filter(pk=item.pk).exists()


def test_every_post_needs_the_token(user: User):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    item = ItemFactory.create()
    urls = [
        reverse("app_template:create"),
        reverse("app_template:update", kwargs={"pk": item.pk}),
        delete_url(item),
    ]

    for url in urls:
        response = client.post(url, {"name": "Apple"}, headers=HTMX)

        assert response.status_code == HTTPStatus.FORBIDDEN, url
