from __future__ import annotations

from typing import TYPE_CHECKING

from .themes import resolve_theme

if TYPE_CHECKING:
    from django.http import HttpRequest

    from .themes import Theme


def theme(request: HttpRequest) -> dict[str, Theme]:
    """Expose the request's theme to templates as ``ui_theme``."""
    return {"ui_theme": resolve_theme(request)}
