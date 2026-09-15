import pytest
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from {{ cookiecutter.project_slug }}.ui.templatetags.ui import ui_attr
from {{ cookiecutter.project_slug }}.ui.templatetags.ui import ui_attrs
from {{ cookiecutter.project_slug }}.ui.templatetags.ui import ui_url
from {{ cookiecutter.project_slug }}.ui.tests.markup import element


class Attrs:
    """The shape of Cotton's attrs: ``attrs_dict()`` leaves out the declared inputs."""

    def __init__(self, forwarded):
        self.forwarded = forwarded

    def attrs_dict(self):
        return self.forwarded


def test_ui_attrs_reads_the_undeclared_attributes():
    assert ui_attrs(Attrs({"id": "x", "hidden": True})) == 'id="x" hidden'
    assert ui_attrs({"id": "x"}) == 'id="x"'
    with pytest.raises(TypeError, match="takes a component's attrs"):
        ui_attrs("id")


def test_ui_attr_encodes_one_value():
    assert ui_attr('a "b" <c>') == "a &quot;b&quot; &lt;c&gt;"
    assert ui_attr(mark_safe('&lt;c&gt; "b"')) == "&lt;c&gt; &quot;b&quot;"
    assert ui_attr(None) == ""
    assert ui_attr(0) == "0"


def test_ui_url_applies_the_named_policy():
    assert ui_url("https://example.com/?a=1&b=2") == "https://example.com/?a=1&amp;b=2"
    assert ui_url("/x/", "local") == "/x/"
    with pytest.raises(ValueError, match="scheme"):
        ui_url("https://example.com/", "local")
    with pytest.raises(ValueError, match="http or https"):
        ui_url(mark_safe("javascript&#58;alert(1)"))
    assert ui_url("javascript&#58;alert(1)") == "javascript&amp;#58;alert(1)"
    with pytest.raises(ValueError, match="not a URL policy"):
        ui_url("/x/", "remote")


@pytest.mark.usefixtures("fixture_templates")
def test_a_component_forwards_through_the_filters(rf):
    context = {
        "title": 'Say "hi" & <go>',
        "count": 0,
        "expanded": False,
        "disabled": True,
        "url": "/users/?page=2&sort=name",
    }
    html = render_to_string("tests/forward.html", context, request=rf.get("/"))
    assert element(html, "button") == {
        "type": "button",
        "title": 'Say "hi" & <go>',
        "id": "go",
        "data-count": "0",
        "aria-expanded": "false",
        "disabled": None,
        "hx-get": "/users/?page=2&sort=name",
    }
    assert "Go" in html


@pytest.mark.usefixtures("fixture_templates")
def test_a_forbidden_attribute_fails_the_render(rf):
    with pytest.raises(ValueError, match="declares and writes it itself"):
        render_to_string("tests/forbidden.html", {}, request=rf.get("/"))
