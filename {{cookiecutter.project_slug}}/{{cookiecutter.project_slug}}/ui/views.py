"""The theme stylesheet, served on every page, and the showcase, which config/urls.py
registers only under DEBUG (docs/frontend.rst)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from {{ cookiecutter.project_slug }}.htmx import HtmxTemplateMixin

from .forms import FilterForm
from .forms import PreviewForm
from .forms import SampleForm
from .showcase import results
from .themes import PREVIEW_SESSION_KEY
from .themes import render_stylesheet
from .themes import resolve
from .themes import resolve_theme

if TYPE_CHECKING:
    from django.http import HttpRequest

    from {{ cookiecutter.project_slug }}.typedefs import HtmxHttpRequest

    from .themes import Theme

# The sample form as submitted with wrong answers, for the states of the field component
INVALID_SAMPLE = {
    "invalid-name": "",
    "invalid-email": "not an address",
    "invalid-plan": "team",
    "invalid-seats": "1",
}


@transaction.non_atomic_requests
def theme_stylesheet(request: HttpRequest) -> HttpResponse:
    """The resolved theme as a stylesheet, private and uncached: it is per request.

    No transaction is opened. Without DEBUG, when no session preview is read, no
    database is needed either, so the stylesheet is served while the database is not
    and an error page still has its colours.
    """
    response = HttpResponse(
        render_stylesheet(resolve_theme(request)),
        content_type="text/css; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store"
    return response


class ShowcaseView(HtmxTemplateMixin, TemplateView):
    """The showcase: every component with its contract, example and source, the sample
    form, the paged results and the theme preview.

    An htmx request gets the part it targets, a POST the sample form's partial and a GET
    the results'. An invalid sample answers 200 like a valid one: htmx's default
    configuration swaps no error response.
    """

    template_name = "ui/showcase.html"
    request: HtmxHttpRequest

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.htmx_partial = "sample" if request.method == "POST" else "results"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = SampleForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(sample_form=form))
        messages.success(request, "The sample form is valid; nothing was saved.")
        return self.render_to_response(self.get_context_data(result=form.summary()))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Resolved first: a preview that can no longer be served leaves the session here
        theme = resolve_theme(self.request)
        preview = None
        if settings.DEBUG:
            preview = self.request.session.get(PREVIEW_SESSION_KEY)
        filter_form = FilterForm(self.request.GET)
        query = filter_form.cleaned_data["q"] if filter_form.is_valid() else ""
        context |= results(self.request, query)
        context |= {
            "filter_form": filter_form,
            "query": query,
            "invalid_form": SampleForm(INVALID_SAMPLE, prefix="invalid"),
            "previewing": preview is not None,
        }
        context.setdefault("sample_form", SampleForm())
        context.setdefault("result", None)
        if "preview_form" not in context:
            context["preview_form"] = PreviewForm(
                initial=PreviewForm.initial_for(theme, preview),
                beneath=_beneath(theme),
            )
        return context


class PreviewView(ShowcaseView):
    """Keep a theme preview in the session and return to the showcase, or show the
    showcase with the preview form's errors and the theme as it was."""

    http_method_names = ["post"]

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        # A whole page, whose next load fetches the theme stylesheet again
        self.htmx_partial = None

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = PreviewForm(request.POST, beneath=_beneath(resolve_theme(request)))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(preview_form=form))
        request.session[PREVIEW_SESSION_KEY] = form.preview()
        messages.success(request, "The preview applies to this session until reset.")
        return redirect(f"{reverse('showcase:index')}#showcase-theme")


@require_POST
def reset_preview(request: HttpRequest) -> HttpResponse:
    """Remove the session's theme preview and return to the showcase."""
    request.session.pop(PREVIEW_SESSION_KEY, None)
    messages.success(request, "The configured theme applies again.")
    return redirect(f"{reverse('showcase:index')}#showcase-theme")


def _beneath(theme: Theme) -> Theme:
    """The theme a preview's colours apply over: its palette with the brand."""
    return resolve(theme.palette, theme.mode, settings.UI_BRAND)
