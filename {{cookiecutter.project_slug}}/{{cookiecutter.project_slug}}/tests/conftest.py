from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


@pytest.fixture
def fixture_templates(settings: Settings) -> None:
    """Add the tests' templates to the engine, keeping the project's directories.

    Assigning ``TEMPLATES`` resets the engines and the fixture restores them afterwards.
    """
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(TEMPLATES_DIR), *templates[0]["DIRS"]]
    settings.TEMPLATES = templates
