"""Themes: the colour tokens resolved for one request, and the stylesheet serving them.

``resolve``, ``validate``, ``override_problems``, ``servable_theme``, ``preview_theme``
and ``render_stylesheet`` are pure functions over dictionaries. ``configured_theme``
reads the settings, and ``resolve_theme`` the request as well: it is the extension point
for a downstream application's own source of colours (docs/frontend.rst).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final
from typing import cast
from weakref import WeakKeyDictionary

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .contrast import HEX_COLOUR
from .contrast import contrast_ratio
from .contrast import parse_hex
from .palettes import BRAND_TOKENS
from .palettes import PAIRS
from .palettes import PALETTES
from .palettes import SETS
from .palettes import STATUS_TOKENS
from .palettes import TOKENS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.http import HttpRequest

logger = logging.getLogger(__name__)

# ``system`` leaves the choice between the light and dark sets to the browser
MODES: Final = ("system", "light", "dark")
# Where the showcase keeps a preview in the session, which is read under DEBUG only
PREVIEW_SESSION_KEY: Final = "ui_theme_preview"
# What a preview holds: the palette and the mode it selects, and its colours per set
PREVIEW_KEYS: Final = ("palette", "mode", *SETS)


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
    """One reason a theme cannot be served, and the colour set it is in, if any."""

    set_name: str | None
    message: str

    def __str__(self) -> str:
        if self.set_name is None:
            return self.message
        return f"{self.set_name}: {self.message}"


class InvalidThemeError(ValueError):
    """A theme that cannot be served, with every problem found in it."""

    def __init__(self, problems: Iterable[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(str(problem) for problem in self.problems))


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


def override_problems(override: object) -> list[Problem]:
    """What keeps ``override`` from applying over a palette as a brand's colours.

    An override maps ``light`` and ``dark``, either of them left out, to mappings of the
    tokens a brand may override, ``BRAND_TOKENS``, to ``#RRGGBB`` colours. The status
    tokens belong to the palette.
    """
    if not isinstance(override, Mapping):
        kind = type(override).__name__
        return [Problem(None, f"expected a mapping of light and dark, not {kind}")]
    problems: list[Problem] = []
    for set_name, colours in override.items():
        if set_name not in SETS:
            problems.append(Problem(None, f"unknown set {set_name!r}"))
        elif not isinstance(colours, Mapping):
            kind = type(colours).__name__
            message = f"expected a mapping of tokens to colours, not {kind}"
            problems.append(Problem(set_name, message))
        else:
            problems += _colour_problems(set_name, colours)
    return problems


def _colour_problems(set_name: str, colours: Mapping[object, object]) -> list[Problem]:
    problems: list[Problem] = []
    for token, value in colours.items():
        if token in STATUS_TOKENS:
            message = f"{token} belongs to the palette, not the brand"
        elif token not in BRAND_TOKENS:
            message = f"unknown token {token}"
        elif not isinstance(value, str) or not HEX_COLOUR.fullmatch(value):
            message = f"{token} is {value!r}, not a #RRGGBB colour"
        else:
            continue
        problems.append(Problem(set_name, message))
    return problems


def servable_theme(palette: object, mode: object, *overrides: object) -> Theme:
    """The theme of ``palette`` in ``mode`` with ``overrides`` applied in turn, once
    nothing keeps it from being served.

    Raises ``InvalidThemeError`` with every problem found: an unknown palette or mode
    and what keeps an override from applying, or else what ``validate`` finds in the
    result.
    """
    problems: list[Problem] = []
    if not isinstance(palette, str) or palette not in PALETTES:
        message = f"{palette!r} is not a palette: {', '.join(PALETTES)}"
        problems.append(Problem(None, message))
    if not isinstance(mode, str) or mode not in MODES:
        problems.append(Problem(None, f"{mode!r} is not a mode: {', '.join(MODES)}"))
    for override in overrides:
        problems += override_problems(override)
    if problems:
        raise InvalidThemeError(problems)
    theme = resolve(
        cast("str", palette),
        cast("str", mode),
        *cast("tuple[Mapping[str, Mapping[str, str]], ...]", overrides),
    )
    problems = validate(theme)
    if problems:
        raise InvalidThemeError(problems)
    return theme


def preview_theme(preview: object, brand: object) -> Theme:
    """The theme a preview asks for, resolved against the current palettes and brand.

    A preview is what the showcase keeps in the session: a ``palette``, a ``mode`` and,
    optionally, ``light`` and ``dark`` colours shaped as an override. They apply over
    the palette and ``brand``, the deployment's override, in that order. Raises
    ``InvalidThemeError`` when the result cannot be served.
    """
    if not isinstance(preview, Mapping):
        kind = type(preview).__name__
        problem = Problem(None, f"expected a preview mapping, not {kind}")
        raise InvalidThemeError([problem])
    unknown = [key for key in preview if key not in PREVIEW_KEYS]
    if unknown:
        raise InvalidThemeError(
            Problem(None, f"unknown preview key {key!r}") for key in unknown
        )
    colours = {name: preview[name] for name in SETS if name in preview}
    return servable_theme(preview.get("palette"), preview.get("mode"), brand, colours)


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
    """The theme ``UI_PALETTE``, ``UI_MODE`` and ``UI_BRAND`` configure, validated: one
    that cannot be served is a configuration error, which the system checks report
    before any page asks."""
    try:
        theme = servable_theme(settings.UI_PALETTE, settings.UI_MODE, settings.UI_BRAND)
    except InvalidThemeError as error:
        msg = f"The configured UI theme cannot be served: {error}"
        raise ImproperlyConfigured(msg) from error
    return theme


_resolved: WeakKeyDictionary[HttpRequest, Theme] = WeakKeyDictionary()


def resolve_theme(request: HttpRequest) -> Theme:
    """The theme of ``request``, resolved once per request.

    Under ``DEBUG`` the preview the showcase keeps in the session applies. A preview
    that can no longer be served, because a palette or ``UI_BRAND`` changed beneath
    it, is logged, removed from the session and replaced by the configured theme; a
    configured theme that cannot be served is a configuration error.

    A downstream application's own source of colours, a company record for one, goes
    in here the same way (docs/frontend.rst): resolve it with ``servable_theme``, and
    on ``InvalidThemeError`` log which record failed and fall back, leaving the record
    as it is.
    """
    theme = _resolved.get(request)
    if theme is None:
        theme = _previewed_theme(request) or configured_theme()
        _resolved[request] = theme
    return theme


def _previewed_theme(request: HttpRequest) -> Theme | None:
    """The theme of the session's preview under DEBUG; None without one."""
    session = getattr(request, "session", None)
    if not settings.DEBUG or session is None or PREVIEW_SESSION_KEY not in session:
        return None
    try:
        theme = preview_theme(session[PREVIEW_SESSION_KEY], settings.UI_BRAND)
    except InvalidThemeError as error:
        logger.warning(
            "The theme preview in the session cannot be served and was removed: %s",
            error,
        )
        del session[PREVIEW_SESSION_KEY]
        return None
    return theme
