"""The starter pages and the navigation bar every page carries."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements

pytestmark = pytest.mark.django_db


def links(html):
    """The ``href`` of every link, by the text of its ``id`` where it has one."""
    return [attrs for attrs in elements(html, "a") if "id" in attrs]


def test_the_home_page_invites_a_visitor_to_sign_in(client):
    response = client.get(reverse("home"))

    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert element(html, "h1") == {"class": "text-4xl font-bold"}
    assert element(html, "nav")["aria-label"] == "Main navigation"
    # The page links are written once and rendered twice, the account links once
    assert [attrs["id"] for attrs in links(html)] == ["sign-up-link", "log-in-link"]
    assert html.count(f'href="{reverse("about")}"') > 1
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
