"""What the showcase shows: its examples, the components it documents and the sample
tasks it pages through.

An example is a template under ``templates/ui/examples/``, rendered live by the showcase
and shown as written by ``example_source``; a component's contract is the comment its
template opens with, shown by ``component_contract``. Both read only the templates named
here, from the files as written rather than as Cotton compiles them (docs/frontend.rst).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Final

from django.core.paginator import Paginator
from django.template import Engine
from django.urls import reverse

if TYPE_CHECKING:
    from django.http import HttpRequest

EXAMPLES: Final = (
    "button",
    "link",
    "card",
    "alert",
    "badge",
    "field",
    "form",
    "table",
    "pagination",
    "empty_state",
)
COMPONENTS: Final = (
    "button",
    "link",
    "card",
    "alert",
    "badge",
    "field",
    "table",
    "pagination",
    "empty_state",
)
# The comment a component's template opens with. The braces are character classes, so
# Cookiecutter, which renders this file as a template, leaves the pattern alone.
RE_CONTRACT: Final = re.compile(
    r"\A[{]% comment %[}]\n(?P<text>.*?)\n[{]% endcomment %[}]",
    re.DOTALL,
)
TASKS_PER_PAGE: Final = 3
# Where the results are on the showcase page, so a link without htmx lands on them
RESULTS_FRAGMENT: Final = "#showcase-pagination"


@dataclass(frozen=True)
class Task:
    """A row of the showcase's results."""

    title: str
    status: str
    level: str


_STATUSES: Final = (
    ("Open", "neutral"),
    ("In review", "info"),
    ("Done", "success"),
    ("Due soon", "warning"),
    ("Blocked", "error"),
)
TASKS: Final = tuple(
    Task(f"Sample task {number}", *_STATUSES[number % len(_STATUSES)])
    for number in range(1, 25)
)


def matching_tasks(query: str) -> list[Task]:
    """The tasks whose title or status holds ``query``, in any letter case."""
    needle = query.casefold()
    return [
        task for task in TASKS if needle in f"{task.title} {task.status}".casefold()
    ]


def page_url(request: HttpRequest, number: int) -> str:
    """The showcase's URL of results page ``number``, the request's other parameters
    kept. Not the request's own path: the preview form posts elsewhere and gets the
    showcase back with its errors."""
    query = request.GET.copy()
    query["page"] = str(number)
    return f"{reverse('showcase:index')}?{query.urlencode()}{RESULTS_FRAGMENT}"


def results(request: HttpRequest, query: str) -> dict[str, Any]:
    """The page of tasks matching ``query`` that the request asks for, with the URLs
    the pagination component takes: previous, next and every page's."""
    paginator = Paginator(matching_tasks(query), TASKS_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    numbers = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
    previous_url = next_url = ""
    if page.has_previous():
        previous_url = page_url(request, page.previous_page_number())
    if page.has_next():
        next_url = page_url(request, page.next_page_number())
    return {
        "page": page,
        "previous_url": previous_url,
        "next_url": next_url,
        # The ellipsis is a pair with no URL
        "page_urls": [
            (number, page_url(request, number) if isinstance(number, int) else "")
            for number in numbers
        ],
    }


def example_source(name: str) -> str:
    """The example ``name`` as written, one of ``EXAMPLES``."""
    if name not in EXAMPLES:
        msg = f"{name!r} is not an example of the showcase: {', '.join(EXAMPLES)}"
        raise ValueError(msg)
    return _source(f"ui/examples/{name}.html").strip()


def component_contract(name: str) -> str:
    """The contract of the component ``name``, one of ``COMPONENTS``: the comment its
    template opens with, as one paragraph."""
    if name not in COMPONENTS:
        msg = f"{name!r} is not a component of the showcase: {', '.join(COMPONENTS)}"
        raise ValueError(msg)
    template_name = f"cotton/ui/{name}.html"
    match = RE_CONTRACT.match(_source(template_name))
    if match is None:
        msg = f"{template_name} does not open with a comment"
        raise ValueError(msg)
    return " ".join(match.group("text").split())


def _source(template_name: str) -> str:
    """A template's file as written, found by the engine's loaders."""
    origin = Engine.get_default().get_template(template_name).origin
    return Path(origin.name).read_text(encoding="utf-8")
