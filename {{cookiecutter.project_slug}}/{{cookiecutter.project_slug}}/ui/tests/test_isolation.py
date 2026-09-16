"""A component sees its inputs, the request and the context processors, never the page's
variables. The setting behind this, COTTON_ENABLE_CONTEXT_ISOLATION, is what Cotton 2.7
offers; its successor is COTTON_ISOLATE_BY_DEFAULT, and this test says which the
installed release honours."""

import pytest
from django.template.loader import render_to_string

from {{ cookiecutter.project_slug }}.ui.tests.markup import elements


@pytest.mark.usefixtures("fixture_templates")
def test_a_component_reads_only_what_it_is_given(rf):
    context = {"page_var": "leaked"}
    html = render_to_string("tests/isolation.html", context, request=rf.get("/"))
    bare, explicit = elements(html, "p")
    assert bare["data-page"] == ""
    assert bare["data-method"] == "GET"
    assert bare["data-csrf"] == "yes"
    assert bare["data-label"] == ""
    assert explicit["data-label"] == "leaked"
    assert explicit["data-page"] == ""
