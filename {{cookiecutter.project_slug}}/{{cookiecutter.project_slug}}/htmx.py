"""htmx helpers: partials for htmx requests, and login redirects that leave the page."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from urllib.parse import urlsplit

from asgiref.sync import iscoroutinefunction
from asgiref.sync import markcoroutinefunction
from django.conf import settings
from django.shortcuts import resolve_url
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
from django_htmx.http import HttpResponseClientRedirect

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponseBase
    from django.views.generic.base import ContextMixin
    from django.views.generic.base import TemplateResponseMixin
    from django.views.generic.base import View
    from django_htmx.middleware import HtmxDetails

    from {{ cookiecutter.project_slug }}.typedefs import HtmxHttpRequest

    GetResponse = Callable[[HttpRequest], HttpResponseBase]
    AsyncGetResponse = Callable[[HttpRequest], Awaitable[HttpResponseBase]]

    class _TemplateViewBase(TemplateResponseMixin, ContextMixin, View):
        """Typing-only base so mypy knows the methods this mixin overrides."""

else:
    _TemplateViewBase = object


class HtmxTemplateMixin(_TemplateViewBase):
    """Render one template partial of the view's template for htmx requests.

    Set ``htmx_partial`` to the name of a ``partialdef`` block in the view's
    template. A request carrying the ``HX-Request`` header then renders
    ``"<template>#<htmx_partial>"``, that is only the partial, while every
    other request renders the whole template, so the page keeps working
    without htmx. Boosted requests (``hx-boost``) expect a whole page and get
    the full template. Every response gets ``Vary: HX-Request`` because its
    body depends on that header.

    The context flag ``htmx_fragment`` tells templates which of the two is
    being rendered, so the messages block can be marked for an out-of-band
    swap in a fragment without being emitted twice in a full page. Branch on
    that flag rather than on ``request.htmx``: a template that branches on the
    request varies by the header on every page that includes it, including
    pages whose view sends no ``Vary``.

    Function-based views do the same thing directly::

        @vary_on_headers("HX-Request")
        def profile(request):
            fragment = bool(request.htmx) and not request.htmx.boosted
            template_name = "users/user_detail.html"
            if fragment:
                template_name += "#profile"
            context = {"htmx_fragment": fragment}
            return render(request, template_name, context)
    """

    htmx_partial: str | None = None
    request: HtmxHttpRequest

    @method_decorator(vary_on_headers("HX-Request"))
    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseBase:
        return super().dispatch(request, *args, **kwargs)

    def renders_htmx_fragment(self) -> bool:
        """Does this response carry the partial rather than the whole template?"""
        htmx = self.request.htmx
        return bool(self.htmx_partial and htmx and not htmx.boosted)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["htmx_fragment"] = self.renders_htmx_fragment()
        return context

    def get_template_names(self) -> list[str]:
        names = super().get_template_names()
        if not self.renders_htmx_fragment():
            return names
        return [f"{name}#{self.htmx_partial}" for name in names]


class HtmxLoginRedirectMiddleware:
    """Turn redirects to the login page into browser redirects for htmx requests.

    ``LoginRequiredMixin`` answers an expired session with a 302 to
    ``LOGIN_URL``. htmx would follow it inside the request and swap the login
    page into the target element. For htmx requests the 302 becomes
    django-htmx's ``HttpResponseClientRedirect`` (a 200 with the
    ``HX-Redirect`` header), so the browser navigates to the login page and
    comes back through ``?next=``. Boosted requests and every other redirect
    are left alone. The middleware needs ``request.htmx``, so it is listed
    after ``HtmxMiddleware``.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: GetResponse | AsyncGetResponse) -> None:
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(
        self,
        request: HttpRequest,
    ) -> HttpResponseBase | Awaitable[HttpResponseBase]:
        if self.async_mode:
            return self.__acall__(request)
        response = cast("GetResponse", self.get_response)(request)
        return self.process_response(request, response)

    async def __acall__(self, request: HttpRequest) -> HttpResponseBase:
        response = await cast("AsyncGetResponse", self.get_response)(request)
        return self.process_response(request, response)

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponseBase,
    ) -> HttpResponseBase:
        location = response.headers.get("Location")
        status = response.status_code
        is_redirect = HTTPStatus.MULTIPLE_CHOICES <= status < HTTPStatus.BAD_REQUEST
        if location is None or not is_redirect:
            return response
        if urlsplit(location).path != urlsplit(resolve_url(settings.LOGIN_URL)).path:
            return response
        htmx: HtmxDetails | None = getattr(request, "htmx", None)
        if htmx and not htmx.boosted:
            response = HttpResponseClientRedirect(location)
        # The answer depends on the header whichever branch was taken above
        patch_vary_headers(response, ("HX-Request",))
        return response
