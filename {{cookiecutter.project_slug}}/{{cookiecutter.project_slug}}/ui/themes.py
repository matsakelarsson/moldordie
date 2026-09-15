"""Themes: the colour tokens resolved for one request, and the stylesheet serving them.

``resolve``, ``validate`` and ``render_stylesheet`` are pure functions over
dictionaries. ``resolve_theme`` is the one place that reads the settings and the
request, and the extension point for a downstream application's own source of
colours (docs/frontend.rst).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final
from weakref import WeakKeyDictionary

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .contrast import contrast_ratio
from .contrast import parse_hex
from .palettes import PAIRS
from .palettes import PALETTES
from .palettes import SETS
from .palettes import TOKENS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.http import HttpRequest

# ``system`` leaves the choice between the light and dark sets to the browser
MODES: Final = ("system", "light", "dark")


@dataclass(frozen=True)
class Theme:
    """Both resolved colour sets of a request, and the mode it asked for."""

    palette: str
    mode: str
    light: Mapping[str, str]
    dark: Mapping[str, str]

    @property
    def forced_mode(self) -> str | None:
        """The set the page must use, or None when the browser's preference decides."""
        return None if self.mode == "system" else self.mode

    def colours(self, set_name: str) -> Mapping[str, str]:
        """The ``light`` or ``dark`` set."""
        if set_name not in SETS:
            msg = f"{set_name!r} is not a colour set: {' or '.join(SETS)}"
            raise ValueError(msg)
        return self.light if set_name == "light" else self.dark


@dataclass(frozen=True)
class Problem:
    """One reason a theme cannot be served, in the set it was found in."""

    set_name: str
    message: str


def resolve(
    palette: str,
    mode: str,
    *overrides: Mapping[str, Mapping[str, str]],
) -> Theme:
    """The theme of ``palette`` in ``mode``, with each of ``overrides`` applied in turn.

    An override maps ``light`` and ``dark`` to token-to-colour mappings and may be
    partial: a set or a token it leaves out keeps the value beneath it. The result is
    not validated; ``validate`` says whether it can be served.
    """
    if palette not in PALETTES:
        msg = f"{palette!r} is not a palette: {', '.join(PALETTES)}"
        raise ValueError(msg)
    if mode not in MODES:
        msg = f"{mode!r} is not a mode: {', '.join(MODES)}"
        raise ValueError(msg)
    sets = {name: dict(PALETTES[palette][name]) for name in SETS}
    for override in overrides:
        for name in SETS:
            sets[name].update(override.get(name, {}))
    return Theme(palette, mode, sets["light"], sets["dark"])


def validate(theme: Theme) -> list[Problem]:
    """What keeps ``theme`` from being served: a token that is unknown or missing, a
    value that is not a colour, or a pair below the ratio the adjacency table asks.
    """
    problems: list[Problem] = []
    for set_name in SETS:
        colours = theme.colours(set_name)
        found = [
            Problem(set_name, f"unknown token {token}")
            for token in colours
            if token not in TOKENS
        ]
        found += [
            Problem(set_name, f"missing token {token}")
            for token in TOKENS
            if token not in colours
        ]
        for token, value in colours.items():
            try:
                parse_hex(value)
            except ValueError:
                found.append(
                    Problem(set_name, f"{token} is {value!r}, not a #RRGGBB colour"),
                )
        if not found:
            for pair in PAIRS:
                ratio = contrast_ratio(
                    colours[pair.foreground],
                    colours[pair.background],
                )
                if ratio < pair.ratio:
                    found.append(
                        Problem(
                            set_name,
                            f"{pair.foreground} on {pair.background} is {ratio:.2f}:1, "
                            f"below {pair.ratio}:1 for {pair.where}",
                        ),
                    )
        problems += found
    return problems


def render_stylesheet(theme: Theme) -> str:
    """``theme`` as CSS custom properties: the light set on the root, the dark set
    under the browser's preference unless light is forced, and again when dark is.
    """
    light = _declarations(theme.light)
    dark = _declarations(theme.dark)
    preferred = '@media (prefers-color-scheme: dark){:root:not([data-ui-mode="light"]){'
    forced = ':root[data-ui-mode="dark"]{'
    return ":root{" + light + "}\n" + preferred + dark + "}}\n" + forced + dark + "}\n"


def _declarations(colours: Mapping[str, str]) -> str:
    declarations = []
    for token in TOKENS:
        value = colours[token]
        parse_hex(value)
        declarations.append(f"--ui-{token}:{value};")
    return "".join(declarations)


def configured_theme() -> Theme:
    """The theme ``UI_PALETTE`` and ``UI_MODE`` configure, validated: an invalid one is
    a configuration error, which the system checks report before any page asks."""
    try:
        theme = resolve(settings.UI_PALETTE, settings.UI_MODE)
    except ValueError as error:
        msg = f"The UI theme settings are invalid: {error}"
        raise ImproperlyConfigured(msg) from error
    problems = validate(theme)
    if problems:
        details = "; ".join(f"{p.set_name}: {p.message}" for p in problems)
        msg = f"The configured UI theme cannot be served: {details}"
        raise ImproperlyConfigured(msg)
    return theme


_resolved: WeakKeyDictionary[HttpRequest, Theme] = WeakKeyDictionary()


def resolve_theme(request: HttpRequest) -> Theme:
    """The theme of ``request``, resolved once per request.

    This is where a downstream application merges its own source of colours, a company
    record for one: resolve it as an override of the configured theme, validate the
    result, and fall back to ``configured_theme()`` when it cannot be served.
    """
    try:
        return _resolved[request]
    except KeyError:
        theme = configured_theme()
        _resolved[request] = theme
        return theme
