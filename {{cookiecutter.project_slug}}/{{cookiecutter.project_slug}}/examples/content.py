"""What the examples page shows: the examples it names, their sources as written, and
the sample data of its htmx demos. Nothing is stored: the page keeps no state on the
server, since every environment routes it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from django.template import Engine


@dataclass(frozen=True)
class Example:
    """One example: a template under ``templates/examples/``, rendered and shown."""

    name: str
    title: str

    @property
    def template_name(self) -> str:
        return f"examples/{self.name}.html"

    @property
    def source(self) -> str:
        return source(self.name)


@dataclass(frozen=True)
class Task:
    """A row of the filtered table. ``badge`` is a whole daisyUI class, written out
    here because Tailwind generates a class only where it finds the whole name."""

    title: str
    status: str
    badge: str


@dataclass(frozen=True)
class Tab:
    slug: str
    title: str
    body: str


# The examples without a request of their own, in the order the page shows them
STATIC_EXAMPLES: Final = (
    Example("theme", "The theme's colours"),
    Example("buttons", "Buttons"),
    Example("alerts", "Alerts"),
    Example("badges", "Badges"),
    Example("card", "Cards"),
)
# The templates of the htmx demos, which the page places itself
HTMX_EXAMPLES: Final = (
    "form",
    "filter",
    "results",
    "toggle",
    "tabs",
    "modal",
    "notices",
)

TASKS: Final = (
    Task("Draft the landing page", "Done", "badge-success"),
    Task("Choose the brand colours", "Done", "badge-success"),
    Task("Write the sign-up email", "In review", "badge-info"),
    Task("Translate the navigation", "In review", "badge-info"),
    Task("Set up the staging server", "Blocked", "badge-error"),
    Task("Order the domain name", "Done", "badge-success"),
    Task("Plan the launch", "Planned", "badge-neutral"),
    Task("Invite the first users", "Planned", "badge-neutral"),
    Task("Review the privacy policy", "Blocked", "badge-error"),
    Task("Measure the first week", "Planned", "badge-neutral"),
    Task("Tidy the backlog", "In review", "badge-info"),
    Task("Celebrate", "Planned", "badge-neutral"),
)
TASKS_PER_PAGE: Final = 5

TABS: Final = (
    Tab("overview", "Overview", "A tab is a link: without htmx it loads this page."),
    Tab("activity", "Activity", "With htmx, only this panel came from the server."),
    Tab("settings", "Settings", "The server marks the tab it rendered as selected."),
)


def source(name: str) -> str:
    """The template of the example ``name`` as it is written, for the page to show.

    Only the examples this module names have a source: the page never reads a
    template a request could name.
    """
    names = (*(example.name for example in STATIC_EXAMPLES), *HTMX_EXAMPLES)
    if name not in names:
        msg = f"{name!r} is not an example"
        raise ValueError(msg)
    template = Engine.get_default().get_template(f"examples/{name}.html")
    return template.source.strip()


def matching_tasks(query: str) -> list[Task]:
    """The tasks whose title or status holds ``query``, whatever its case."""
    needle = query.strip().casefold()
    return [
        task
        for task in TASKS
        if needle in task.title.casefold() or needle in task.status.casefold()
    ]


def tab_for(slug: str | None) -> Tab:
    """The tab a request names, or the first one."""
    return next((tab for tab in TABS if tab.slug == slug), TABS[0])
