"""Tests for the Content Security Policy configured in ``config/settings/base.py``."""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User

pytestmark = pytest.mark.django_db

RE_NONCE = re.compile(r"'nonce-([A-Za-z0-9_-]+)'")
RE_HTMX_CONFIG = re.compile(r'<meta name="htmx-config"\s+content=\'([^\']+)\'')


def test_pages_send_a_nonce_based_policy(client: Client):
    response = client.get(reverse("home"))

    assert response.status_code == HTTPStatus.OK
    policy = response["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy
    match = RE_NONCE.search(policy)
    assert match, policy
    # The htmx script tag rendered by django-htmx carries the nonce
    assert f'nonce="{match.group(1)}"'.encode() in response.content


def test_htmx_is_configured_for_the_policy(client: Client):
    response = client.get(reverse("home"))

    match = RE_HTMX_CONFIG.search(response.content.decode())
    assert match, "htmx-config meta tag missing"
    assert json.loads(match.group(1)) == {
        "allowEval": False,
        "allowScriptTags": False,
        "includeIndicatorStyles": False,
    }


def test_htmx_fragments_send_the_policy(user: User, client: Client):
    client.force_login(user)

    response = client.get(user.get_absolute_url(), headers={"HX-Request": "true"})

    assert response.status_code == HTTPStatus.OK
    assert "script-src 'self'" in response["Content-Security-Policy"]
{%- if cookiecutter.rest_api == 'DRF' %}


def test_api_docs_are_exempt_from_the_policy(admin_client: Client):
    response = admin_client.get(reverse("api-docs"))

    assert response.status_code == HTTPStatus.OK
    assert "Content-Security-Policy" not in response
{%- elif cookiecutter.rest_api == 'Django Ninja' %}


def test_api_docs_use_local_swagger_assets(admin_client: Client):
    response = admin_client.get(reverse("api:openapi-view"))

    assert response.status_code == HTTPStatus.OK
    assert b"cdn.jsdelivr.net" not in response.content
    assert b"ninja/swagger-ui-bundle.js" in response.content
{%- endif %}
