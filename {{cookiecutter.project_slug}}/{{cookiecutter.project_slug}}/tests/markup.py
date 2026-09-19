"""Reading rendered markup in the tests: the elements and their parsed attributes."""

from __future__ import annotations

from html.parser import HTMLParser

Attributes = dict[str, str | None]


class _Elements(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, Attributes]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.found.append((tag, dict(attrs)))


def elements(markup: str, tag: str) -> list[Attributes]:
    """The attributes of every ``tag`` element in ``markup``, entities decoded."""
    parser = _Elements()
    parser.feed(markup)
    return [attrs for found, attrs in parser.found if found == tag]


def element(
    markup: str,
    tag: str,
    key: str | None = None,
    value: str | None = None,
) -> Attributes:
    """The attributes of the one ``tag`` element in ``markup``, or of the one whose
    ``key`` attribute is ``value``."""
    found = elements(markup, tag)
    if key is not None:
        found = [attrs for attrs in found if attrs.get(key) == value]
    assert len(found) == 1, found
    return found[0]
