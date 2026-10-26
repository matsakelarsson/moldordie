"""``startapp`` as this project runs it: a new app under the package, from the template.

Django's own command writes an empty app into the working directory. This one copies
the app template beside the scaffold (``scaffold/apps.py``) into the package, under
the name given and with its model called what ``--model`` says (``scaffold/names.py``,
``scaffold/copying.py``), and prints where the new app is registered. The copy is a
complete app whose tests pass once it is.
"""

from __future__ import annotations

import keyword
from functools import partial
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from {{ cookiecutter.project_slug }}.scaffold.copying import copy_renamed
from {{ cookiecutter.project_slug }}.scaffold.copying import run_formatters
from {{ cookiecutter.project_slug }}.scaffold.names import APP_TEMPLATE
from {{ cookiecutter.project_slug }}.scaffold.names import PLACEHOLDER_APP
from {{ cookiecutter.project_slug }}.scaffold.names import PLACEHOLDER_MODEL
from {{ cookiecutter.project_slug }}.scaffold.names import Names
from {{ cookiecutter.project_slug }}.scaffold.names import camel_case
from {{ cookiecutter.project_slug }}.scaffold.names import clashes
from {{ cookiecutter.project_slug }}.scaffold.names import identifiers_of
from {{ cookiecutter.project_slug }}.scaffold.names import rename

if TYPE_CHECKING:
    from django.core.management.base import CommandParser

# What to add where, the code as it goes in: the repository's integration scripts make
# these edits, and its tests hold each line here to what they insert
NEXT_STEPS = """\
Created the app {package}.{app} with its model {model} in {directory}.
Register it, then run "manage.py migrate" for its first migration:

  - add "{package}.{app}" to LOCAL_APPS in config/settings/base.py
  - add path("{app}/", include("{package}.{app}.urls", namespace="{app}"))
    to urlpatterns in config/urls.py
{%- if cookiecutter.rest_api == 'Django Ninja' %}
  - add api.add_router("/{plural}/", "{package}.{app}.api.views.router")
    to config/api.py
{%- elif cookiecutter.rest_api == 'DRF' %}
  - add from {package}.{app}.api.views import {model}ViewSet and
    router.register("{plural}", {model}ViewSet) to config/api_router.py
{%- endif %}
"""
NOT_FORMATTED = """\
The copy is not laid out as the pre-commit hooks want it; they do that at the first
commit:
{problems}
"""


def is_app_name(name: str) -> bool:
    """A lowercase identifier, not a keyword: a directory, a label, a namespace."""
    lowercase = name == name.lower()
    return name.isidentifier() and lowercase and not keyword.iskeyword(name)


def is_model_name(name: str) -> bool:
    """An identifier in CapWords that is not a keyword."""
    return name.isidentifier() and name[:1].isupper() and not keyword.iskeyword(name)


class Command(BaseCommand):
    help = "Create an app from the app template, under the package"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "name",
            help="The app's name, a lowercase identifier: its directory under the "
            "package, its label and its URL namespace",
        )
        parser.add_argument(
            "--model",
            help="The name of its model, in CapWords; the app's name in CapWords when "
            "left out",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        name: str = options["name"]
        model: str = options["model"] or camel_case(name)
        package = settings.APPS_DIR.name
        if not is_app_name(name):
            msg = f"'{name}' is not a lowercase identifier, so it cannot name an app."
            raise CommandError(msg)
        directory = settings.APPS_DIR / name
        if directory.exists():
            msg = f"{directory} exists already."
            raise CommandError(msg)
        if (settings.APPS_DIR / f"{name}.py").exists():
            msg = f"'{name}' is the name of a module of {package} already."
            raise CommandError(msg)
        if not is_model_name(model):
            msg = f"'{model}' is not in CapWords, so it cannot name a model."
            raise CommandError(msg)
        # A name the template uses for something else would be renamed onto it
        identifiers = identifiers_of(APP_TEMPLATE)
        checks = [
            (name, "an app", Names(app=name, model=PLACEHOLDER_MODEL)),
            (model, "a model", Names(app=PLACEHOLDER_APP, model=model)),
        ]
        for given, what, names in checks:
            taken = clashes(names, identifiers)
            if taken:
                listed = ", ".join(sorted(taken))
                msg = f"'{given}' cannot name {what}: the app template has {listed}."
                raise CommandError(msg)
        names = Names(app=name, model=model)
        copy_renamed(APP_TEMPLATE, directory, partial(rename, names=names))
        problems = run_formatters(directory)
        self.stdout.write(
            NEXT_STEPS.format(
                package=package,
                app=name,
                model=model,
                plural=f"{names.model_name}s",
                directory=directory.relative_to(settings.BASE_DIR),
            ),
        )
        if problems:
            listed = "\n".join(f"  - {problem}" for problem in problems)
            warning = NOT_FORMATTED.format(problems=listed)
            self.stdout.write(self.style.WARNING(warning))
