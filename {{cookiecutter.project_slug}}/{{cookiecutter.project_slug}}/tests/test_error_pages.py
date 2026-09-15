"""The error pages: cards on base.html that render without the database.

The tests carry no django_db mark, so a query while rendering fails them.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.views.defaults import server_error

if TYPE_CHECKING:
    from django.test import Client
    from django.test import RequestFactory


def test_the_not_found_page(client: Client):
    response = client.get("/no-such-page/")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "404.html" in [template.name for template in response.templates]
    html = response.content.decode()
    assert '<article class="ui-card"' in html
    assert "<h1>Page not found</h1>" in html
    assert 'href="/ui/theme.css"' in html


def test_the_server_error_page_renders_without_a_request_context(rf: RequestFactory):
    response = server_error(rf.get("/"))

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    html = response.content.decode()
    assert '<article class="ui-card"' in html
    assert "<h1>Ooops!!! 500</h1>" in html
    assert 'href="/ui/theme.css"' in html
