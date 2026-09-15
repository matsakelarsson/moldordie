from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from {{ cookiecutter.project_slug }}.identity.tests.headless import create_verified_user

if TYPE_CHECKING:
    from {{ cookiecutter.project_slug }}.users.models import User


@pytest.fixture
def user(db: None) -> User:
    """A user who can sign in through the app client: a known password, verified."""
    return create_verified_user()
