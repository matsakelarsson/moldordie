from {{ cookiecutter.project_slug }}.ui.checks import check_theme_settings


def test_the_default_settings_pass():
    assert check_theme_settings(None) == []


def test_an_unknown_palette_is_reported(settings):
    settings.UI_PALETTE = "pink"
    (error,) = check_theme_settings(None)
    assert error.id == "ui.E001"
    assert "pink" in error.msg
    assert error.hint is not None
    assert "blue, teal, violet" in error.hint


def test_an_unknown_mode_is_reported(settings):
    settings.UI_MODE = "auto"
    (error,) = check_theme_settings(None)
    assert error.id == "ui.E002"
    assert error.hint is not None
    assert "system, light, dark" in error.hint


def test_what_a_brand_may_not_override_is_reported(settings):
    settings.UI_BRAND = {"light": {"info": "#000000", "accent": "blue"}, "dusk": {}}
    errors = check_theme_settings(None)
    assert [error.id for error in errors] == ["ui.E003"] * 3
    assert [error.msg for error in errors] == [
        "UI_BRAND['light']: info belongs to the palette, not the brand.",
        "UI_BRAND['light']: accent is 'blue', not a #RRGGBB colour.",
        "UI_BRAND: unknown set 'dusk'.",
    ]
    assert errors[0].hint is not None
    assert "docs/frontend.rst" in errors[0].hint


def test_a_brand_that_breaks_a_pair_is_reported(settings):
    settings.UI_BRAND = {"dark": {"fg": "#1a1f2a"}}
    errors = check_theme_settings(None)
    assert {error.id for error in errors} == {"ui.E004"}
    expected = (
        "UI_BRAND breaks a pair of the dark set: "
        "fg on surface is 1.00:1, below 4.5:1 for text."
    )
    assert expected in [error.msg for error in errors]


def test_the_pairs_are_checked_once_the_settings_are_valid(settings):
    settings.UI_PALETTE = "pink"
    settings.UI_BRAND = {"dark": {"fg": "#1a1f2a"}}
    assert [error.id for error in check_theme_settings(None)] == ["ui.E001"]
