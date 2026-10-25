"""The project's URLs with the fixture page the htmx mixin's tests drive."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.contrib import messages
from django.db import transaction
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from config.urls import urlpatterns as project_urlpatterns

from {{ cookiecutter.project_slug }}.htmx import HtmxTemplateMixin

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse

    from {{ cookiecutter.project_slug }}.typedefs import HtmxHttpRequest

AFTER_A_POST = "/after/"


# No transaction, so that the mixin's tests run with database access blocked
@method_decorator(transaction.non_atomic_requests, name="dispatch")
class FixtureView(HtmxTemplateMixin, TemplateView):
    """A page with one partial; a post adds a message and answers, or redirects."""

    template_name = "tests/htmx.html"
    htmx_partial: str | None = "card"
    request: HtmxHttpRequest

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        messages.info(request, "The post was noted.")
        return self.fragment_or_redirect(AFTER_A_POST, posted=True)


class PageOnlyView(FixtureView):
    """The same page from a view that names no partial."""

    htmx_partial = None


urlpatterns = [
    *project_urlpatterns,
    path("htmx/fixture/", FixtureView.as_view(), name="htmx_fixture"),
    path("htmx/page-only/", PageOnlyView.as_view(), name="htmx_page_only"),
]
