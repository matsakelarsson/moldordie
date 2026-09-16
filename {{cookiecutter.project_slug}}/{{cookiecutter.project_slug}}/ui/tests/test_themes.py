import logging

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ImproperlyConfigured

from {{ cookiecutter.project_slug }}.ui.palettes import PALETTES
from {{ cookiecutter.project_slug }}.ui.palettes import TOKENS
from {{ cookiecutter.project_slug }}.ui.themes import MODES
from {{ cookiecutter.project_slug }}.ui.themes import PREVIEW_SESSION_KEY
from {{ cookiecutter.project_slug }}.ui.themes import InvalidThemeError
from {{ cookiecutter.project_slug }}.ui.themes import Theme
from {{ cookiecutter.project_slug }}.ui.themes import configured_theme
from {{ cookiecutter.project_slug }}.ui.themes import override_problems
from {{ cookiecutter.project_slug }}.ui.themes import preview_theme
from {{ cookiecutter.project_slug }}.ui.themes import render_stylesheet
from {{ cookiecutter.project_slug }}.ui.themes import resolve
from {{ cookiecutter.project_slug }}.ui.themes import resolve_theme
from {{ cookiecutter.project_slug }}.ui.themes import servable_theme
from {{ cookiecutter.project_slug }}.ui.themes import validate


def test_resolve_copies_the_palette():
    theme = resolve("teal", "system")
    teal = PALETTES["teal"]
    assert theme == Theme("teal", "system", teal["light"], teal["dark"])
    assert theme.light is not PALETTES["teal"]["light"]
    assert theme.forced_mode is None
    assert resolve("blue", "dark").forced_mode == "dark"
    assert MODES == ("system", "light", "dark")


def test_resolve_applies_partial_overrides_in_turn():
    theme = resolve(
        "blue",
        "light",
        {"light": {"accent": "#111111"}},
        {
            "light": {"accent": "#222222", "surface": "#eeeeee"},
            "dark": {"accent": "#dddddd"},
        },
    )
    assert theme.light["accent"] == "#222222"
    assert theme.light["surface"] == "#eeeeee"
    assert theme.light["bg"] == PALETTES["blue"]["light"]["bg"]
    assert theme.dark["accent"] == "#dddddd"
    assert theme.colours("dark") is theme.dark


def test_resolve_refuses_unknown_names():
    with pytest.raises(ValueError, match="not a palette"):
        resolve("pink", "system")
    with pytest.raises(ValueError, match="not a mode"):
        resolve("blue", "auto")
    with pytest.raises(ValueError, match="not a colour set"):
        resolve("blue", "system").colours("system")


@pytest.mark.parametrize("palette", list(PALETTES))
@pytest.mark.parametrize("mode", MODES)
def test_the_built_in_palettes_validate(palette, mode):
    assert validate(resolve(palette, mode)) == []


def test_validate_reports_tokens_and_colours_before_contrast():
    override = {"light": {"accent": "#12345", "extra": "#000000"}}
    theme = resolve("blue", "system", override)
    problems = validate(theme)
    assert [(p.set_name, p.message) for p in problems] == [
        ("light", "unknown token extra"),
        ("light", "accent is '#12345', not a #RRGGBB colour"),
    ]
    missing = Theme("blue", "system", {}, PALETTES["blue"]["dark"])
    expected = {f"missing token {token}" for token in TOKENS}
    assert {p.message for p in validate(missing)} == expected


def test_validate_reports_a_pair_below_its_ratio():
    theme = resolve("blue", "system", {"dark": {"fg": "#1a1f2a"}})
    messages = [p.message for p in validate(theme) if p.set_name == "dark"]
    assert "fg on surface is 1.00:1, below 4.5:1 for text" in messages
    assert all("fg on bg" in m or "fg on surface" in m for m in messages)
    assert not [p for p in validate(theme) if p.set_name == "light"]


def test_render_stylesheet_has_the_three_fixed_blocks():
    theme = resolve("violet", "light")
    css = render_stylesheet(theme)
    root, dark_media, forced_dark, trailing = css.split("\n")
    assert trailing == ""
    assert root.startswith(":root{--ui-bg:#ffffff;--ui-surface:#f4f5f7;")
    assert root.endswith("--ui-error-tint:#fee2e2;}")
    preferred = '@media (prefers-color-scheme: dark){:root:not([data-ui-mode="light"]){'
    assert dark_media.startswith(preferred + "--ui-bg:#0f1218;")
    assert dark_media.endswith("}}")
    assert forced_dark.startswith(':root[data-ui-mode="dark"]{--ui-bg:#0f1218;')
    assert forced_dark.endswith("}")
    for token in TOKENS:
        assert root.count(f"--ui-{token}:") == 1
        assert forced_dark.count(f"--ui-{token}:") == 1
    assert f"--ui-accent:{PALETTES['violet']['light']['accent']};" in root


def test_render_stylesheet_writes_colours_only():
    theme = resolve("blue", "system", {"light": {"accent": "red; background: url(x)"}})
    with pytest.raises(ValueError, match="not a #RRGGBB colour"):
        render_stylesheet(theme)


def test_configured_theme_reads_the_settings(settings):
    settings.UI_PALETTE = "teal"
    settings.UI_MODE = "dark"
    assert configured_theme() == resolve("teal", "dark")


