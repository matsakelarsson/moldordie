"""WCAG contrast arithmetic: the relative luminance of a colour and the ratio of two.

The formulas are those of WCAG 2.2, "relative luminance" and "contrast ratio". Ratios
are compared unrounded; the thresholds are AA's, 4.5:1 for text and 3:1 for the
boundaries and indicators that carry meaning.
"""

from __future__ import annotations

import math
import re

TEXT_RATIO = 4.5
NON_TEXT_RATIO = 3.0

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
_CHANNELS = 255
_LINEAR_LIMIT = 0.04045
_LINEAR_DIVISOR = 12.92
_GAMMA_OFFSET = 0.055
_GAMMA_DIVISOR = 1.055
_GAMMA = 2.4
_LUMINANCE_OFFSET = 0.05
_WEIGHTS = (0.2126, 0.7152, 0.0722)


def parse_hex(colour: object) -> tuple[int, int, int]:
    """The red, green and blue channels of a ``#RRGGBB`` colour."""
    if not isinstance(colour, str) or not HEX_COLOUR.fullmatch(colour):
        msg = f"{colour!r} is not a #RRGGBB colour"
        raise ValueError(msg)
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def _linear(channel: int) -> float:
    srgb = channel / _CHANNELS
    if srgb <= _LINEAR_LIMIT:
        return srgb / _LINEAR_DIVISOR
    return math.pow((srgb + _GAMMA_OFFSET) / _GAMMA_DIVISOR, _GAMMA)


def relative_luminance(colour: str) -> float:
    """The relative luminance of ``colour``, 0 for black and 1 for white."""
    channels = parse_hex(colour)
    luminance = 0.0
    for weight, channel in zip(_WEIGHTS, channels, strict=True):
        luminance += weight * _linear(channel)
    return luminance


def contrast_ratio(colour: str, other: str) -> float:
    """The contrast ratio of two colours, from 1 for the same colour to 21."""
    lighter, darker = sorted(
        (relative_luminance(colour), relative_luminance(other)),
        reverse=True,
    )
    return (lighter + _LUMINANCE_OFFSET) / (darker + _LUMINANCE_OFFSET)
