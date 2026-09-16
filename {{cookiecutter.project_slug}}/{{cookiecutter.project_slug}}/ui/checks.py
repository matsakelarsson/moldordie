"""System checks of the UI library: the theme the settings configure can be served."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core import checks

from .palettes import PALETTES
from .themes import MODES
from .themes import override_problems
from .themes import resolve
from .themes import validate

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig


def check_theme_settings(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    """``UI_PALETTE`` names a built-in palette, ``UI_MODE`` a supported mode, and
    ``UI_BRAND`` gives the brand's tokens colours that every pair still meets."""
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
    for problem in override_problems(settings.UI_BRAND):
        where = "UI_BRAND"
        if problem.set_name is not None:
            where += f"[{problem.set_name!r}]"
        messages.append(
            checks.Error(
                f"{where}: {problem.message}.",
                hint="UI_BRAND maps light and dark to the tokens a brand may "
                "override, each to a #RRGGBB colour; see docs/frontend.rst.",
                id="ui.E003",
            ),
        )
    if messages:
        return messages
    theme = resolve(settings.UI_PALETTE, settings.UI_MODE, settings.UI_BRAND)
    return [
        checks.Error(
            f"UI_BRAND breaks a pair of the {problem.set_name} set: {problem.message}.",
            hint="Choose colours that meet the ratio against every token they meet; "
            "the pairs are PAIRS in ui/palettes.py.",
            id="ui.E004",
        )
        for problem in validate(theme)
    ]