def test_an_invalid_configuration_is_a_configuration_error(settings):
    settings.UI_PALETTE = "pink"
    with pytest.raises(ImproperlyConfigured, match="not a palette"):
        configured_theme()


def test_resolve_theme_resolves_once_per_request(rf):
    request = rf.get("/")
    theme = resolve_theme(request)
    assert theme == configured_theme()
    assert resolve_theme(request) is theme
    assert resolve_theme(rf.get("/")) is not theme


def test_override_problems_say_what_a_brand_may_not_do():
    assert override_problems({"light": {"accent": "#123456"}, "dark": {}}) == []
    assert override_problems({}) == []
    problems = override_problems(
        {
            "light": {"info": "#123456", "shade": "#123456", "accent": "blue"},
            "dusk": {},
            "dark": ["accent"],
        },
    )
    assert [str(problem) for problem in problems] == [
        "light: info belongs to the palette, not the brand",
        "light: unknown token shade",
        "light: accent is 'blue', not a #RRGGBB colour",
        "unknown set 'dusk'",
        "dark: expected a mapping of tokens to colours, not list",
    ]
    (problem,) = override_problems(["light"])
    assert str(problem) == "expected a mapping of light and dark, not list"


def test_servable_theme_raises_with_every_problem():
    theme = servable_theme("teal", "dark", {"dark": {"accent": "#5eead4"}})
    assert theme.dark["accent"] == "#5eead4"
    with pytest.raises(InvalidThemeError) as caught:
        servable_theme("pink", "auto", {"light": {"info": "#000000"}})
    assert [str(problem) for problem in caught.value.problems] == [
        "'pink' is not a palette: blue, teal, violet",
        "'auto' is not a mode: system, light, dark",
        "light: info belongs to the palette, not the brand",
    ]
    with pytest.raises(InvalidThemeError, match=r"light: fg on bg is 1\.00:1"):
        servable_theme("blue", "system", {"light": {"fg": "#ffffff"}})


def test_configured_theme_applies_the_brand(settings):
    settings.UI_BRAND = {"light": {"border": "#cccccc"}}
    theme = configured_theme()
    assert theme.light["border"] == "#cccccc"
    assert theme.dark == PALETTES["blue"]["dark"]


def test_a_brand_that_breaks_a_pair_is_a_configuration_error(settings):
    settings.UI_BRAND = {"dark": {"fg": "#1a1f2a"}}
    with pytest.raises(ImproperlyConfigured, match=r"dark: fg on surface is 1\.00:1"):
        configured_theme()


def test_a_preview_resolves_over_the_brand():
    brand = {"light": {"border": "#cccccc"}, "dark": {"border": "#3a4150"}}
    preview = {"palette": "violet", "mode": "light", "dark": {"accent": "#c4b5fd"}}
    theme = preview_theme(preview, brand)
    assert (theme.palette, theme.mode) == ("violet", "light")
    assert theme.light["border"] == "#cccccc"
    assert theme.dark["border"] == "#3a4150"
    assert theme.dark["accent"] == "#c4b5fd"
    # The preview's colours apply over the brand's
    theme = preview_theme({**preview, "light": {"border": "#bbbbbb"}}, brand)
    assert theme.light["border"] == "#bbbbbb"


def test_a_preview_that_cannot_be_served():
    with pytest.raises(InvalidThemeError, match="expected a preview mapping, not str"):
        preview_theme("teal", {})
    with pytest.raises(InvalidThemeError, match="unknown preview key 'accent'"):
        preview_theme({"palette": "teal", "mode": "dark", "accent": "#000000"}, {})
    with pytest.raises(InvalidThemeError, match="None is not a mode"):
        preview_theme({"palette": "teal"}, {})


def with_preview(rf, preview):
    request = rf.get("/")
    request.session = SessionStore()
    request.session[PREVIEW_SESSION_KEY] = preview
    return request


def test_a_preview_applies_under_debug_only(rf, settings):
    preview = {"palette": "violet", "mode": "dark"}
    assert resolve_theme(with_preview(rf, preview)) == configured_theme()
    settings.DEBUG = True
    assert resolve_theme(with_preview(rf, preview)) == resolve("violet", "dark")
    # A request that has no session has no preview
    assert resolve_theme(rf.get("/")) == configured_theme()


def test_a_stale_preview_is_logged_removed_and_replaced(rf, settings, caplog):
    settings.DEBUG = True
    request = with_preview(rf, {"palette": "pink", "mode": "dark"})

    with caplog.at_level(logging.WARNING, logger=resolve_theme.__module__):
        theme = resolve_theme(request)

    assert theme == configured_theme()
    assert PREVIEW_SESSION_KEY not in request.session
    (record,) = [r for r in caplog.records if r.name == resolve_theme.__module__]
    assert record.levelno == logging.WARNING
    assert "'pink' is not a palette" in record.getMessage()


def test_a_stale_preview_over_an_invalid_configuration_raises(rf, settings):
    settings.DEBUG = True
    settings.UI_PALETTE = "pink"
    preview = {"palette": "blue", "mode": "system", "light": {"fg": "#ffffff"}}
    with pytest.raises(ImproperlyConfigured, match="not a palette"):
        resolve_theme(with_preview(rf, preview))
