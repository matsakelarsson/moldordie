"""System checks of the UI library: the theme the settings configure exists."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core import checks

from .palettes import PALETTES
from .themes import MODES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig


def check_theme_settings(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    """``UI_PALETTE`` names a built-in palette and ``UI_MODE`` a supported mode."""
    messages: list[checks.CheckMessage] = []
    if settings.UI_PALETTE not in PALETTES:
        messages.append(
            checks.Error(
                f"UI_PALETTE is {settings.UI_PALETTE!r}, which is not a palette of "
                "the UI library.",
                hint=f"Choose one of {', '.join(PALETTES)}; see docs/frontend.rst.",
                id="ui.E001",
            ),
        )
    if settings.UI_MODE not in MODES:
        messages.append(
            checks.Error(
                f"UI_MODE is {settings.UI_MODE!r}, which is not a mode of the "
                "UI library.",
                hint=f"Choose one of {', '.join(MODES)}.",
                id="ui.E002",
            ),
        )
    return messages
