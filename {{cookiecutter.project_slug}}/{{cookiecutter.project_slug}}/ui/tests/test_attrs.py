import pytest
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from {{ cookiecutter.project_slug }}.ui.attrs import attribute_value
from {{ cookiecutter.project_slug }}.ui.attrs import serialize_attrs
from {{ cookiecutter.project_slug }}.ui.attrs import url_value
from {{ cookiecutter.project_slug }}.ui.links import local_url
from {{ cookiecutter.project_slug }}.ui.links import navigation_url
from {{ cookiecutter.project_slug }}.ui.tests.markup import element


def button(attrs):
    return element(f"<button {serialize_attrs(attrs)}>x</button>", "button")


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("class", "declares and writes it itself"),
        ("Style", "forbids inline code"),
        ("onclick", "forbids inline code"),
        ("ONMOUSEOVER", "forbids inline code"),
        ("hx-on:click", "forbids inline code"),
        ("hx-on::after-request", "forbids inline code"),
        ("data-hx-on:click", "forbids inline code"),
    ],
)
def test_forbidden_names(name, reason):
    with pytest.raises(ValueError, match=reason):
        serialize_attrs({name: "x"})


@pytest.mark.parametrize("name", ["", "1st", "a b", 'x"', "ä", "a=b"])
def test_invalid_names(name):
    with pytest.raises(ValueError, match="not an attribute name"):
        serialize_attrs({name: "x"})


def test_duplicate_names_after_case_folding():
    with pytest.raises(ValueError, match="given twice"):
        serialize_attrs({"id": "a", "ID": "b"})


def test_none_omits_and_order_is_kept():
    assert serialize_attrs({"id": None, "name": "n", "data-x": "1"}) == (
        'name="n" data-x="1"'
    )
    assert serialize_attrs({}) == ""


def test_native_boolean_attributes():
    assert serialize_attrs({"disabled": True, "required": False}) == "disabled"
    with pytest.raises(ValueError, match="boolean attribute"):
        serialize_attrs({"disabled": "false"})
    with pytest.raises(ValueError, match="boolean attribute"):
        serialize_attrs({"required": 1})


def test_hidden_is_enumerated():
    assert serialize_attrs({"hidden": True}) == "hidden"
    assert serialize_attrs({"hidden": False}) == ""
    assert serialize_attrs({"hidden": "until-found"}) == 'hidden="until-found"'
    with pytest.raises(ValueError, match="hidden takes"):
        serialize_attrs({"hidden": "false"})


def test_aria_data_and_htmx_take_the_words_true_and_false():
    attrs = {"aria-expanded": False, "data-open": True, "hx-push-url": True}
    assert serialize_attrs(attrs) == (
        'aria-expanded="false" data-open="true" hx-push-url="true"'
    )
    with pytest.raises(ValueError, match="takes text"):
        serialize_attrs({"title": True})


def test_text_is_escaped_and_parses_back():
    text = "a \"b\" & <c> 'd'"
    assert serialize_attrs({"title": text}) == (
        'title="a &quot;b&quot; &amp; &lt;c&gt; &#x27;d&#x27;"'
    )
    assert button({"title": text}) == {"title": text}


def test_marked_safe_text_keeps_entities_and_encodes_literal_quotes():
    safe = mark_safe('x &quot;y&quot; "z" &amp; <b>')
    assert serialize_attrs({"title": safe}) == (
        'title="x &quot;y&quot; &quot;z&quot; &amp; <b>"'
    )
    assert button({"title": safe}) == {"title": 'x "y" "z" & <b>'}


def test_a_marked_safe_value_cannot_inject_an_attribute():
    payload = mark_safe('"x" onmouseover="alert(1)"')
    parsed = button({"title": payload})
    assert parsed == {"title": '"x" onmouseover="alert(1)"'}
    assert "onmouseover" not in parsed


def test_numbers_and_lazy_text():
    assert serialize_attrs({"data-count": 0, "data-ratio": 1.5}) == (
        'data-count="0" data-ratio="1.5"'
    )
    assert serialize_attrs({"title": gettext_lazy("Close")}) == 'title="Close"'


@pytest.mark.parametrize("value", [{"a": 1}, ["a"], ("a",), {"a"}, object()])
def test_structured_values_are_refused(value):
    with pytest.raises(TypeError, match="takes text, not a"):
        serialize_attrs({"hx-vals": value})


def test_htmx_destinations_stay_on_this_origin():
    assert serialize_attrs({"hx-get": "/x/?p=1&q=2"}) == 'hx-get="/x/?p=1&amp;q=2"'
    assert button({"hx-get": "/x/?p=1&q=2"}) == {"hx-get": "/x/?p=1&q=2"}
    for name in ("hx-get", "hx-post", "hx-put", "hx-patch", "hx-delete", "data-hx-get"):
        with pytest.raises(ValueError, match=r"scheme|protocol-relative"):
            serialize_attrs({name: "https://evil.example/"})
        with pytest.raises(ValueError, match="scheme"):
            serialize_attrs({name: "javascript:alert(1)"})


def test_history_attributes_take_a_word_or_a_local_url():
    assert serialize_attrs({"hx-push-url": "true", "hx-replace-url": "false"}) == (
        'hx-push-url="true" hx-replace-url="false"'
    )
    assert serialize_attrs({"hx-push-url": "/users/"}) == 'hx-push-url="/users/"'
    with pytest.raises(ValueError, match="protocol-relative"):
        serialize_attrs({"data-hx-push-url": "//evil.example/"})


def test_a_marked_safe_destination_is_validated_as_the_browser_reads_it():
    with pytest.raises(ValueError, match="scheme"):
        serialize_attrs({"hx-get": mark_safe("javascript&#58;alert(1)")})
    # Ordinary text is validated as written: this is a relative path named literally so
    assert serialize_attrs({"hx-get": "javascript&#58;alert(1)"}) == (
        'hx-get="javascript&amp;#58;alert(1)"'
    )
    assert button({"hx-get": "javascript&#58;alert(1)"}) == {
        "hx-get": "javascript&#58;alert(1)",
    }


def test_attribute_value():
    assert attribute_value('a "b"') == "a &quot;b&quot;"
    assert attribute_value(mark_safe('&lt;a&gt; "b"')) == "&lt;a&gt; &quot;b&quot;"
    assert attribute_value(3) == "3"


def test_url_value():
    assert url_value("/a?b=1&c=2", navigation_url) == "/a?b=1&amp;c=2"
    assert url_value(mark_safe("/a?b=1&amp;c=2"), navigation_url) == "/a?b=1&amp;c=2"
    assert url_value("https://example.com/", navigation_url) == "https://example.com/"
    with pytest.raises(ValueError, match="scheme"):
        url_value("https://example.com/", local_url)
    with pytest.raises(ValueError, match="missing"):
        url_value(None, navigation_url)
