"""The theme stylesheet: the request's colour tokens, served as CSS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.http import HttpResponse

from .themes import render_stylesheet
from .themes import resolve_theme

if TYPE_CHECKING:
    from django.http import HttpRequest


@transaction.non_atomic_requests
def theme_stylesheet(request: HttpRequest) -> HttpResponse:
    """The resolved theme as a stylesheet, private and uncached: it is per request.

    No database is needed, so no transaction is opened: the stylesheet is served while
    the database is not, and an error page still has its colours.
    """
    response = HttpResponse(
        render_stylesheet(resolve_theme(request)),
        content_type="text/css; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store"
    return response
