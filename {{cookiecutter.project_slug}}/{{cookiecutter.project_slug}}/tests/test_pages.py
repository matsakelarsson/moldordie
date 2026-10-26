"""The starter pages, the sidebar and the bar every page carries, and the account menu
the pages of the signed-in user's own account add to the sidebar."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements
from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db
SIDEBAR_AND_HERO = 2


def links(html):
    """The ``href`` of every link, by the text of its ``id`` where it has one."""
    return [attrs for attrs in elements(html, "a") if "id" in attrs]


def sidebar_links(html):
    """Every link of the sidebar in order: its ``href``, and whether it is the page."""
    nav = html.partition('aria-label="Main navigation"')[2].partition("</nav>")[0]
    return [(attrs["href"], "aria-current" in attrs) for attrs in elements(nav, "a")]


def current(html):
    return [href for href, is_current in sidebar_links(html) if is_current]


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


def test_an_account_page_adds_the_account_menu_to_the_sidebar(client, user):
    # A visitor's entrance page and a signed-in user's page of the site: the pages alone
    entrance = client.get(reverse("account_login")).content.decode()
    client.force_login(user)
    about = client.get(reverse("about")).content.decode()
    pages = [href for href, _ in sidebar_links(about)]
    assert [href for href, _ in sidebar_links(entrance)] == pages
    assert reverse("account_email") not in about

    # A page of the account: the menu after the pages, the page itself marked
    account = [
        user.get_absolute_url(),
        reverse("account_email"),
        reverse("account_change_password"),
        reverse("mfa_index"),
        {%- if cookiecutter.identity_provider != "none" %}
        # The connections page, since the project has a provider to connect
        reverse("socialaccount_connections"),
        {%- endif %}
        reverse("account_logout"),
    ]
    email = client.get(reverse("account_email")).content.decode()
    assert [href for href, _ in sidebar_links(email)] == [*pages, *account]
    assert current(email) == [reverse("account_email")]
    two_factor = client.get(reverse("mfa_index")).content.decode()
    assert current(two_factor) == [reverse("mfa_index")]
    sign_out = client.get(reverse("account_logout")).content.decode()
    assert current(sign_out) == [reverse("account_logout")]

    # The profile and its form are pages of the account; another user's profile is not
    for url in (user.get_absolute_url(), reverse("users:update")):
        html = client.get(url).content.decode()
        assert [href for href, _ in sidebar_links(html)] == [*pages, *account]
        assert current(html) == [user.get_absolute_url()]
    other = client.get(UserFactory.create().get_absolute_url()).content.decode()
    assert [href for href, _ in sidebar_links(other)] == pages
