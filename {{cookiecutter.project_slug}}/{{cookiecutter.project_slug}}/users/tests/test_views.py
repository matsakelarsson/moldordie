from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.template.base import PartialTemplate
from django.test import Client
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from {{ cookiecutter.project_slug }}.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

HTMX_HEADERS = {"HX-Request": "true"}
# The messages container marked for htmx's out-of-band swap
RE_MESSAGES_SWAPPED = re.compile(rb'<div[^>]*\bid="messages"[^>]*\bhx-swap-oob="true"')


def template_names(response) -> list[str]:
    """Names of the rendered templates; partials read as ``"<template>#<partial>"``."""
    names = []
    for template in response.templates:
        if isinstance(template, PartialTemplate):
            # Loaders record a str name; the stub also allows bytes and None
            template_name = template.origin.template_name
            assert isinstance(template_name, str)
            names.append(f"{template_name}#{template.name}")
        elif template.name:
            names.append(template.name)
    return names


def login_redirect(next_url: str) -> str:
    return f"{reverse(settings.LOGIN_URL)}?next={next_url}"


def assert_fragment(content: bytes) -> None:
    """Content for the target only: no page, no script, no style, no stylesheet."""
    lowered = content.lower()
    assert b"<html" not in lowered
    assert b"<script" not in lowered
    assert b"<style" not in lowered
    assert b"<link" not in lowered


class TestUserUpdateView:
    def test_get_full_page(self, user: User, client: Client):
        client.force_login(user)

        response = client.get(reverse("users:update"))

        assert response.status_code == HTTPStatus.OK
        assert template_names(response)[0] == "users/user_form.html"
        assert b"<html" in response.content
        assert b'id="user-profile"' in response.content

    def test_get_htmx_partial(self, user: User, client: Client):
        client.force_login(user)

        response = client.get(reverse("users:update"), headers=HTMX_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert template_names(response)[0] == "users/user_form.html#profile"
        assert "base.html" not in template_names(response)
        assert_fragment(response.content)
        assert b'id="user-profile"' in response.content
        assert "HX-Request" in response["Vary"]

    def test_post_without_csrf_token_is_forbidden(self, user: User):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        client.get(reverse("users:update"))  # sets the CSRF cookie

        response = client.post(
            reverse("users:update"),
            {"name": "New Name"},
            headers=HTMX_HEADERS,
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        user.refresh_from_db()
        assert user.name != "New Name"

    def test_post_with_csrf_header(self, user: User):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        page = client.get(reverse("users:update"))
        # The token htmx sends comes from the hx-headers attribute on <body>
        match = re.search(r'"X-CSRFToken": "([^"]+)"', page.content.decode())
        assert match

        response = client.post(
            reverse("users:update"),
            {"name": "New Name"},
            headers={**HTMX_HEADERS, "X-CSRFToken": match.group(1)},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == user.get_absolute_url()
        user.refresh_from_db()
        assert user.name == "New Name"

    def test_htmx_post_redirects_to_detail_partial(self, user: User, client: Client):
        client.force_login(user)

        response = client.post(
            reverse("users:update"),
            {"name": "New Name"},
            headers=HTMX_HEADERS,
            follow=True,
        )

        assert response.redirect_chain == [(user.get_absolute_url(), HTTPStatus.FOUND)]
        assert template_names(response)[0] == "users/user_detail.html#profile"
        assert "base.html#messages" in template_names(response)
        assert_fragment(response.content)
        assert RE_MESSAGES_SWAPPED.search(response.content)
        assert str(_("Information successfully updated")).encode() in response.content
        # The message arrives after the page loaded: announced, and dismissible
        assert b'role="status"' in response.content
        assert b"data-ui-dismiss" in response.content

    def test_not_authenticated(self, client: Client):
        url = reverse("users:update")

        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == login_redirect(url)


class TestUserRedirectView:
    def test_redirects_to_the_profile(self, user: User, client: Client):
        client.force_login(user)

        response = client.get(reverse("users:redirect"))

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == user.get_absolute_url()

    def test_not_authenticated(self, client: Client):
        url = reverse("users:redirect")

        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == login_redirect(url)


class TestUserDetailView:
    def test_full_page(self, user: User, client: Client):
        client.force_login(user)

        response = client.get(user.get_absolute_url())

        assert response.status_code == HTTPStatus.OK
        assert template_names(response)[0] == "users/user_detail.html"
        assert b"<html" in response.content
        assert b'id="user-profile"' in response.content
        assert response.content.count(b'id="messages"') == 1

    def test_htmx_partial(self, user: User, client: Client):
        client.force_login(user)

        response = client.get(user.get_absolute_url(), headers=HTMX_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert template_names(response)[0] == "users/user_detail.html#profile"
        assert "base.html" not in template_names(response)
        assert_fragment(response.content)
        assert b'id="user-profile"' in response.content
        assert "HX-Request" in response["Vary"]

    def test_boosted_request_gets_the_full_page(self, user: User, client: Client):
        client.force_login(user)

        headers = {**HTMX_HEADERS, "HX-Boosted": "true"}
        response = client.get(user.get_absolute_url(), headers=headers)

        assert response.status_code == HTTPStatus.OK
        assert template_names(response)[0] == "users/user_detail.html"
        assert b"<html" in response.content
        assert b"hx-swap-oob" not in response.content
        assert response.content.count(b'id="messages"') == 1

    def test_not_authenticated(self, user: User, client: Client):
        url = user.get_absolute_url()

        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == login_redirect(url)

    def test_nameless_user_is_shown_without_the_address(self, client: Client):
        # Every signed-in user can view a profile: the address must not be the fallback
        nameless = UserFactory.create(email="hidden@example.com", name="")
        client.force_login(UserFactory.create())

        response = client.get(nameless.get_absolute_url())

        assert response.status_code == HTTPStatus.OK
        assert f"<h1>{nameless.display_name}</h1>".encode() in response.content
        assert b"hidden@example.com" not in response.content
    {%- if cookiecutter.username_type == "username" %}

    def test_named_user_keeps_the_username_as_a_sub_line(self, client: Client):
        user = UserFactory.create(name="Ann Lee")
        client.force_login(user)

        response = client.get(user.get_absolute_url())

        assert b"<h1>Ann Lee</h1>" in response.content
        assert f"<p>{user.username}</p>".encode() in response.content

    def test_nameless_user_shows_the_username_once(self, client: Client):
        user = UserFactory.create(name="")
        client.force_login(user)

        response = client.get(user.get_absolute_url())

        assert f"<h1>{user.username}</h1>".encode() in response.content
        assert f"<p>{user.username}</p>".encode() not in response.content
    {%- endif %}
