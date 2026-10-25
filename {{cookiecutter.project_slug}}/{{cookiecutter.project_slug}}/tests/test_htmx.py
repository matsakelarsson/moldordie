"""The htmx helpers of ``{{ cookiecutter.project_slug }}/htmx.py``: the mixin on the
fixture page ``tests/urls.py`` routes, without database access, and the login-redirect
middleware on the profile pages."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.responses import fragment
from {{ cookiecutter.project_slug }}.tests.responses import login_redirect
from {{ cookiecutter.project_slug }}.tests.responses import page
from {{ cookiecutter.project_slug }}.tests.urls import AFTER_A_POST

if TYPE_CHECKING:
    from django.test import AsyncClient
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

HTMX_HEADERS = {"HX-Request": "true"}
BOOSTED_HEADERS = {"HX-Request": "true", "HX-Boosted": "true"}
RESTORE_HEADERS = {"HX-Request": "true", "HX-History-Restore-Request": "true"}
MESSAGE = "The post was noted."


@pytest.mark.urls("{{ cookiecutter.project_slug }}.tests.urls")
@pytest.mark.usefixtures("fixture_templates")
class TestHtmxTemplateMixin:
    """The mixin on the fixture page: nothing here may touch the database."""

    def test_a_plain_request_gets_the_page(self, client: Client):
        response = client.get(reverse("htmx_fixture"))

        html = page(response)
        assert element(html, "article")["data-rendering"] == "page"
        assert "HX-Request" in response["Vary"]
        assert "HX-History-Restore-Request" in response["Vary"]

    def test_an_htmx_request_gets_the_partial_and_the_messages(self, client: Client):
        response = client.get(reverse("htmx_fixture"), headers=HTMX_HEADERS)

        html = fragment(response)
        assert element(html, "article")["data-rendering"] == "fragment"
        assert "<h1" not in html
        # The messages follow the partial, so the swap lands first
        assert html.index('id="card"') < html.index('id="messages"')

    def test_a_message_added_during_the_request_rides_along(self, client: Client):
        response = client.post(reverse("htmx_fixture"), headers=HTMX_HEADERS)

        html = fragment(response)
        assert "After the post" in html
        alert = element(html, "div", "role", "status")
        assert "alert-info" in (alert["class"] or "").split()
        assert html.index('id="messages"') < html.index(MESSAGE)

    @pytest.mark.parametrize(
        "headers",
        [BOOSTED_HEADERS, RESTORE_HEADERS],
        ids=["boosted", "history restore"],
    )
    def test_a_boosted_request_and_a_history_restore_get_the_page(
        self,
        client: Client,
        headers: dict[str, str],
    ):
        html = page(client.get(reverse("htmx_fixture"), headers=headers))

        assert element(html, "article")["data-rendering"] == "page"

    def test_a_post_without_htmx_redirects_keeping_its_message(self, client: Client):
        response = client.post(reverse("htmx_fixture"))

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == AFTER_A_POST
        # The message waits for the next page, as after any redirect
        html = page(client.get(reverse("htmx_fixture")))
        assert MESSAGE in html
        assert "Before any post" in html

    def test_a_view_without_a_partial_gives_htmx_the_page(self, client: Client):
        html = page(client.get(reverse("htmx_page_only"), headers=HTMX_HEADERS))

        assert element(html, "article")["data-rendering"] == "page"


@pytest.mark.django_db
class TestHtmxLoginRedirectMiddleware:
    def test_htmx_request_gets_hx_redirect(self, client: Client):
        url = reverse("users:update")

        response = client.get(url, headers=HTMX_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert response["HX-Redirect"] == login_redirect(url)
        assert "Location" not in response
        assert "HX-Request" in response["Vary"]
        assert response.content == b""

    def test_plain_request_keeps_the_redirect(self, client: Client):
        url = reverse("users:update")

        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == login_redirect(url)
        assert "HX-Redirect" not in response
        assert "HX-Request" in response["Vary"]

    def test_boosted_request_keeps_the_redirect(self, client: Client):
        url = reverse("users:update")

        response = client.get(url, headers=BOOSTED_HEADERS)

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == login_redirect(url)
        assert "HX-Redirect" not in response

    def test_other_redirects_are_untouched(self, user: User, client: Client):
        client.force_login(user)

        response = client.post(
            reverse("users:update"),
            {"name": "New Name"},
            headers=HTMX_HEADERS,
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == user.get_absolute_url()
        assert "HX-Redirect" not in response

    def test_async_request_gets_hx_redirect(self, async_client: AsyncClient):
        url = reverse("users:update")

        response = async_to_sync(async_client.get)(url, headers=HTMX_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert response["HX-Redirect"] == login_redirect(url)
