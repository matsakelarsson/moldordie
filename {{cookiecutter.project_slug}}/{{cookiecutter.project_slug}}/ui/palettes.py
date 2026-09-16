"""The colour tokens of the UI library, the pairs they contrast in, and the palettes.

Python owns the colours so that the theme stylesheet, the validation of a theme and the
tests read the same values (docs/frontend.rst); ``static/css/ui/tokens.css`` holds the
tokens that are not colours. A palette is complete: every token, in both sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .contrast import NON_TEXT_RATIO
from .contrast import TEXT_RATIO

# The two colour sets of a palette, one for light mode and one for dark
SETS: Final = ("light", "dark")
STATUSES: Final = ("info", "success", "warning", "error")
# The tokens a brand may override. ``border`` is decorative and unchecked;
# ``border-control`` bounds inputs and buttons and is checked.
BRAND_TOKENS: Final = (
    "bg",
    "surface",
    "fg",
    "fg-muted",
    "border",
    "border-control",
    "accent",
    "accent-hover",
    "accent-fg",
    "focus",
)
# The tokens the palette owns: per status its solid, the text on the solid, the text
# on the page and on the tint, and the tint itself
STATUS_TOKENS: Final = tuple(
    f"{status}{suffix}"
    for status in STATUSES
    for suffix in ("", "-fg", "-text", "-tint")
)
TOKENS: Final = BRAND_TOKENS + STATUS_TOKENS


@dataclass(frozen=True)
class Pair:
    """A foreground token, the background it is shown on, and the ratio AA asks."""

    foreground: str
    background: str
    ratio: float
    where: str


def _pairs() -> tuple[Pair, ...]:
    """The adjacency table: each pair of tokens that meet on the page, and its ratio."""
    pairs: list[Pair] = []
    page = ("bg", "surface")
    tints = tuple(f"{status}-tint" for status in STATUSES)
    for foreground in ("fg", "fg-muted"):
        pairs += [Pair(foreground, bg, TEXT_RATIO, "text") for bg in page]
    for foreground in ("accent", "accent-hover"):
        pairs += [Pair(foreground, bg, TEXT_RATIO, "links") for bg in page]
    pairs += [
        Pair("accent-fg", bg, TEXT_RATIO, "the primary button")
        for bg in ("accent", "accent-hover")
    ]
    for status in STATUSES:
        pairs += [
            Pair(f"{status}-text", bg, TEXT_RATIO, f"{status} text")
            for bg in (*page, f"{status}-tint")
        ]
        pairs.append(Pair(f"{status}-fg", status, TEXT_RATIO, f"the {status} badge"))
    pairs += [
        Pair("border-control", bg, NON_TEXT_RATIO, "control boundaries") for bg in page
    ]
    pairs += [
        Pair("focus", bg, NON_TEXT_RATIO, "the focus ring") for bg in (*page, *tints)
    ]
    for status in STATUSES:
        pairs += [
            Pair(status, bg, NON_TEXT_RATIO, f"the {status} indicator")
            for bg in (*page, f"{status}-tint")
        ]
    return tuple(pairs)


PAIRS: Final = _pairs()

_LIGHT = {
    "bg": "#ffffff",
    "surface": "#f4f5f7",
    "fg": "#1b1f27",
    "fg-muted": "#5a6170",
    "border": "#d8dce3",
    "border-control": "#6e7586",
    "info": "#0369a1",
    "info-fg": "#ffffff",
    "info-text": "#075985",
    "info-tint": "#e0f2fe",
    "success": "#15803d",
    "success-fg": "#ffffff",
    "success-text": "#166534",
    "success-tint": "#dcfce7",
    "warning": "#b45309",
    "warning-fg": "#ffffff",
    "warning-text": "#92400e",
    "warning-tint": "#fef3c7",
    "error": "#b91c1c",
    "error-fg": "#ffffff",
    "error-text": "#991b1b",
    "error-tint": "#fee2e2",
}
_DARK = {
    "bg": "#0f1218",
    "surface": "#1a1f2a",
    "fg": "#e6e9ef",
    "fg-muted": "#a3aab7",
    "border": "#2c3342",
    "border-control": "#6b7385",
    "info": "#38bdf8",
    "info-fg": "#0b1220",
    "info-text": "#7dd3fc",
    "info-tint": "#0c2a4a",
    "success": "#4ade80",
    "success-fg": "#0b1220",
    "success-text": "#86efac",
    "success-tint": "#0f2e1c",
    "warning": "#fbbf24",
    "warning-fg": "#0b1220",
    "warning-text": "#fcd34d",
    "warning-tint": "#3a2a06",
    "error": "#f87171",
    "error-fg": "#0b1220",
    "error-text": "#fca5a5",
    "error-tint": "#3b1212",
}


def _palette(
    light_accent: str,
    light_hover: str,
    dark_accent: str,
    dark_hover: str,
) -> dict[str, dict[str, str]]:
    """A palette from its accents: white text on the light accents, near-black on the
    dark ones, and the hover colour as the focus ring of each set."""
    return {
        "light": {
            **_LIGHT,
            "accent": light_accent,
            "accent-hover": light_hover,
            "accent-fg": "#ffffff",
            "focus": light_hover,
        },
        "dark": {
            **_DARK,
            "accent": dark_accent,
            "accent-hover": dark_hover,
            "accent-fg": "#0b1220",
            "focus": dark_hover,
        },
    }


PALETTES: Final[dict[str, dict[str, dict[str, str]]]] = {
    "blue": _palette("#2563eb", "#1d4ed8", "#60a5fa", "#93c5fd"),
    "teal": _palette("#0f766e", "#115e59", "#2dd4bf", "#5eead4"),
    "violet": _palette("#6d28d9", "#5b21b6", "#a78bfa", "#c4b5fd"),
}
