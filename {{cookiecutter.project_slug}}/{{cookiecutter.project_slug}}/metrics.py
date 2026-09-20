{%- set service_tokens = cookiecutter.identity_provider != 'none' -%}
{%- set entra = cookiecutter.identity_provider == 'entra' -%}
"""The metrics endpoint, written for the scraper rather than for a person.

{% if service_tokens -%}
Prometheus is a machine: it presents a bearer credential and never a session, so no
account, group or browser login decides whether a scrape succeeds. Two credentials are
accepted, and the token says which. A token {% if entra %}the tenant{% else %}Google{% endif %} issued to a calling service
is verified like any other (``identity/verification.py``), and the registration behind
it must hold ``identity.read_metrics``: a service the provider vouches for is not by
that alone a service that may scrape. Anything else is compared against
``METRICS_TOKEN``, the credential each deployed environment drew for a scraper the
provider knows nothing about; an empty one authorises nobody that way. Neither
credential falls back to the other.
{%- else -%}
Prometheus is a machine: it presents a bearer credential and never a session, so no
account, group or browser login decides whether a scrape succeeds. ``METRICS_TOKEN``
is that credential, drawn separately for each deployed environment. An empty one
refuses every request, because a deployment that configured no credential has
authorised nobody.
{%- endif %}

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
{%- if service_tokens %}

from {{ cookiecutter.project_slug }}.identity.verification import Rejected
from {{ cookiecutter.project_slug }}.identity.verification import service_verifier
from {{ cookiecutter.project_slug }}.identity.verification import unverified_issuer
{%- endif %}

if TYPE_CHECKING:
    from django.http import HttpRequest

# An Authorization header is a scheme and a credential
SCHEME_AND_CREDENTIAL = 2
{%- if service_tokens %}
# What a calling service's registration must hold to read the exposition
READ_METRICS = "identity.read_metrics"
{%- endif %}


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
{%- if service_tokens %}


def forbidden() -> HttpResponse:
    """Refuse a caller the project knows and has not allowed to read the metrics."""
    return HttpResponse(status=HTTPStatus.FORBIDDEN)
{%- endif %}


def exposition(request: HttpRequest) -> HttpResponse:
    """What the container has recorded, in Prometheus' exposition format."""
    return cast("HttpResponse", ExportToDjangoView(request))
{%- if service_tokens %}


def exposition_for_service(request: HttpRequest, token: str) -> HttpResponse:
    """The exposition for a calling service, once the token and the grant both hold.

    The verifier decides whether the provider really issued the token to a registered,
    enabled service; the permission decides whether that service may scrape. A refused
    token is 401 and a service without the grant is 403: one presented no usable
    credential, the other presented one that does not reach this far.
    """
    try:
        registration = service_verifier().verify(token)
    except Rejected:
        return unauthorized()
    if not registration.has_perm(READ_METRICS):
        return forbidden()
    return exposition(request)
{%- endif %}


@transaction.non_atomic_requests
@require_safe
def metrics(request: HttpRequest) -> HttpResponse:
    """The exposition, for a request that presented a credential this project accepts.

    {% if service_tokens -%}
    The token's own ``iss`` claim picks the branch, unverified and trusted for nothing
    else: a configured provider issuer means the verifier decides, and anything else is
    compared against the configured token. That comparison is over bytes and in constant
    time, so a credential that is not ASCII is refused rather than raising, and a wrong
    one tells the caller nothing about how wrong it was. No transaction is opened: a
    scrape reads the registrations at most, and writes nothing.
    {%- else -%}
    The comparison is over bytes and in constant time, so a credential that is not
    ASCII is refused rather than raising, and a wrong one tells the caller nothing
    about how wrong it was. No transaction is opened: the scrape reads no table.
    {%- endif %}
    """
    presented = presented_credential(request)
    if presented is None:
        return unauthorized()
{%- if service_tokens %}
    issuer = unverified_issuer(presented)
    if isinstance(issuer, str) and issuer in settings.IDENTITY_SERVICE_ISSUERS:
        return exposition_for_service(request, presented)
{%- endif %}
    token = settings.METRICS_TOKEN
    if not token or not compare_digest(presented.encode(), token.encode()):
        return unauthorized()
    return exposition(request)
