"""The starter pages, and the sidebar and the bar every page carries."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements

pytestmark = pytest.mark.django_db
SIDEBAR_AND_HERO = 2


def links(html):
    """The ``href`` of every link, by the text of its ``id`` where it has one."""
    return [attrs for attrs in elements(html, "a") if "id" in attrs]


def test_the_home_page_invites_a_visitor_to_sign_in(client):
    response = client.get(reverse("home"))

    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert element(html, "h1") == {"class": "text-4xl font-bold"}
    assert element(html, "nav")["aria-label"] == "Main navigation"
    # The pages are in the sidebar, a drawer on a checkbox that the bar's menu button
    # and the overlay check; the account links are in the bar
    assert element(html, "input", "id", "sidebar")["class"] == "drawer-toggle"
    labels = [a for a in elements(html, "label") if a.get("for") == "sidebar"]
    assert [attrs["class"] for attrs in labels] == [
        "btn btn-ghost btn-square drawer-button",
        "drawer-overlay",
    ]
    assert [attrs["id"] for attrs in links(html)] == ["sign-up-link", "log-in-link"]
    # Once in the sidebar, and once more where the hero links to it
    assert html.count(f'href="{reverse("about")}"') == SIDEBAR_AND_HERO
    current = [attrs for attrs in elements(html, "a") if "aria-current" in attrs]
    assert {attrs["href"] for attrs in current} == {reverse("home")}


def test_the_navigation_of_a_closed_registration(client, settings):
    settings.ACCOUNT_ALLOW_REGISTRATION = False

    html = client.get(reverse("home")).content.decode()

    assert [attrs["id"] for attrs in links(html)] == ["log-in-link"]
    assert reverse("account_signup") not in html


def test_the_navigation_of_a_signed_in_user(client, user):
    client.force_login(user)

    html = client.get(reverse("about")).content.decode()

    assert links(html) == []
    hrefs = [attrs["href"] for attrs in elements(html, "a")]
    assert user.get_absolute_url() in hrefs
    assert reverse("account_logout") in hrefs
    assert reverse("account_login") not in hrefs
    # prose, from Tailwind's typography plugin, styles the running text
    assert element(html, "article") == {"class": "prose max-w-none"}
