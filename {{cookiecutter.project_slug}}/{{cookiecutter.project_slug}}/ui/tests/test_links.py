import pytest

from {{ cookiecutter.project_slug }}.ui.links import local_url
from {{ cookiecutter.project_slug }}.ui.links import navigation_url

RELATIVE = [
    "/users/~update/",
    "users/",
    "../about/",
    "?page=2",
    "#top",
    "/a?b=1&c=2#d",
    ".",
]
ABSOLUTE = [
    "https://example.com/",
    "http://localhost:8000/x",
    "https://docs.example.org/a?b=c",
]
HOSTILE = [
    "",
    " /users/",
    "/users/ ",
    "/users/\n",
    "java\tscript:alert(1)",
    "\\\\evil.example",
    "/a\\b",
    "//evil.example/",
    "///evil.example/",
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "data:text/html,x",
    "mailto:a@example.com",
    "http:///path",
    "http://",
]


@pytest.mark.parametrize("url", RELATIVE + ABSOLUTE)
def test_navigation_accepts_relative_and_http_urls(url):
    assert navigation_url(url) == url


@pytest.mark.parametrize("url", HOSTILE)
def test_navigation_rejects_what_could_leave_the_page_unsafely(url):
    with pytest.raises(ValueError, match=r"URL|whitespace|control|protocol-relative"):
        navigation_url(url)


@pytest.mark.parametrize("url", RELATIVE)
def test_local_accepts_relative_references(url):
    assert local_url(url) == url


@pytest.mark.parametrize("url", HOSTILE + ABSOLUTE)
def test_local_rejects_everything_off_this_origin(url):
    reasons = r"URL|whitespace|control|protocol-relative|scheme"
    with pytest.raises(ValueError, match=reasons):
        local_url(url)


def test_a_colon_in_the_first_segment_reads_as_a_scheme():
    with pytest.raises(ValueError, match="scheme"):
        local_url("foo:bar/")
    assert local_url("./foo:bar/") == "./foo:bar/"
