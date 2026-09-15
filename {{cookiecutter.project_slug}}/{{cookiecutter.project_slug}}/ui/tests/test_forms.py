"""The showcase's forms: the sample's rule across two fields and the theme preview."""

from {{ cookiecutter.project_slug }}.ui.forms import PreviewForm
from {{ cookiecutter.project_slug }}.ui.forms import SampleForm
from {{ cookiecutter.project_slug }}.ui.palettes import PALETTES
from {{ cookiecutter.project_slug }}.ui.themes import resolve

SAMPLE = {"name": "Ada", "plan": "team", "seats": "2", "terms": "on"}


def test_a_team_plan_takes_two_seats():
    form = SampleForm({**SAMPLE, "seats": "1"})
    assert not form.is_valid()
    assert form.non_field_errors() == ["A team plan needs at least two seats."]
    valid = SampleForm(SAMPLE)
    assert valid.is_valid()
    assert valid.summary() == "Ada chose the Team plan; seats: 2."


def test_the_disabled_field_keeps_its_value():
    form = SampleForm({**SAMPLE, "reference": "changed"})
    assert form.is_valid()
    assert form.cleaned_data["reference"] == "SAMPLE-042"


def preview_form(data):
    return PreviewForm(data, beneath=resolve("blue", "system"))


def test_a_preview_keeps_the_colours_given():
    data = {
        "palette": "violet",
        "mode": "light",
        "dark_accent": "#c4b5fd",
        "light_fg": "",
    }
    form = preview_form(data)
    assert form.is_valid(), form.errors
    assert form.preview() == {
        "palette": "violet",
        "mode": "light",
        "light": {},
        "dark": {"accent": "#c4b5fd"},
    }


def test_a_preview_colour_is_written_as_hex():
    form = preview_form({"palette": "blue", "mode": "system", "light_accent": "#abc"})
    assert form.errors == {"light_accent": ["Enter a colour as #RRGGBB."]}


def test_a_preview_is_checked_over_the_brand(settings):
    data = {
        "palette": "blue",
        "mode": "system",
        "light_accent": "#3a6ee6",
        "light_surface": "#ffffff",
    }
    assert preview_form(data).is_valid()
    settings.UI_BRAND = {"light": {"accent-fg": "#f9fafb"}}
    form = preview_form(data)
    assert not form.is_valid()
    (error,) = form.non_field_errors()
    assert error.startswith("light: accent-fg on accent is 4.4")


def test_the_form_starts_from_the_theme_and_its_preview():
    beneath = resolve("teal", "dark")
    preview = {"palette": "teal", "mode": "dark", "light": {"accent": "#0f766e"}}
    initial = PreviewForm.initial_for(beneath, preview)
    form = PreviewForm(initial=initial, beneath=beneath)
    assert form["palette"].value() == "teal"
    assert form["light_accent"].value() == "#0f766e"
    assert form["dark_accent"].value() is None
    placeholder = form.fields["dark_accent"].widget.attrs["placeholder"]
    assert placeholder == PALETTES["teal"]["dark"]["accent"]
    assert form.shows_colours
    plain = PreviewForm(initial=PreviewForm.initial_for(beneath, None), beneath=beneath)
    assert not plain.shows_colours
