# Annotations stay evaluated at runtime (no ``from __future__ import annotations``)
# because django-ninja reads them to build the OpenAPI schema.
from typing import Literal

from ninja import Router
from ninja import Schema

from {{ cookiecutter.project_slug }}.typedefs import PrincipalHttpRequest

from .auth import either_auth
from .models import ServiceRegistration

router = Router(tags=["identity"])


class PrincipalSchema(Schema):
    """Who is calling: a user by display name, or a registered service by name."""

    kind: Literal["user", "service"]
    name: str


@router.get("/", auth=either_auth, response=PrincipalSchema, url_name="principal")
def retrieve_principal(request: PrincipalHttpRequest) -> PrincipalSchema:
    """The example endpoint a user or a service may call."""
    if isinstance(request.auth, ServiceRegistration):
        return PrincipalSchema(kind="service", name=request.auth.name)
    return PrincipalSchema(kind="user", name=request.auth.display_name)
