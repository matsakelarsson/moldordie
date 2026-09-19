"""Django's form renderer on the project's templates: field, widgets and errors.

``FORM_RENDERER`` sends every form through ``templates/django/forms/``. The field
template keeps Django's associations between a widget, its label, its help text and its
errors; the widget templates give each control daisyUI's class for its type and merge
the widget's own into the one class attribute.
"""

from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.forms import SampleForm
from {{ cookiecutter.project_slug }}.tests.forms import WidgetsForm
from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements

# The sample form's fields that get a wrapper: the hidden one is its widget alone
VISIBLE_FIELDS = 4
CHECK_LABEL = "label text-base-content whitespace-normal"
HELP = "text-base-content/70"


def named(html, tag, key, value):
    """The one ``tag`` element whose ``key`` attribute is ``value``."""
    found = [attrs for attrs in elements(html, tag) if attrs.get(key) == value]
    assert len(found) == 1, found
    return found[0]


def test_a_field_in_order_with_its_associations():
    html = str(SampleForm(data={}))

    assert '<label class="fieldset-legend" for="id_name">Name</label>' in html
    assert named(html, "input", "name", "name") == {
        "type": "text",
        "name": "name",
        "class": "input aria-invalid:input-error w-full",
        "required": None,
        "aria-invalid": "true",
        "aria-describedby": "id_name_helptext id_name_error",
        "id": "id_name",
    }
    assert named(html, "ul", "id", "id_name_error") == {
        "class": "errorlist text-error text-sm",
        "id": "id_name_error",
    }
    assert named(html, "div", "id", "id_name_helptext") == {
        "class": HELP,
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


def test_a_checkbox_sits_inside_its_label():
    html = str(SampleForm())

    assert named(html, "label", "for", "id_agree") == {
        "class": CHECK_LABEL,
        "for": "id_agree",
    }
    assert named(html, "input", "name", "agree") == {
        "type": "checkbox",
        "name": "agree",
        "class": "checkbox aria-invalid:checkbox-error",
        "id": "id_agree",
    }
    start = html.index('for="id_agree"')
    end = html.index("</label>", start)
    assert start < html.index('name="agree"') < html.index("<span>Agree</span>") < end


def test_a_choice_group_is_a_fieldset_with_a_legend():
    html = str(SampleForm(data={}))

    assert element(html, "fieldset") == {
        "class": "fieldset",
        "aria-describedby": "id_flavour_helptext id_flavour_error",
    }
    assert '<legend class="fieldset-legend">Flavour</legend>' in html
    radios = [attrs for attrs in elements(html, "input") if attrs["type"] == "radio"]
    assert [radio["id"] for radio in radios] == ["id_flavour_0", "id_flavour_1"]
    assert all(radio["aria-invalid"] == "true" for radio in radios)
    assert all(radio["class"] == "radio aria-invalid:radio-error" for radio in radios)
    assert named(html, "label", "for", "id_flavour_0")["class"] == CHECK_LABEL
    assert named(html, "ul", "id", "id_flavour_error")["class"].startswith("errorlist ")
    assert named(html, "div", "id", "id_flavour_helptext")["class"] == HELP
    assert "Pick one." in html


def test_a_hidden_field_is_its_widget_alone():
    html = str(SampleForm())

    assert named(html, "input", "name", "token") == {
        "type": "hidden",
        "name": "token",
        "id": "id_token",
    }
    assert html.count('class="fieldset"') == VISIBLE_FIELDS


def test_a_widget_with_its_own_id_keeps_it():
    html = str(SampleForm())

    assert named(html, "label", "for", "custom-id") == {
        "class": "fieldset-legend",
        "for": "custom-id",
    }
    assert named(html, "input", "name", "custom")["id"] == "custom-id"


def test_a_form_without_ids_keeps_its_labels_as_text():
    html = str(SampleForm(auto_id=False))

    assert '<span class="fieldset-legend">Name</span>' in html
    assert '<legend class="fieldset-legend">Flavour</legend>' in html
    helps = [attrs for attrs in elements(html, "div") if attrs.get("class") == HELP]
    assert helps == [{"class": HELP}, {"class": HELP}]
    assert "How to address you." in html
    labels = elements(html, "label")
    assert [attrs.get("for") for attrs in labels] == [None, None, None, "custom-id"]
    assert "helptext" not in html


def test_a_label_set_on_the_bound_field_is_shown():
    form = SampleForm()
    form["name"].label = "Full name"

    html = str(form)

    assert '<label class="fieldset-legend" for="id_name">Full name</label>' in html


class WholeForm(SampleForm):
    def clean(self):
        msg = "Nothing agrees."
        raise ValidationError(msg)


def test_errors_of_the_whole_form_come_first():
    html = str(WholeForm(data={}))

    nonfield = "errorlist nonfield text-error text-sm font-medium"
    assert named(html, "ul", "class", nonfield) == {"class": nonfield}
    assert html.index("Nothing agrees.") < html.index('for="id_name"')
    assert html.count('class="fieldset"') == VISIBLE_FIELDS


class Stored:
    """A file a model already holds, as a clearable file input shows it."""

    url = "/media/avatar.png"

    def __str__(self):
        return "avatar.png"


WIDGET_CLASSES = [
    ("input", "text", "input aria-invalid:input-error w-full"),
    ("input", "email", "input aria-invalid:input-error w-full"),
    ("input", "password", "input aria-invalid:input-error w-full"),
    ("input", "number", "input aria-invalid:input-error w-full"),
    ("input", "day", "input aria-invalid:input-error w-full"),
    ("input", "level", "range aria-invalid:range-error w-full"),
    ("textarea", "notes", "textarea aria-invalid:textarea-error w-full"),
    ("select", "colour", "select aria-invalid:select-error w-full"),
    ("select", "colours", "select aria-invalid:select-error w-full"),
    ("input", "agree", "checkbox aria-invalid:checkbox-error"),
    ("input", "notify", "aria-invalid:toggle-error toggle"),
    ("input", "upload", "file-input aria-invalid:file-input-error w-full"),
    ("input", "avatar", "file-input aria-invalid:file-input-error w-full"),
    ("input", "tagged", "input aria-invalid:input-error w-full validator"),
]


@pytest.mark.parametrize(("tag", "name", "classes"), WIDGET_CLASSES)
def test_a_widget_gets_the_class_of_its_kind(tag, name, classes):
    html = str(WidgetsForm())

    assert named(html, tag, "name", name)["class"] == classes


def test_the_options_of_a_group_get_their_class_each():
    html = str(WidgetsForm())

    inputs = elements(html, "input")
    radios = {attrs["class"] for attrs in inputs if attrs["name"] == "size"}
    assert radios == {"radio aria-invalid:radio-error"}
    boxes = {attrs["class"] for attrs in inputs if attrs["name"] == "toppings"}
    assert boxes == {"checkbox aria-invalid:checkbox-error"}
    # A named group of options is shown under its name, and so is a select's
    assert '<span class="font-semibold">Cheese</span>' in html
    assert element(html, "optgroup") == {"label": "Warm"}
    assert named(html, "select", "name", "colours")["multiple"] is None


def test_a_class_of_the_widgets_own_is_merged_into_the_one_attribute():
    html = str(WidgetsForm())

    tag = html[html.index('name="tagged"') - 30 : html.index('id="id_tagged"')]
    assert tag.count("class=") == 1
    assert named(html, "input", "name", "tagged")["required"] is None


def test_a_file_a_model_holds_is_shown_with_the_box_that_clears_it():
    html = str(WidgetsForm(initial={"avatar": Stored()}))

    assert named(html, "a", "href", "/media/avatar.png") == {
        "class": "link",
        "href": "/media/avatar.png",
    }
    assert named(html, "input", "name", "avatar-clear") == {
        "type": "checkbox",
        "class": "checkbox checkbox-sm",
        "name": "avatar-clear",
        "id": "avatar-clear_id",
    }
    assert named(html, "label", "for", "avatar-clear_id")["class"] == CHECK_LABEL


@pytest.mark.django_db
def test_the_admin_keeps_its_own_look(admin_client):
    """The renderer is the project's everywhere, the admin included: its widgets come
    through the same templates and keep the classes its stylesheets style."""
    response = admin_client.get(reverse("admin:users_user_add"))

    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert "css/tailwind.css" not in html
    classes = [attrs.get("class") or "" for attrs in elements(html, "input")]
    assert any(value.endswith(" vTextField") for value in classes)
