"""The metrics endpoint, written for the scraper rather than for a person.

Prometheus is a machine: it presents a bearer credential and never a session, so no
account, group or browser login decides whether a scrape succeeds. ``METRICS_TOKEN``
is that credential, drawn separately for each deployed environment. An empty one
refuses every request, because a deployment that configured no credential has
authorised nobody.

The exposition itself is django-prometheus', built from what the middlewares, the
database backend and the cache backend recorded. Under Gunicorn each worker keeps its
own registry, so the deployed image points ``PROMETHEUS_MULTIPROC_DIR`` at a directory
the workers of that container share and the exporter reads all of them, which is what
makes one scrape describe the whole container (``compose/production/django/start``).
"""

from __future__ import annotations

from hmac import compare_digest
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import cast

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_safe
from django_prometheus.exports import ExportToDjangoView

if TYPE_CHECKING:
    from django.http import HttpRequest

# An Authorization header is a scheme and a credential
SCHEME_AND_CREDENTIAL = 2


def presented_credential(request: HttpRequest) -> str | None:
    """The credential of an ``Authorization: Bearer`` header; None for any other."""
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != SCHEME_AND_CREDENTIAL or parts[0].lower() != "bearer":
        return None
    return parts[1]


def unauthorized() -> HttpResponse:
    """Refuse the scrape, naming the scheme it should have presented."""
    return HttpResponse(
        status=HTTPStatus.UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@transaction.non_atomic_requests
@require_safe
def metrics(request: HttpRequest) -> HttpResponse:
    """The exposition, for a request that presented the configured token.

    The comparison is over bytes and in constant time, so a credential that is not
    ASCII is refused rather than raising, and a wrong one tells the caller nothing
    about how wrong it was. No transaction is opened: the scrape reads no table.
    """
    token = settings.METRICS_TOKEN
    presented = presented_credential(request)
    if not token or presented is None:
        return unauthorized()
    if not compare_digest(presented.encode(), token.encode()):
        return unauthorized()
    return cast("HttpResponse", ExportToDjangoView(request))
