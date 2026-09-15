import pytest

from {{ cookiecutter.project_slug }}.ui.contrast import contrast_ratio
from {{ cookiecutter.project_slug }}.ui.contrast import parse_hex
from {{ cookiecutter.project_slug }}.ui.palettes import BRAND_TOKENS
from {{ cookiecutter.project_slug }}.ui.palettes import PAIRS
from {{ cookiecutter.project_slug }}.ui.palettes import PALETTES
from {{ cookiecutter.project_slug }}.ui.palettes import SETS
from {{ cookiecutter.project_slug }}.ui.palettes import STATUS_TOKENS
from {{ cookiecutter.project_slug }}.ui.palettes import TOKENS

PALETTE_SETS = [(palette, set_name) for palette in PALETTES for set_name in SETS]
TOKEN_COUNT = 26
PAIR_COUNT = 46


def test_the_tokens():
    assert len(TOKENS) == TOKEN_COUNT
    assert len(set(TOKENS)) == TOKEN_COUNT
    assert set(BRAND_TOKENS).isdisjoint(STATUS_TOKENS)
    assert PALETTES["blue"]["light"]["accent"] != PALETTES["blue"]["light"]["info"]


def test_the_adjacency_table_names_every_checked_token():
    """Every token but the decorative border meets another somewhere on the page."""
    assert len(PAIRS) == PAIR_COUNT
    named = {pair.foreground for pair in PAIRS} | {pair.background for pair in PAIRS}
    assert named == set(TOKENS) - {"border"}
    assert all(pair.foreground != pair.background for pair in PAIRS)


@pytest.mark.parametrize(("palette", "set_name"), PALETTE_SETS)
def test_every_palette_is_complete(palette, set_name):
    colours = PALETTES[palette][set_name]
    assert set(colours) == set(TOKENS)
    assert len(colours) == len(TOKENS)
    for value in colours.values():
        parse_hex(value)


@pytest.mark.parametrize(("palette", "set_name"), PALETTE_SETS)
def test_every_palette_meets_the_adjacency_table(palette, set_name):
    colours = PALETTES[palette][set_name]
    failures = []
    for pair in PAIRS:
        ratio = contrast_ratio(colours[pair.foreground], colours[pair.background])
        if ratio < pair.ratio:
            failures.append(
                f"{pair.foreground} on {pair.background}: {ratio:.3f}, {pair}",
            )
    assert failures == []
