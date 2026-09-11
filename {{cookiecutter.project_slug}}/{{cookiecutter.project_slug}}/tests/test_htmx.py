"""Tests for the htmx helpers in ``{{ cookiecutter.project_slug }}/htmx.py``."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.urls import reverse

if TYPE_CHECKING:
    from django.test import AsyncClient
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

HTMX_HEADERS = {"HX-Request": "true"}
BOOSTED_HEADERS = {"HX-Request": "true", "HX-Boosted": "true"}


def login_redirect(next_url: str) -> str:
    return f"{reverse(settings.LOGIN_URL)}?next={next_url}"


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
