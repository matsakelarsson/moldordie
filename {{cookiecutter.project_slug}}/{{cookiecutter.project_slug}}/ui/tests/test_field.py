"""The field component, its adapter for Django's form renderer, and ``ui_label``."""

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from {{ cookiecutter.project_slug }}.ui.templatetags.ui import ui_label
from {{ cookiecutter.project_slug }}.ui.tests.forms import SampleForm
from {{ cookiecutter.project_slug }}.ui.tests.markup import element
from {{ cookiecutter.project_slug }}.ui.tests.markup import elements

# The sample form's fields that get a wrapper: the hidden one is its widget alone
VISIBLE_FIELDS = 4


def render_fields(rf, form):
    context = {"form": form}
    return render_to_string("tests/field.html", context, request=rf.get("/"))


def named(html, tag, key, value):
    """The one ``tag`` element whose ``key`` attribute is ``value``."""
    found = [attrs for attrs in elements(html, tag) if attrs.get(key) == value]
    assert len(found) == 1, found
    return found[0]


@pytest.mark.usefixtures("fixture_templates")
def test_a_bound_field_in_order_with_its_associations(rf):
    html = render_fields(rf, SampleForm(data={}))

    assert named(html, "div", "data-probe", "name") == {
        "class": "ui-field ui-field-invalid",
        "data-probe": "name",
    }
    assert '<label class="ui-label" for="id_name">Name</label>' in html
    assert named(html, "input", "name", "name") == {
        "type": "text",
        "name": "name",
        "required": None,
        "aria-invalid": "true",
        "aria-describedby": "id_name_helptext id_name_error",
        "id": "id_name",
    }
    assert '<ul class="errorlist" id="id_name_error">' in html
    assert named(html, "div", "id", "id_name_helptext") == {
        "class": "ui-help",
        "id": "id_name_helptext",
    }
    assert "How to address you." in html
    positions = [
        html.index('for="id_name"'),
        html.index('name="name"'),
        html.index('id="id_name_error"'),
        html.index('id="id_name_helptext"'),
    ]
    assert positions == sorted(positions)


@pytest.mark.usefixtures("fixture_templates")
def test_a_checkbox_sits_inside_its_label(rf):
    html = render_fields(rf, SampleForm())

    assert named(html, "label", "for", "id_agree") == {
        "class": "ui-label ui-label-check",
        "for": "id_agree",
    }
    start = html.index('for="id_agree"')
    end = html.index("</label>", start)
    assert start < html.index('name="agree"') < html.index("<span>Agree</span>") < end


@pytest.mark.usefixtures("fixture_templates")
def test_a_choice_group_is_a_fieldset_with_a_legend(rf):
    html = render_fields(rf, SampleForm(data={}))

    assert element(html, "fieldset") == {
        "class": "ui-field ui-field-group ui-field-invalid",
        "aria-describedby": "id_flavour_helptext id_flavour_error",
    }
    assert '<legend class="ui-legend">Flavour</legend>' in html
    radios = [attrs for attrs in elements(html, "input") if attrs["type"] == "radio"]
    assert [radio["id"] for radio in radios] == ["id_flavour_0", "id_flavour_1"]
    assert all(radio["aria-invalid"] == "true" for radio in radios)
    assert '<ul class="errorlist" id="id_flavour_error">' in html
    assert named(html, "div", "id", "id_flavour_helptext") == {
        "class": "ui-help",
        "id": "id_flavour_helptext",
    }
    assert "Pick one." in html


@pytest.mark.usefixtures("fixture_templates")
def test_a_hidden_field_is_its_widget_alone(rf):
    html = render_fields(rf, SampleForm())

    assert named(html, "input", "name", "token") == {
        "type": "hidden",
        "name": "token",
        "id": "id_token",
    }
    assert html.count('class="ui-field') == VISIBLE_FIELDS


@pytest.mark.usefixtures("fixture_templates")
def test_a_widget_with_its_own_id_keeps_it(rf):
    html = render_fields(rf, SampleForm())

    assert named(html, "label", "for", "custom-id") == {
        "class": "ui-label",
        "for": "custom-id",
    }
    assert named(html, "input", "name", "custom")["id"] == "custom-id"


@pytest.mark.usefixtures("fixture_templates")
def test_a_form_without_ids_keeps_its_labels_as_text(rf):
    html = render_fields(rf, SampleForm(auto_id=False))

    assert '<span class="ui-label">Name</span>' in html
    assert '<span class="ui-legend">Flavour</span>' in html
    helps = [a for a in elements(html, "div") if a.get("class") == "ui-help"]
    assert helps == [{"class": "ui-help"}, {"class": "ui-help"}]
    assert "How to address you." in html
    labels = elements(html, "label")
    assert [attrs.get("for") for attrs in labels] == [None, None, None, "custom-id"]
    assert "helptext" not in html


@pytest.mark.usefixtures("fixture_templates")
def test_a_label_set_on_the_bound_field_is_shown(rf):
    form = SampleForm()
    form["name"].label = "Full name"

    html = render_fields(rf, form)

    assert '<label class="ui-label" for="id_name">Full name</label>' in html


class WholeForm(SampleForm):
    def clean(self):
        msg = "Nothing agrees."
        raise ValidationError(msg)


def test_a_form_rendered_by_django_goes_through_the_component():
    html = str(WholeForm(data={}))

    assert '<ul class="errorlist nonfield"><li>Nothing agrees.</li></ul>' in html
    assert html.count('class="ui-field') == VISIBLE_FIELDS
    assert '<label class="ui-label" for="id_name">Name</label>' in html
    assert '<legend class="ui-legend">Flavour</legend>' in html
    assert "<span>Agree</span>" in html
    assert named(html, "input", "name", "token") == {
        "type": "hidden",
        "name": "token",
        "id": "id_token",
    }


def test_ui_label_writes_the_tag_without_the_suffix():
    form = SampleForm(label_suffix=":")

    label = '<label class="ui-label" for="id_name">Name</label>'
    assert ui_label(form["name"]) == label
    legend = '<legend class="ui-legend">Flavour</legend>'
    assert ui_label(form["flavour"], "legend") == legend
    bare = SampleForm(auto_id=False)["name"]
    assert ui_label(bare) == '<span class="ui-label">Name</span>'
    with pytest.raises(TypeError, match="takes a bound field"):
        ui_label(forms.CharField())
