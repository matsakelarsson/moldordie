"""The daisyUI themes a visitor may choose, and the cookie that keeps the choice.

The theme picker in ``templates/partials/navigation.html`` posts the choice to
``set_theme`` through htmx. The ``theme`` context processor reads the cookie back, and
``base.html`` writes it as ``data-theme`` on the root element, so the next page arrives
in the chosen theme. No script is involved: a checked ``theme-controller`` radio
restyles the page in CSS alone, and nothing but the server ever reads the cookie.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Final

from django.db import transaction
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_htmx.http import HttpResponseClientRefresh

if TYPE_CHECKING:
    from django.http import HttpRequest

    from {{ cookiecutter.project_slug }}.typedefs import HtmxHttpRequest

# The project's own theme, the default look: styles/theme.css
OWN_THEME: Final = "brand"
# The themes of the built stylesheet: the own theme, then daisyUI's in the order
# styles/main.css enables them. tests/test_themes.py compares the two, so a theme is
# dropped, or added, in both places.
THEMES: Final = (
    OWN_THEME,
    "light",
    "dark",
    "cupcake",
    "bumblebee",
    "emerald",
    "corporate",
    "synthwave",
    "retro",
    "cyberpunk",
    "valentine",
    "halloween",
    "garden",
    "forest",
    "aqua",
    "lofi",
    "pastel",
    "fantasy",
    "wireframe",
    "black",
    "luxury",
    "dracula",
    "cmyk",
    "autumn",
    "business",
    "acid",
    "lemonade",
    "night",
    "coffee",
    "winter",
    "dim",
    "nord",
    "sunset",
    "caramellatte",
    "abyss",
    "silk",
)
# The picker's choice that names no theme: the browser's colour scheme decides
SYSTEM: Final = "system"
COOKIE_NAME: Final = "theme"
COOKIE_MAX_AGE: Final = 60 * 60 * 24 * 365


def current_theme(request: HttpRequest) -> str:
    """The theme the visitor chose, or ``""`` when the browser's colour scheme
    decides: there is no cookie, or it names no theme of the stylesheet."""
    name = request.COOKIES.get(COOKIE_NAME, "")
    return name if name in THEMES else ""


def theme(request: HttpRequest) -> dict[str, object]:
    """Expose ``current_theme``, which ``base.html`` writes as ``data-theme``, and
    ``themes``, the picker's choices, in templates."""
    return {"current_theme": current_theme(request), "themes": THEMES}


def _next_url(request: HttpRequest) -> str:
    """Where a post without htmx returns to: ``next``, if it stays on this host."""
    url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return resolve_url("home")


@transaction.non_atomic_requests
@require_POST
def set_theme(request: HtmxHttpRequest) -> HttpResponse:
    """Keep the chosen theme in a cookie, or forget it for ``system``.

    htmx gets no content for a theme, since the checked radio has restyled the page
    already, and a refresh for ``system``: nothing on the page can undo the
    ``data-theme`` it was served with. A post without htmx is redirected back. A name
    outside ``THEMES`` is refused, so none ever reaches the cookie or the attribute.
    No transaction is opened: the choice touches no table.
    """
    name = request.POST.get("theme", "")
    if name != SYSTEM and name not in THEMES:
        return HttpResponseBadRequest()
    response: HttpResponse
    if not request.htmx or request.htmx.boosted:
        response = redirect(_next_url(request))
    elif name == SYSTEM:
        response = HttpResponseClientRefresh()
    else:
        response = HttpResponse(status=HTTPStatus.NO_CONTENT)
    if name == SYSTEM:
        response.delete_cookie(COOKIE_NAME, samesite="Lax")
    else:
        response.set_cookie(
            COOKIE_NAME,
            name,
            max_age=COOKIE_MAX_AGE,
            secure=request.is_secure(),
            httponly=True,
            samesite="Lax",
        )
    return response
