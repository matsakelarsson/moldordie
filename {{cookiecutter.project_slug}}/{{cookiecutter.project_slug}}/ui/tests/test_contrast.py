import pytest

from {{ cookiecutter.project_slug }}.ui.contrast import contrast_ratio
from {{ cookiecutter.project_slug }}.ui.contrast import parse_hex
from {{ cookiecutter.project_slug }}.ui.contrast import relative_luminance

MAX_RATIO = 21
AA_TEXT = 4.5


def test_reference_ratios():
    """The extremes and two colours either side of AA, as WCAG's formula gives them."""
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(MAX_RATIO)
    assert contrast_ratio("#777777", "#777777") == 1
    assert contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.005)
    assert contrast_ratio("#767676", "#ffffff") > AA_TEXT
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.005)
    assert contrast_ratio("#777777", "#ffffff") < AA_TEXT


def test_ratio_is_symmetric():
    assert contrast_ratio("#1b1f27", "#f4f5f7") == contrast_ratio("#f4f5f7", "#1b1f27")


def test_luminance_extremes():
    assert relative_luminance("#000000") == 0
    assert relative_luminance("#ffffff") == pytest.approx(1)
    assert relative_luminance("#FFFFFF") == pytest.approx(1)


@pytest.mark.parametrize("colour", ["#fff", "ffffff", "#ggg000", "#1234567", "", "red"])
def test_only_six_digit_hex_colours(colour):
    with pytest.raises(ValueError, match="not a #RRGGBB colour"):
        parse_hex(colour)


def test_channels():
    assert parse_hex("#0a141e") == (10, 20, 30)
