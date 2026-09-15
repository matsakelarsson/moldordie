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
