"""Permissions of users and services on the routes both may call."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from ninja.errors import HttpError

from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration
from {{ cookiecutter.project_slug }}.identity.permissions import require_permission
from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user

if TYPE_CHECKING:
    from django.test import Client
    from django.test import RequestFactory

pytestmark = pytest.mark.django_db

PERMISSION = "users.view_user"


@pytest.fixture
def view_user() -> Permission:
    return Permission.objects.get(content_type__app_label="users", codename="view_user")


@pytest.fixture
def service() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject="billing")


def calling(rf: RequestFactory, principal: object):
    """A request the policy resolved to ``principal``, as the route sees it."""
    request = rf.get("/")
    request.auth = principal  # type: ignore[attr-defined]
    return request


class TestServiceRegistrationHasPerm:
    def test_a_granted_permission(self, service, view_user):
        service.permissions.add(view_user)

        assert service.has_perm(PERMISSION) is True

    def test_a_permission_not_granted(self, service, view_user):
        assert service.has_perm(PERMISSION) is False
        assert service.has_perm("users.change_user") is False

    def test_the_full_name_counts(self, service, view_user):
        """A codename alone, or one of another app, matches nothing."""
        service.permissions.add(view_user)

        assert service.has_perm("view_user") is False
        assert service.has_perm("identity.view_user") is False

    def test_a_disabled_service_has_no_permission(self, service, view_user):
        service.permissions.add(view_user)
        service.enabled = False
        service.save()

        assert service.has_perm(PERMISSION) is False


class TestRequirePermission:
    def test_a_service_with_the_permission_passes(self, rf, service, view_user):
        service.permissions.add(view_user)

        require_permission(calling(rf, service), PERMISSION)

    def test_a_service_without_it_is_forbidden(self, rf, service):
        with pytest.raises(HttpError) as refused:
            require_permission(calling(rf, service), PERMISSION)

        assert refused.value.status_code == HTTPStatus.FORBIDDEN

    def test_a_disabled_service_is_forbidden_even_with_it(self, rf, service, view_user):
        service.permissions.add(view_user)
        service.enabled = False
        service.save()

        with pytest.raises(HttpError) as refused:
            require_permission(calling(rf, service), PERMISSION)

        assert refused.value.status_code == HTTPStatus.FORBIDDEN

    def test_a_user_with_the_permission_passes(self, rf, view_user):
        user = create_verified_user()
        user.user_permissions.add(view_user)

        require_permission(calling(rf, user), PERMISSION)

    def test_a_user_without_it_is_forbidden(self, rf):
        user = create_verified_user()

        with pytest.raises(HttpError) as refused:
            require_permission(calling(rf, user), PERMISSION)

        assert refused.value.status_code == HTTPStatus.FORBIDDEN


def test_missing_credentials_stay_unauthorized(client: Client):
    """The policy answers before any permission is asked: 401, not 403."""
    response = client.get(reverse("api:principal"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
