"""What the app's tests share: the client, signed in as the ``user`` fixture's user."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from django.test import Client

    from {{ cookiecutter.project_slug }}.users.models import User


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    client.force_login(user)
    return client
