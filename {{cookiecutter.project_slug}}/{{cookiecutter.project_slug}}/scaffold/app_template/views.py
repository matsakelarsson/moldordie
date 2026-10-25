"""The app's views: the list, filtered and paged, one record, and the forms that
create, change and delete one.

Each answers an htmx request with a partial of its template and any other request
with the whole page, so every page works without JavaScript (``HtmxTemplateMixin``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import Form
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from django_htmx.http import HttpResponseClientRedirect

from {{ cookiecutter.project_slug }}.htmx import HtmxTemplateMixin
from {{ cookiecutter.project_slug }}.scaffold.app_template.forms import FilterForm
from {{ cookiecutter.project_slug }}.scaffold.app_template.forms import ItemForm
from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpResponse

    from {{ cookiecutter.project_slug }}.typedefs import AuthenticatedHtmxRequest

PER_PAGE = 20


class ItemViewMixin(LoginRequiredMixin, HtmxTemplateMixin):
    """What the app's views share: a signed-in user, htmx partials, and ``opts``, the
    model's names, for the templates' headings."""

    request: AuthenticatedHtmxRequest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["opts"] = Item._meta  # noqa: SLF001 - as the admin passes its model's
        return context


class ItemListView(ItemViewMixin, ListView[Item]):
    """The records, newest first, filtered by ``?q=`` and paged; htmx gets the table."""

    model = Item
    htmx_partial = "results"
    paginate_by = PER_PAGE
    filter_form: FilterForm
    query: str

    def get_queryset(self) -> QuerySet[Item]:
        self.filter_form = FilterForm(self.request.GET)
        valid = self.filter_form.is_valid()
        self.query = self.filter_form.cleaned_data["q"] if valid else ""
        queryset = super().get_queryset()
        return queryset.filter(name__icontains=self.query) if self.query else queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["query"] = self.query
        page = context["page_obj"]
        context["page_range"] = list(page.paginator.get_elided_page_range(page.number))
        return context


class ItemDetailView(ItemViewMixin, DetailView[Item]):
    """One record; htmx gets its card."""

    model = Item
    htmx_partial = "card"


class ItemCreateView(
    ItemViewMixin,
    SuccessMessageMixin[ItemForm],
    CreateView[Item, ItemForm],
):
    """A new record: the form's card, and on success the record's with a message."""

    model = Item
    form_class = ItemForm
    htmx_partial = "card"
    success_message = _("%(name)s was created.")


class ItemUpdateView(
    ItemViewMixin,
    SuccessMessageMixin[ItemForm],
    UpdateView[Item, ItemForm],
):
    """A changed record: the form's card, and on success the record's with a message."""

    model = Item
    form_class = ItemForm
    htmx_partial = "card"
    success_message = _("%(name)s was saved.")


class ItemDeleteView(ItemViewMixin, DeleteView[Item, Form]):
    """The confirmation, a dialog for htmx, and the deletion, after which the browser
    leaves for the list either way."""

    model = Item
    htmx_partial = "dialog"
    success_url = reverse_lazy("app_template:list")

    def form_valid(self, form: Form) -> HttpResponse:
        name = str(self.object)
        response = super().form_valid(form)
        messages.success(self.request, _("%(name)s was deleted.") % {"name": name})
        if self.renders_htmx_fragment():
            # The dialog came into the page over htmx; the answer sends the browser away
            return HttpResponseClientRedirect(self.get_success_url())
        return response
