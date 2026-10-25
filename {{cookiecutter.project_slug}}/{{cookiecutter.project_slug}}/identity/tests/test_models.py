"""The registration of a calling service: what it may do, and when it may do nothing."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission

from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration

pytestmark = pytest.mark.django_db

PERMISSION = "users.view_user"


@pytest.fixture
def view_user() -> Permission:
    return Permission.objects.get(content_type__app_label="users", codename="view_user")


@pytest.fixture
def service() -> ServiceRegistration:
    return ServiceRegistration.objects.create(name="Billing", subject="billing")


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
