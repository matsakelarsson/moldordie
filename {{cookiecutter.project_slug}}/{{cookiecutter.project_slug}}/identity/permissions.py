"""Permissions on the routes a user or a service may call.

The policies answer 401 for missing or invalid credentials before a route runs; a
route under ``either_auth`` that needs a permission asks ``require_permission``, which
answers 403 for a caller, user or service, that lacks it::

    @router.get("/reports/", auth=either_auth)
    def list_reports(request: PrincipalHttpRequest) -> list[ReportSchema]:
        require_permission(request, "reports.view_report")
        ...

A permission gates what a caller may do, not which rows it may see: that boundary is
the project's to add to its own models (``docs/authentication.rst``).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from ninja.errors import HttpError

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.typedefs import PrincipalHttpRequest


def require_permission(request: PrincipalHttpRequest, perm: str) -> None:
    """Refuse the request with 403 unless its principal holds ``perm``.

    ``perm`` is the full ``app_label.codename``. A user holds it through Django's
    authentication backends, a service through its registration's granted permissions,
    which a disabled registration never holds.
    """
    if not request.auth.has_perm(perm):
        raise HttpError(HTTPStatus.FORBIDDEN, "Permission denied")
