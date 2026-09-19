"""The examples page: daisyUI components and htmx patterns as this project writes them.

Every view renders ``templates/examples/index.html``: the whole page for a plain
request, so each demo works without JavaScript, and one of its partials for an htmx
request. The page is routed in every environment, so it keeps nothing on the server: no
table and no session, only the query string, the posted form and one cookie. The views
open no transaction, and their tests run without database access to hold them to it.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Final

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from {{ cookiecutter.project_slug }}.examples.content import HTMX_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import STATIC_EXAMPLES
from {{ cookiecutter.project_slug }}.examples.content import TABS
from {{ cookiecutter.project_slug }}.examples.content import TASKS_PER_PAGE
from {{ cookiecutter.project_slug }}.examples.content import matching_tasks
from {{ cookiecutter.project_slug }}.examples.content import source
from {{ cookiecutter.project_slug }}.examples.content import tab_for
from {{ cookiecutter.project_slug }}.examples.forms import ExampleForm
from {{ cookiecutter.project_slug }}.examples.forms import FilterForm
from {{ cookiecutter.project_slug }}.htmx import HtmxTemplateMixin

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse

    from {{ cookiecutter.project_slug }}.typedefs import HtmxHttpRequest

# The one thing the page remembers, and in the visitor's browser: the toggle's state
NOTIFICATIONS_COOKIE: Final = "examples_notifications"
NOTIFICATIONS_MAX_AGE: Final = 60 * 60 * 24 * 30
# Under DEBUG the lazy tabs answer this many seconds late, so the indicator shows
DEBUG_DELAY: Final = 0.6
# The messages the notices demo may add: a request chooses among them, never the text
NOTICES: Final = {
    "info": (messages.INFO, "A note: nothing happened, and that is fine."),
    "success": (messages.SUCCESS, "Done. The server says so."),
    "warning": (messages.WARNING, "Careful: this is only a demonstration."),
    "error": (messages.ERROR, "That failed, as it was asked to."),
}


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class ExamplesView(HtmxTemplateMixin, TemplateView):
    """The page, and for an htmx request the filtered, paged table of tasks."""

    template_name = "examples/index.html"
    htmx_partial: str | None = "results"
    request: HtmxHttpRequest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        filter_form = FilterForm(self.request.GET)
        query = filter_form.cleaned_data["q"] if filter_form.is_valid() else ""
        paginator = Paginator(matching_tasks(query), TASKS_PER_PAGE)
        page = paginator.get_page(self.request.GET.get("page"))
        notifications = self.request.COOKIES.get(NOTIFICATIONS_COOKIE) == "on"
        defaults: dict[str, Any] = {
            "static_examples": STATIC_EXAMPLES,
            "sources": {name: source(name) for name in HTMX_EXAMPLES},
            "filter_form": filter_form,
            "query": query,
            "page": page,
            "page_range": list(paginator.get_elided_page_range(page.number)),
            "notifications": notifications,
            "tabs": TABS,
            "current_tab": tab_for(self.request.GET.get("tab")),
            "example_form": ExampleForm(),
            "result": None,
            "modal_open": False,
        }
        # What a view passes wins over the default that stands in for it
        return {**defaults, **super().get_context_data(**kwargs)}

    def back_to(self, example: str) -> HttpResponse:
        """Without htmx a post is answered with a redirect to its example."""
        return redirect(f"{reverse('examples:index')}#example-{example}")


class ExampleFormView(ExamplesView):
    """A form validated on the server. An invalid one answers 200 like a valid one:
    htmx swaps no error response unless told to."""

    htmx_partial = "form"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = ExampleForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(example_form=form))
        messages.success(request, "The form is valid; nothing was saved.")
        return self.render_to_response(self.get_context_data(result=form.summary()))


class ToggleView(ExamplesView):
    """A toggle that posts its state as it changes, kept in a cookie."""

    htmx_partial = "toggle"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        enabled = request.POST.get("enabled") == "on"
        state = "on" if enabled else "off"
        messages.info(request, f"Notifications are {state}.")
        response: HttpResponse
        if self.renders_htmx_fragment():
            context = self.get_context_data(notifications=enabled)
            response = self.render_to_response(context)
        else:
            response = self.back_to("toggle")
        response.set_cookie(
            NOTIFICATIONS_COOKIE,
            state,
            max_age=NOTIFICATIONS_MAX_AGE,
            secure=request.is_secure(),
            httponly=True,
            samesite="Lax",
        )
        return response


class TabsView(ExamplesView):
    """Tabs whose panel is fetched when its tab is chosen."""

    htmx_partial = "tabs"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if settings.DEBUG and self.renders_htmx_fragment():
            time.sleep(DEBUG_DELAY)
        return super().get(request, *args, **kwargs)


class ModalView(ExamplesView):
    """A dialog fetched from the server and closed by its answer."""

    htmx_partial = "modal"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("modal_open", True)
        return super().get_context_data(**kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.POST.get("answer") == "confirm":
            messages.success(request, "Archived, or it would have been.")
        if self.renders_htmx_fragment():
            return self.render_to_response(self.get_context_data(modal_open=False))
        return self.back_to("modal")


class NoticesView(ExamplesView):
    """Messages added during an htmx request, swapped into the page out of band."""

    htmx_partial = "notices"
    http_method_names = ["post", "options"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        notice = NOTICES.get(request.POST.get("level", ""))
        if notice is None:
            return HttpResponseBadRequest()
        level, text = notice
        messages.add_message(request, level, text)
        if self.renders_htmx_fragment():
            return self.render_to_response(self.get_context_data())
        return self.back_to("notices")
