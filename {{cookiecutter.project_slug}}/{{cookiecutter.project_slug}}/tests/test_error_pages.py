"""The error pages: daisyUI heroes on base.html that render without the database.

The tests carry no django_db mark, so a query while rendering fails them.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.test import Client
from django.views.defaults import permission_denied
from django.views.defaults import server_error

if TYPE_CHECKING:
    from django.test import RequestFactory

HERO = '<div class="hero py-16">'
STYLESHEET = 'href="/static/css/tailwind.css"'


def test_the_not_found_page(client: Client):
    response = client.get("/no-such-page/")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "404.html" in [template.name for template in response.templates]
    html = response.content.decode()
    assert HERO in html
    assert '<h1 class="text-4xl font-bold">Page not found</h1>' in html
    assert STYLESHEET in html


def test_the_forbidden_page(rf: RequestFactory):
    response = permission_denied(rf.get("/"), Exception("This room is locked."))

    assert response.status_code == HTTPStatus.FORBIDDEN
    html = response.content.decode()
    assert HERO in html
    assert '<h1 class="text-4xl font-bold">Forbidden (403)</h1>' in html
    assert "This room is locked." in html
    assert STYLESHEET in html


def test_the_csrf_failure_page():
    client = Client(enforce_csrf_checks=True)

    response = client.post("/accounts/login/", {"login": "ada", "password": "secret"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "403_csrf.html" in [template.name for template in response.templates]
    html = response.content.decode()
    assert HERO in html
    assert '<h1 class="text-4xl font-bold">Forbidden (403)</h1>' in html


def test_the_server_error_page_renders_without_a_request_context(rf: RequestFactory):
    response = server_error(rf.get("/"))

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    html = response.content.decode()
    assert HERO in html
    assert '<h1 class="text-4xl font-bold">Ooops!!! 500</h1>' in html
    assert STYLESHEET in html
