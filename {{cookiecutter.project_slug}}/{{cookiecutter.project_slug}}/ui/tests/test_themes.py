import pytest
from django.core.exceptions import ImproperlyConfigured

from {{ cookiecutter.project_slug }}.ui.palettes import PALETTES
from {{ cookiecutter.project_slug }}.ui.palettes import TOKENS
from {{ cookiecutter.project_slug }}.ui.themes import MODES
from {{ cookiecutter.project_slug }}.ui.themes import Theme
from {{ cookiecutter.project_slug }}.ui.themes import configured_theme
from {{ cookiecutter.project_slug }}.ui.themes import render_stylesheet
from {{ cookiecutter.project_slug }}.ui.themes import resolve
from {{ cookiecutter.project_slug }}.ui.themes import resolve_theme
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
